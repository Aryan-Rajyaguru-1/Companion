// Package ota implements network firmware upload (OTA) for devices running
// the ArduinoOTA library (ESP32 / ESP8266 cores).
//
// It is a from-scratch Go implementation of the ArduinoOTA wire protocol:
//
//	UDP invite  → "<cmd> <hostPort> <size> <md5>\n"  → device replies "OK"
//	Password    → device replies "AUTH <nonce>" (64-hex), client answers
//	              "200 <cnonce> <response>\n" where response is
//	              SHA256(PBKDF2-HMAC-SHA256(pw, "<nonce>:<cnonce>", 10000)
//	              + ":" + nonce + ":" + cnonce)
//	TCP         → the DEVICE dials back to host:port and streams the image
//	              itself, ACKing every chunk with an ASCII byte count and
//	              finally "OK" (success) or an error string.
//
// Protocol reference: ArduinoOTA.cpp in the installed ESP32 Arduino core
// (no Arduino code was copied; constants and handshake order only).
package ota

import (
	"bufio"
	"context"
	"crypto/hmac"
	"crypto/md5"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net"
	"os"
	"strconv"
	"strings"
	"time"
)

// Wire constants shared with the ArduinoOTA library.
const (
	CmdFlash  = 0    // U_FLASH   — update sketch flash partition
	CmdFS     = 101  // U_SPIFFS  — update filesystem image (U_FLASHFS=100 legacy)
	CmdAuth   = 200  // U_AUTH    — second-leg auth packet
	UDPReport = 5353 // mDNS/OTA status report port

	pbkdf2Iterations = 10000
	chunkSize        = 1024
	acceptTimeout    = 15 * time.Second
)

// Device is one OTA-capable device discovered on the network.
type Device struct {
	Host string // IP address
	Port int    // OTA port (3232)
	Name string // hostname (e.g. "companion-bridge")
}

// Options controls a Push operation.
type Options struct {
	ImagePath  string // path to the .bin image
	DeviceIP   string // device IP (from discovery or explicit)
	DevicePort int    // device OTA port; 0 → 3232
	Password   string // OTA password ("", or "sha256:..." for pre-hashed)
	HostIP     string // local IP the device should dial back to
	HostPort   int    // local TCP port to accept the device connection
	OnProgress func(sent, total int64)
	OnMessage  func(string)
}

func (o *Options) log(msg string) {
	if o.OnMessage != nil {
		o.OnMessage(msg)
	}
}

func (o *Options) progress(sent, total int64) {
	if o.OnProgress != nil {
		o.OnProgress(sent, total)
	}
}

// ── Discovery ─────────────────────────────────────────────────────

// Discover finds OTA devices advertising `_arduino._tcp` via mDNS.
// queryMDNS (mdns_discovery.go) does the heavy lifting; nil → empty result.
func Discover(ctx context.Context, timeout time.Duration) []Device {
	svcs := queryMDNS(ctx, timeout)
	out := make([]Device, 0, len(svcs))
	for _, s := range svcs {
		out = append(out, Device{Host: s.IP, Port: s.Port, Name: s.Name})
	}
	return out
}

// Probe checks whether a device is listening on the OTA port.
// A pure TCP connect suffices — ArduinoOTA accepts and times out idle peers.
func Probe(host string, port int) error {
	if port <= 0 {
		port = 3232
	}
	conn, err := net.DialTimeout("tcp", net.JoinHostPort(host, strconv.Itoa(port)), 3*time.Second)
	if err != nil {
		return fmt.Errorf("no OTA server at %s:%d — is the device running a sketch with ArduinoOTA.begin()?",
			host, port)
	}
	conn.Close()
	return nil
}

// localIPFor returns the source IP the host would use to reach deviceIP.
func localIPFor(deviceIP string) (string, error) {
	if deviceIP == "" {
		return "", errors.New("empty device IP")
	}
	conn, err := net.DialTimeout("udp", net.JoinHostPort(deviceIP, "9"), 2*time.Second)
	if err != nil {
		return "", err
	}
	defer conn.Close()
	return conn.LocalAddr().(*net.UDPAddr).IP.String(), nil
}

// firstNonLoopback returns a usable LAN IPv4 address of this host.
func firstNonLoopback() (string, error) {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return "", err
	}
	for _, a := range addrs {
		if ipn, ok := a.(*net.IPNet); ok && !ipn.IP.IsLoopback() {
			if v4 := ipn.IP.To4(); v4 != nil {
				return v4.String(), nil
			}
		}
	}
	return "", errors.New("no non-loopback IPv4 address found")
}

// ── Push ──────────────────────────────────────────────────────────

// Push performs a full OTA transfer.
func Push(ctx context.Context, opts Options) error {
	port := opts.DevicePort
	if port <= 0 {
		port = 3232
	}

	img, md5sum, size, err := openImage(opts.ImagePath)
	if err != nil {
		return err
	}
	defer img.Close()

	hostIP := opts.HostIP
	if hostIP == "" {
		if hostIP, err = localIPFor(opts.DeviceIP); err != nil {
			if hostIP, err = firstNonLoopback(); err != nil {
				return fmt.Errorf("cannot determine host IP for OTA: %w", err)
			}
		}
	}
	hostPort := opts.HostPort
	if hostPort == 0 {
		hostPort = randomPort(10000, 60000)
	}

	// Start accepting the device's dial-back BEFORE the invite — the device
	// connects immediately after replying "OK".
	ln, err := net.Listen("tcp", net.JoinHostPort(hostIP, strconv.Itoa(hostPort)))
	if err != nil {
		return fmt.Errorf("listen on %s:%d: %w", hostIP, hostPort, err)
	}
	acceptCh := make(chan net.Conn, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			acceptCh <- nil
			return
		}
		acceptCh <- conn
	}()
	defer ln.Close()

	// ── UDP invite ──────────────────────────────────────────────
	opts.log(fmt.Sprintf("» OTA target: %s:%d  image: %d bytes (md5 %s…)",
		opts.DeviceIP, port, size, md5sum[:12]))

	inv, err := invite(ctx, opts.DeviceIP, port, hostPort, size, md5sum, opts.Password)
	if err != nil {
		return err
	}
	opts.log("» Device accepted OTA invitation")

	// Wait for the device's dial-back connection.
	var conn net.Conn
	select {
	case conn = <-acceptCh:
		ln.Close() // stop accepting; transfer happens on conn
	case <-time.After(acceptTimeout):
		return errors.New("device did not connect back for the image transfer (15s timeout)")
	case <-ctx.Done():
		return ctx.Err()
	}
	if conn == nil {
		return fmt.Errorf("accept failed on %s:%d", hostIP, hostPort)
	}
	defer conn.Close()
	conn.SetDeadline(time.Time{}) // streaming may be slow; no overall deadline

	return streamImage(ctx, conn, img, size, inv, opts)
}

// openImage opens the image, returning the reader, its MD5 and size.
func openImage(path string) (*os.File, string, int64, error) {
	img, err := os.Open(path)
	if err != nil {
		return nil, "", 0, fmt.Errorf("open image: %w", err)
	}
	st, err := img.Stat()
	if err != nil {
		img.Close()
		return nil, "", 0, fmt.Errorf("stat image: %w", err)
	}
	h := md5.New()
	if _, err := io.Copy(h, img); err != nil {
		img.Close()
		return nil, "", 0, fmt.Errorf("hash image: %w", err)
	}
	sum := hex.EncodeToString(h.Sum(nil))
	if _, err := img.Seek(0, io.SeekStart); err != nil {
		img.Close()
		return nil, "", 0, fmt.Errorf("rewind image: %w", err)
	}
	return img, sum, st.Size(), nil
}

// inviteResult carries post-handshake state for the streaming stage.
type inviteResult struct {
	// reserved for future per-device flags (partition selection etc.)
	ready bool
}

// invite performs the UDP handshake and returns once the device is ready.
// hostPort is embedded in the invite — the device dials back to it.
func invite(ctx context.Context, devIP string, devPort, hostPort int,
	size int64, md5sum, password string) (inviteResult, error) {

	var res inviteResult
	// ArduinoOTA parses with UDP.parseInt() after one discarded byte, then
	// readStringUntil('\n') for the md5 — whitespace-separated ASCII works.
	msg := fmt.Sprintf("%d %d %d %s\n", CmdFlash, hostPort, size, md5sum)

	raddr := &net.UDPAddr{IP: net.ParseIP(devIP), Port: devPort}
	if raddr.IP == nil {
		// Allow "host:port" strings passed via Options.DeviceIP.
		h, p, splitErr := net.SplitHostPort(devIP)
		if splitErr != nil {
			return res, fmt.Errorf("invalid device address %q", devIP)
		}
		if pp, _ := strconv.Atoi(p); pp > 0 {
			devPort = pp
			raddr.Port = pp
		}
		raddr.IP = net.ParseIP(h)
		if raddr.IP == nil {
			return res, fmt.Errorf("invalid device IP %q", h)
		}
	}

	udp, err := net.DialUDP("udp4", nil, raddr)
	if err != nil {
		return res, fmt.Errorf("udp dial: %w", err)
	}
	defer udp.Close()

	reply, err := udpExchange(ctx, udp, []byte(msg), 10*time.Second)
	if err != nil {
		return res, fmt.Errorf("OTA invitation: %w", err)
	}
	reply = strings.TrimSpace(reply)

	switch {
	case reply == "OK":
		res.ready = true
		return res, nil

	case strings.HasPrefix(reply, "AUTH "):
		if password == "" {
			return res, errors.New("device requires an OTA password — pass --ota-password")
		}
		nonce := strings.TrimSpace(strings.TrimPrefix(reply, "AUTH "))
		if len(nonce) != 64 {
			return res, fmt.Errorf("bad AUTH nonce length %d (want 64)", len(nonce))
		}
		cnonce, err := randomHex(32)
		if err != nil {
			return res, err
		}
		response, err := otaResponse(password, nonce, cnonce)
		if err != nil {
			return res, err
		}
		authMsg := fmt.Sprintf("%d %s %s\n", CmdAuth, cnonce, response)
		reply2, err := udpExchange(ctx, udp, []byte(authMsg), 10*time.Second)
		if err != nil {
			return res, fmt.Errorf("OTA auth: %w", err)
		}
		reply2 = strings.TrimSpace(reply2)
		if reply2 != "OK" {
			if strings.Contains(reply2, "Authentication Failed") || reply2 == "" {
				return res, errors.New("OTA authentication failed — wrong password?")
			}
			return res, fmt.Errorf("OTA auth rejected: %s", reply2)
		}
		res.ready = true
		return res, nil

	case strings.Contains(reply, "Authentication Failed"):
		return res, errors.New("OTA authentication failed — wrong password?")

	case reply == "":
		return res, errors.New("empty reply from device (not running ArduinoOTA?)")

	default:
		return res, fmt.Errorf("unexpected device reply: %q", reply)
	}
}

// udpExchange writes one UDP packet and waits for the device's ASCII reply.
func udpExchange(ctx context.Context, udp *net.UDPConn, payload []byte, timeout time.Duration) (string, error) {
	if _, err := udp.Write(payload); err != nil {
		return "", err
	}
	buf := make([]byte, 512)
	udp.SetReadDeadline(time.Now().Add(timeout))
	n, err := udp.Read(buf)
	if err != nil {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return "", fmt.Errorf("no answer from device (%v) — is it powered and on this network?", err)
	}
	return string(buf[:n]), nil
}

// streamImage serves the image to the device over the dial-back connection.
func streamImage(ctx context.Context, conn net.Conn, img io.Reader, size int64,
	_ inviteResult, opts Options) error {

	opts.log("» Device connected — streaming image…")
	reader := bufio.NewReader(conn)
	buf := make([]byte, chunkSize)
	var sent int64

	for sent < size {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		n, rerr := img.Read(buf)
		if n > 0 {
			if _, werr := conn.Write(buf[:n]); werr != nil {
				return fmt.Errorf("write to device: %w", werr)
			}
			// ArduinoOTA ACKs every chunk with the count of bytes written.
			line, aerr := readACKLine(reader)
			if aerr != nil {
				return fmt.Errorf("device stopped ACKing at %d/%d bytes: %w", sent, size, aerr)
			}
			acked, perr := strconv.ParseInt(strings.TrimSpace(line), 10, 64)
			if perr != nil || acked <= 0 {
				// A non-numeric reply here is the device's error output.
				return fmt.Errorf("device rejected data at offset %d: %q", sent, strings.TrimSpace(line))
			}
			sent += int64(n)
			opts.progress(sent, size)
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return fmt.Errorf("read image: %w", rerr)
		}
	}

	// Final verdict: "OK" on success, error text otherwise.
	conn.SetReadDeadline(time.Now().Add(15 * time.Second))
	final, err := readFinal(reader)
	if err != nil {
		return fmt.Errorf("no final device response: %w", err)
	}
	final = strings.TrimSpace(final)
	if !strings.Contains(final, "OK") {
		return fmt.Errorf("device reported failure: %s", final)
	}
	opts.progress(size, size)
	opts.log(fmt.Sprintf("✓ OTA transfer complete — %d bytes written, device rebooting", size))
	return nil
}

// readACKLine reads one ASCII acknowledgement from the device. ACKs are
// decimal byte counts, usually newline-terminated; "OK" can also arrive
// mid-stream and is returned verbatim so the caller can surface it.
func readACKLine(r *bufio.Reader) (string, error) {
	line, err := r.ReadString('\n')
	if err == nil {
		return line, nil
	}
	// Partial line without newline (device may ACK without terminator).
	if len(line) > 0 {
		// Give the peer a short grace period for the rest of the line.
		deadline := time.Now().Add(2 * time.Second)
		for time.Now().Before(deadline) {
			b, berr := r.ReadByte()
			if berr != nil {
				break
			}
			if b == '\n' {
				return line + "\n", nil
			}
			line += string(b)
		}
		return line, nil
	}
	return "", err
}

// readFinal collects the device's final response line(s).
func readFinal(r *bufio.Reader) (string, error) {
	var sb strings.Builder
	deadline := time.Now().Add(15 * time.Second)
	for time.Now().Before(deadline) {
		b, err := r.ReadByte()
		if err != nil {
			if sb.Len() > 0 {
				return sb.String(), nil
			}
			return "", err
		}
		if b == '\n' && sb.Len() > 0 {
			break
		}
		sb.WriteByte(b)
	}
	return sb.String(), nil
}

// ── Auth helpers ──────────────────────────────────────────────────

// otaResponse computes the challenge response for a device that stores
// SHA256(password) (the default of ArduinoOTA.setPassword).
// password may be "sha256:<64hex>" to supply a pre-hashed secret.
func otaResponse(password, nonce, cnonce string) (string, error) {
	pwHash := password
	if strings.HasPrefix(password, "sk-sha256:") {
		pwHash = strings.TrimPrefix(password, "sk-sha256:")
		if len(pwHash) != 64 {
			return "", errors.New("sk-sha256: password must be 64 hex chars")
		}
	} else {
		sum := sha256.Sum256([]byte(password))
		pwHash = hex.EncodeToString(sum[:])
	}
	salt := nonce + ":" + cnonce
	key := pbkdf2SHA256([]byte(pwHash), []byte(salt), pbkdf2Iterations, 32)
	challenge := hex.EncodeToString(key) + ":" + nonce + ":" + cnonce
	sum := sha256.Sum256([]byte(challenge))
	return hex.EncodeToString(sum[:]), nil
}

// pbkdf2SHA256 is RFC 2898 PBKDF2 with HMAC-SHA256 (implemented locally to
// keep the module dependency-free).
func pbkdf2SHA256(password, salt []byte, iter, keyLen int) []byte {
	hashLen := sha256.Size
	numBlocks := (keyLen + hashLen - 1) / hashLen
	dk := make([]byte, 0, numBlocks*hashLen)
	var blockBuf [4]byte
	for block := 1; block <= numBlocks; block++ {
		blockBuf[0] = byte(block >> 24)
		blockBuf[1] = byte(block >> 16)
		blockBuf[2] = byte(block >> 8)
		blockBuf[3] = byte(block)
		prf := hmac.New(sha256.New, password)
		prf.Write(salt)
		prf.Write(blockBuf[:])
		u := prf.Sum(nil)
		t := make([]byte, len(u))
		copy(t, u)
		for n := 2; n <= iter; n++ {
			prf.Reset()
			prf.Write(u)
			u = prf.Sum(u[:0])
			for i := range t {
				t[i] ^= u[i]
			}
		}
		dk = append(dk, t...)
	}
	return dk[:keyLen]
}

// ── Small helpers ─────────────────────────────────────────────────

func randomHex(nBytes int) (string, error) {
	b := make([]byte, nBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func randomPort(min, max int) int {
	n, err := rand.Int(rand.Reader, big.NewInt(int64(max-min)))
	if err != nil {
		return min
	}
	return min + int(n.Int64())
}
