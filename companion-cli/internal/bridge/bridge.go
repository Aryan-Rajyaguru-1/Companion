// Package bridge implements the TCP client for the ESP32 WiFi bridge.
//
// Control protocol (must match esp32_bridge.ino):
//   Prefix: 0xEF 0xBE <cmd> [payload]
//   0x01 — Enter bootloader
//   0x02 — Reset target
//   0x03 — Release pins
//   0x10 BBBBB — Set baud (uint32 big-endian)
//   0x11 P — Set MCU profile (0=generic 1=ESP32 2=AVR 3=STM32)
//   0x20 — Query status
package bridge

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"strings"
	"time"
)

// ── Control protocol constants ────────────────────────────────────

const (
	ctrlA byte = 0xEF
	ctrlB byte = 0xBE

	CmdEnterBoot  byte = 0x01
	CmdReset      byte = 0x02
	CmdRelease    byte = 0x03
	CmdSetBaud    byte = 0x10
	CmdSetProfile byte = 0x11
	CmdQuery      byte = 0x20
)

// MCU profile IDs — must match profiles[] in esp32_bridge.ino
var ProfileIDs = map[string]byte{
	"generic": 0,
	"esp32":   1,
	"esp8266": 1,
	"avr":     2,
	"arduino": 2,
	"stm32":   3,
}

// ── Client ────────────────────────────────────────────────────────

// Client is a TCP connection to the ESP32 WiFi bridge.
type Client struct {
	host    string
	port    int
	conn    net.Conn
	timeout time.Duration
}

// New creates a new bridge client (not yet connected).
func New(host string, port int) *Client {
	return &Client{
		host:    host,
		port:    port,
		timeout: 30 * time.Second,
	}
}

// Connect opens the TCP connection.
func (c *Client) Connect() error {
	addr := fmt.Sprintf("%s:%d", c.host, c.port)
	conn, err := net.DialTimeout("tcp", addr, 8*time.Second)
	if err != nil {
		return fmt.Errorf("cannot connect to bridge at %s — %w\n"+
			"Is the ESP32 bridge powered and on the same WiFi?", addr, err)
	}

	if tc, ok := conn.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}

	c.conn = conn
	return nil
}

// Close closes the TCP connection.
func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
		c.conn = nil
	}
}

// ── Control commands ──────────────────────────────────────────────

func (c *Client) ctrl(cmd byte, payload ...byte) error {
	msg := append([]byte{ctrlA, ctrlB, cmd}, payload...)
	_, err := c.conn.Write(msg)
	return err
}

// EnterBootloader asserts bootloader entry pins on the target.
func (c *Client) EnterBootloader() error { return c.ctrl(CmdEnterBoot) }

// Reset pulses the target reset pin.
func (c *Client) Reset() error { return c.ctrl(CmdReset) }

// Release releases all control pins to idle state.
func (c *Client) Release() error { return c.ctrl(CmdRelease) }

// SetBaud configures the UART baud rate on the bridge.
func (c *Client) SetBaud(baud uint32) error {
	payload := make([]byte, 4)
	binary.BigEndian.PutUint32(payload, baud)
	return c.ctrl(CmdSetBaud, payload...)
}

// SetProfile sets the MCU reset profile.
func (c *Client) SetProfile(mcu string) error {
	id, ok := ProfileIDs[strings.ToLower(mcu)]
	if !ok {
		id = 0
	}
	return c.ctrl(CmdSetProfile, id)
}

// Query asks the bridge for its status string.
func (c *Client) Query() (string, error) {
	if err := c.ctrl(CmdQuery); err != nil {
		return "", err
	}

	c.conn.SetReadDeadline(time.Now().Add(3 * time.Second))
	buf := make([]byte, 256)
	n, err := c.conn.Read(buf)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(buf[:n])), nil
}

// Write sends raw bytes to the target via UART.
func (c *Client) Write(p []byte) (int, error) {
	return c.conn.Write(p)
}

// Read receives raw bytes from the target via UART.
func (c *Client) Read(p []byte) (int, error) {
	return c.conn.Read(p)
}

// SetDeadline sets the read/write deadline on the underlying connection.
func (c *Client) SetDeadline(t time.Time) error {
	return c.conn.SetDeadline(t)
}

// SetReadDeadline sets the read deadline.
func (c *Client) SetReadDeadline(t time.Time) error {
	return c.conn.SetReadDeadline(t)
}

// ReadByteTimeout reads exactly one byte with timeout.
// (Named ReadByteTimeout rather than ReadByte so its signature does not
// conflict with the io.ByteReader convention flagged by go vet.)
func (c *Client) ReadByteTimeout(timeout time.Duration) (byte, error) {
	if c.conn == nil {
		return 0, fmt.Errorf("bridge client not connected")
	}
	c.conn.SetReadDeadline(time.Now().Add(timeout))
	buf := make([]byte, 1)
	if _, err := io.ReadFull(c.conn, buf); err != nil {
		return 0, err
	}
	return buf[0], nil
}

// ── Ping ─────────────────────────────────────────────────────────

// Ping connects, queries status, and disconnects.
// Returns the status string on success.
func Ping(host string, port int) (string, error) {
	c := New(host, port)
	if err := c.Connect(); err != nil {
		return "", err
	}
	defer c.Close()

	info, err := c.Query()
	if err != nil {
		return "", fmt.Errorf("bridge did not respond to query: %w", err)
	}
	return info, nil
}

// ── Serial Monitor ────────────────────────────────────────────────

// MonitorConfig holds serial monitor settings.
type MonitorConfig struct {
	Host       string
	Port       int
	Baud       uint32
	LineEnding string // "", "\n", "\r", "\r\n"
}

// Monitor connects to the bridge and proxies bytes between the terminal
// and the target. It runs until ctx cancellation or the connection drops.
// onData is called for each chunk received from the target.
func Monitor(cfg MonitorConfig, send <-chan string, onData func([]byte)) error {
	c := New(cfg.Host, cfg.Port)
	if err := c.Connect(); err != nil {
		return err
	}
	defer c.Close()

	// Configure baud rate
	if cfg.Baud > 0 {
		c.SetBaud(cfg.Baud)
	}

	done := make(chan error, 2)

	// Goroutine: receive from bridge → callback
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := c.conn.Read(buf)
			if n > 0 {
				onData(buf[:n])
			}
			if err != nil {
				done <- err
				return
			}
		}
	}()

	// Goroutine: send channel → bridge
	go func() {
		for msg := range send {
			c.Write([]byte(msg + cfg.LineEnding))
		}
		done <- io.EOF
	}()

	err := <-done
	if err == io.EOF {
		return nil
	}
	return err
}
