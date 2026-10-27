// Package bridge implements the TCP client for the ESP32 WiFi bridge.
//
// Control protocol (must match esp32_bridge.ino):
//
//	Prefix: 0xEF 0xBE <cmd> [payload]
//	0x01 — Enter bootloader
//	0x02 — Reset target
//	0x03 — Release pins
//	0x10 BBBBB — Set baud (uint32 big-endian)
//	0x11 P — Set MCU profile (0=generic 1=ESP32 2=AVR 3=STM32)
//	0x20 — Query status
//	0x30 — Authentication begin (client → bridge)
//	0x31 HMAC — Authentication response (client → bridge)
//	0x32 NONCE — Authentication challenge (bridge → client)
//	0x33 — Authentication OK (bridge → client)
//	0x34 — Authentication failed (bridge → client)
//
// LAN firmware requires the HMAC-SHA256 challenge-response before accepting
// any control command or raw UART byte. Old firmware ignores the probe; the
// client falls back only when no key is configured and no challenge arrives.
package bridge

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"strconv"
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

	CmdAuthBegin     byte = 0x30
	CmdAuthResponse  byte = 0x31
	CmdAuthChallenge byte = 0x32
	CmdAuthOK        byte = 0x33
	CmdAuthFail      byte = 0x34

	authNonceLen = 32
)

// Authentication failures are distinguishable so callers and tests can tell
// a missing key apart from a wrong key or firmware that predates auth.
var (
	ErrAuthKeyRequired = errors.New(
		"the bridge requires a key, but none is configured — pipe the BRIDGE_KEY " +
			"from config.local.h to `companion config set bridge.key --stdin` " +
			"or set COMPANION_BRIDGE_KEY")
	ErrAuthRejected = errors.New(
		"the bridge rejected the bridge key — bridge.key must match BRIDGE_KEY " +
			"compiled into the bridge firmware")
	ErrAuthUnsupported = errors.New(
		"the bridge firmware did not answer the authentication challenge — " +
			"reflash it with the current esp32_bridge firmware or clear bridge.key " +
			"to allow legacy unauthenticated mode")
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
	key     string
	conn    net.Conn
	timeout time.Duration
	// authProbe overrides the probe window in tests. Zero means derive it from
	// the key (5s keyed, 500ms unkeyed).
	authProbe time.Duration
	// pending holds bytes received while probing legacy firmware for auth
	// support. They are target UART data, not control replies, and must be
	// delivered by the next Read.
	pending []byte
	// noAuth skips the authentication probe for transports that are already
	// authenticated end to end (a `companion relay bridge` loopback socket).
	noAuth bool
}

// New creates a new bridge client (not yet connected). key is the shared
// BRIDGE_KEY; an empty key opts into legacy unauthenticated firmware only.
func New(host string, port int, key string) *Client {
	return &Client{
		host:    host,
		port:    port,
		key:     key,
		timeout: 30 * time.Second,
	}
}

// NewNoAuth creates a client for a transport that is authenticated outside the
// bridge protocol, such as a `companion relay bridge` loopback socket. It skips
// the authentication probe entirely and speaks the firmware's raw control/UART
// protocol, which is what the relay and esptool expect.
func NewNoAuth(host string, port int) *Client {
	c := New(host, port, "")
	c.noAuth = true
	return c
}

// Connect opens the TCP connection and completes the authentication
// handshake when the firmware offers one. It fails closed: a configured key
// never silently falls back to an unauthenticated connection.
func (c *Client) Connect() error {
	// A reconnect starts a fresh session; never replay bytes captured while
	// probing a previous connection.
	c.pending = nil

	addr := net.JoinHostPort(c.host, strconv.Itoa(c.port))
	conn, err := net.DialTimeout("tcp", addr, 8*time.Second)
	if err != nil {
		return fmt.Errorf("cannot connect to bridge at %s — %w\n"+
			"Is the ESP32 bridge powered and on the same WiFi?\n"+
			"Check: `companion fleet discover` scans the LAN for it. In AP mode its\n"+
			"address is 192.168.4.1 and your laptop must join the bridge's WiFi\n"+
			"network. Windows: allow TCP 3333 through Windows Firewall (Private).",
			addr, err)
	}

	if tc, ok := conn.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}

	c.conn = conn
	if !c.noAuth {
		if err := c.authenticate(); err != nil {
			c.Close()
			return err
		}
	}
	return nil
}

// authenticate probes for the challenge-response protocol. A key implies
// fail-closed: every failure is returned, never downgraded to legacy mode.
// Without a key, old firmware (no challenge) remains usable.
func (c *Client) authenticate() error {
	if err := c.ctrl(CmdAuthBegin); err != nil {
		return fmt.Errorf("sending authentication probe: %w", err)
	}

	// Keyed connections may be queued behind another authenticated client
	// (the IDE keeps its control socket open until esptool starts), so allow
	// a little longer. Unkeyed legacy probing stays short.
	probeTimeout := 500 * time.Millisecond
	if c.key != "" {
		probeTimeout = 5 * time.Second
	}
	if c.authProbe > 0 {
		probeTimeout = c.authProbe
	}
	defer c.conn.SetReadDeadline(time.Time{})
	c.conn.SetReadDeadline(time.Now().Add(probeTimeout))

	header := make([]byte, 3)
	n, err := io.ReadFull(c.conn, header)
	if err != nil {
		// Preserve partial target-UART bytes for the monitor path.
		if n > 0 {
			c.pending = append(c.pending, header[:n]...)
		}
		// Only a timeout proves legacy firmware ignored the probe. A closed
		// socket is not evidence of legacy firmware and must never be treated
		// as a successful unauthenticated Connect.
		if isTimeout(err) {
			if c.key != "" {
				return ErrAuthUnsupported
			}
			return nil // legacy firmware: no auth support, no key configured
		}
		if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
			return fmt.Errorf("bridge closed the connection during authentication: %w", err)
		}
		return fmt.Errorf("reading authentication challenge: %w", err)
	}

	if header[0] != ctrlA || header[1] != ctrlB || header[2] != CmdAuthChallenge {
		// Not a challenge: this is target UART data from legacy firmware.
		c.pending = append(c.pending, header...)
		if c.key != "" {
			return ErrAuthUnsupported
		}
		return nil
	}

	nonce := make([]byte, authNonceLen)
	if _, err := io.ReadFull(c.conn, nonce); err != nil {
		return fmt.Errorf("reading authentication nonce: %w", err)
	}

	if c.key == "" {
		return ErrAuthKeyRequired
	}

	mac := hmac.New(sha256.New, []byte(c.key))
	mac.Write(nonce)
	response := append([]byte{ctrlA, ctrlB, CmdAuthResponse}, mac.Sum(nil)...)
	if _, err := c.conn.Write(response); err != nil {
		return fmt.Errorf("sending authentication response: %w", err)
	}

	status := make([]byte, 3)
	if _, err := io.ReadFull(c.conn, status); err != nil {
		return fmt.Errorf("reading authentication result: %w", err)
	}
	if status[0] != ctrlA || status[1] != ctrlB {
		return fmt.Errorf("unexpected authentication reply: % x", status)
	}
	switch status[2] {
	case CmdAuthOK:
		return nil
	case CmdAuthFail:
		return ErrAuthRejected
	default:
		return fmt.Errorf("unexpected authentication status 0x%02X", status[2])
	}
}

func isTimeout(err error) bool {
	var ne net.Error
	return errors.As(err, &ne) && ne.Timeout()
}

// Close closes the TCP connection. The pointer is intentionally retained:
// callers (for example the daemon's serial reader) may be blocked in Read or
// Write concurrently, and a closed net.Conn returns an error instead of
// turning those calls into a nil dereference.
func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
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
	// Do not prepend c.pending here. On legacy firmware those bytes came from
	// the target UART during the auth probe; mixing them into the status reply
	// made `bridge ping` print boot output. They stay queued for Read.
	buf := make([]byte, 256)
	n := 0
	for n < len(buf) {
		m, err := c.conn.Read(buf[n:])
		n += m
		if n > 0 && bytes.IndexByte(buf[:n], '\n') >= 0 {
			break
		}
		if err != nil {
			if n == 0 {
				return "", err
			}
			break
		}
	}
	return strings.TrimSpace(string(buf[:n])), nil
}

// Write sends raw bytes to the target via UART.
func (c *Client) Write(p []byte) (int, error) {
	return c.conn.Write(p)
}

// Read receives raw bytes from the target via UART. Bytes captured while
// probing legacy firmware for auth support are returned first.
func (c *Client) Read(p []byte) (int, error) {
	if len(c.pending) > 0 {
		n := copy(p, c.pending)
		c.pending = c.pending[n:]
		return n, nil
	}
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
	if len(c.pending) > 0 {
		b := c.pending[0]
		c.pending = c.pending[1:]
		return b, nil
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
func Ping(host string, port int, key string) (string, error) {
	c := New(host, port, key)
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
	Key        string
	Baud       uint32
	LineEnding string // "", "\n", "\r", "\r\n"
}

// Monitor connects to the bridge and proxies bytes between the terminal
// and the target. It runs until ctx cancellation or the connection drops.
// onData is called for each chunk received from the target.
func Monitor(cfg MonitorConfig, send <-chan string, onData func([]byte)) error {
	c := New(cfg.Host, cfg.Port, cfg.Key)
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
			// Read drains bytes captured while probing legacy firmware, so the
			// first monitor line is not lost.
			n, err := c.Read(buf)
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
