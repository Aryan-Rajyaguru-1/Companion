package ota

// Protocol self-test: a from-scratch fake OTA device that speaks the same
// wire protocol as the client (UDP invite + optional PBKDF2 auth + TCP
// dial-back with per-chunk ASCII ACKs and a final verdict). This validates
// the full Push() state machine on loopback — no hardware, no Arduino code.

import (
	"context"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// fakeDevice implements the device side of the OTA protocol.
type fakeDevice struct {
	password  string // "" = no auth
	udpPort   int
	hostPort  int    // learned from the invite
	nonce     string // issued when auth is requested
	imgSize   int64
	gotMD5    string
	gotSize   int64
	gotChunks int
	authTried bool
}

func startFakeDevice(t *testing.T, password string, size int64) *fakeDevice {
	t.Helper()
	d := &fakeDevice{password: password, imgSize: size}

	udp, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.ParseIP("127.0.0.1"), Port: 0})
	if err != nil {
		t.Fatalf("fake device udp listen: %v", err)
	}
	d.udpPort = udp.LocalAddr().(*net.UDPAddr).Port
	go d.serveUDP(udp)
	t.Cleanup(func() { udp.Close() })
	return d
}

func (d *fakeDevice) serveUDP(udp *net.UDPConn) {
	buf := make([]byte, 1024)
	for {
		n, raddr, err := udp.ReadFromUDP(buf)
		if err != nil {
			return
		}
		fields := strings.Fields(string(buf[:n]))
		if len(fields) == 0 {
			udp.WriteToUDP([]byte("ERROR empty packet\n"), raddr)
			continue
		}
		cmd, _ := strconv.Atoi(fields[0])
		switch cmd {
		case CmdFlash: // "<cmd> <hostPort> <size> <md5>"
			if len(fields) != 4 {
				udp.WriteToUDP([]byte("ERROR malformed invite\n"), raddr)
				continue
			}
			d.hostPort, _ = strconv.Atoi(fields[1])
			d.gotSize, _ = strconv.ParseInt(fields[2], 10, 64)
			d.gotMD5 = strings.TrimSpace(fields[3])
			if d.password != "" && !d.authTried {
				d.authTried = true
				d.nonce, _ = randomHex(32)
				udp.WriteToUDP([]byte("AUTH "+d.nonce+"\n"), raddr)
				continue
			}
			udp.WriteToUDP([]byte("OK\n"), raddr)
		case CmdAuth: // "<cmd> <cnonce> <response>"
			if len(fields) != 3 {
				udp.WriteToUDP([]byte("ERROR malformed auth\n"), raddr)
				continue
			}
			resp, err := otaResponse(d.password, d.nonce, fields[1])
			if err != nil || resp != fields[2] {
				udp.WriteToUDP([]byte("Authentication Failed\n"), raddr)
				continue
			}
			udp.WriteToUDP([]byte("OK\n"), raddr)
		default:
			udp.WriteToUDP([]byte("ERROR unknown cmd\n"), raddr)
		}
	}
}

// dialTCP performs the device's dial-back to the host port learned from the
// invite. It mirrors ArduinoOTA.cpp::_runUpdate on the wire:
//   - each chunk is ACKed with a BARE decimal count — no newline
//     (client.printf("%u", written));
//   - if the host sends nothing more within ~1s, the device re-sends the
//     same ACK up to 3 times before giving up (the starve-and-retry that
//     the old newline-waiting client tripped over on real hardware);
//   - the final verdict is a bare "OK" (no terminator), sent after
//     Update.end(), and may be COALESCED with the last ACK ("512OK").
func (d *fakeDevice) dialTCP(fail bool) {
	deadline := time.Now().Add(10 * time.Second)
	var conn net.Conn
	for time.Now().Before(deadline) {
		var err error
		conn, err = net.DialTimeout("tcp",
			net.JoinHostPort("127.0.0.1", strconv.Itoa(d.hostPort)), time.Second)
		if err == nil {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if conn == nil {
		return
	}
	defer conn.Close()
	got := int64(0)
	buf := make([]byte, chunkSize)
	for got < d.gotSize {
		want := int64(chunkSize)
		if remain := d.gotSize - got; remain < want {
			want = remain
		}
		n, rerr := io.ReadFull(conn, buf[:want])
		if rerr != nil {
			return
		}
		got += int64(n)
		d.gotChunks++
		fmt.Fprintf(conn, "%d", n) // bare ACK — ArduinoOTA sends no newline
		if rerr != nil || got >= d.gotSize {
			break
		}
		// Starve-retry: if the next chunk doesn't arrive promptly, the real
		// device re-ACKs up to 3 times at ~1s intervals. Emulate once so the
		// client's quiet-period reader must tolerate duplicate ACKs.
		ackN := n
		go func() {
			time.Sleep(1200 * time.Millisecond)
			fmt.Fprintf(conn, "%d", ackN)
		}()
	}
	if fail {
		conn.Write([]byte("ERROR flash failed"))
		return
	}
	// Final verdict, unframed, often coalesced with the last ACK in real
	// captures — here it follows the last bare ACK with no separator.
	conn.Write([]byte("OK"))
}

func pushTestImage(t *testing.T, size int) string {
	t.Helper()
	img := filepath.Join(t.TempDir(), "firmware.bin")
	data := make([]byte, size)
	for i := range data {
		data[i] = byte(i % 251)
	}
	if err := os.WriteFile(img, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return img
}

// pushAsync runs Push on a goroutine, waits for the fake device to learn the
// host port from the invite, then serves the TCP dial-back side.
func pushAsync(t *testing.T, dev *fakeDevice, img, password string) error {
	t.Helper()
	errCh := make(chan error, 1)
	go func() {
		errCh <- Push(context.Background(), Options{
			ImagePath:  img,
			DeviceIP:   "127.0.0.1",
			DevicePort: dev.udpPort,
			Password:   password,
		})
	}()
	deadline := time.Now().Add(5 * time.Second)
	for dev.hostPort == 0 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if dev.hostPort != 0 {
		go dev.dialTCP(false)
	}
	select {
	case err := <-errCh:
		return err
	case <-time.After(20 * time.Second):
		t.Fatal("Push timed out")
		return nil
	}
}

func TestPushLoopback(t *testing.T) {
	const size = 1024*4 + 777 // full chunks + partial final chunk
	img := pushTestImage(t, size)
	dev := startFakeDevice(t, "", int64(size))

	if err := pushAsync(t, dev, img, ""); err != nil {
		t.Fatalf("Push failed: %v", err)
	}
	if dev.gotSize != size {
		t.Errorf("device saw size %d, want %d", dev.gotSize, size)
	}
	if len(dev.gotMD5) != 32 {
		t.Errorf("device saw md5 %q, want 32 hex chars", dev.gotMD5)
	}
	if dev.gotChunks == 0 {
		t.Error("device received no data chunks")
	}
}

func TestPushAuthCorrectPassword(t *testing.T) {
	const size = 1500
	img := pushTestImage(t, size)
	dev := startFakeDevice(t, "hunter2", int64(size))

	if err := pushAsync(t, dev, img, "hunter2"); err != nil {
		t.Fatalf("Push with correct password failed: %v", err)
	}
	if dev.gotChunks == 0 {
		t.Error("device received no chunks after auth")
	}
}

func TestPushAuthWrongPassword(t *testing.T) {
	const size = 2048
	img := pushTestImage(t, size)
	dev := startFakeDevice(t, "hunter2", int64(size))

	err := Push(context.Background(), Options{
		ImagePath:  img,
		DeviceIP:   "127.0.0.1",
		DevicePort: dev.udpPort,
		Password:   "wrong-password",
	})
	if err == nil {
		t.Fatal("Push with wrong password should fail")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("expected auth failure, got: %v", err)
	}
}

func TestPushNoPasswordButRequired(t *testing.T) {
	img := pushTestImage(t, 1024)
	dev := startFakeDevice(t, "secret", int64(1024))

	err := Push(context.Background(), Options{
		ImagePath:  img,
		DeviceIP:   "127.0.0.1",
		DevicePort: dev.udpPort,
	})
	if err == nil {
		t.Fatal("Push without password against auth device should fail")
	}
	if !strings.Contains(err.Error(), "password") {
		t.Errorf("expected password hint, got: %v", err)
	}
}

func TestProbeUnreachable(t *testing.T) {
	if err := Probe("127.0.0.1", 1); err == nil {
		t.Error("Probe on closed port should fail")
	}
}

// ── mDNS discovery parsing ──────────────────────────────────────
// Regression test built from a verbatim captured ESP32 ArduinoOTA
// answer (companion-000000, port 3232 → 192.168.4.1), whose SRV target
// is a bare hostname — the A record does NOT repeat the service
// instance name, so IP attribution must follow the SRV target.
//
//   header: flags 8400, QD=0 AN=1 NS=0 AR=3
func TestParseMDNSArduinoOTAAnswer(t *testing.T) {
	// Captured 2026-09-13 from 192.168.4.1 answering a
	// _arduino._tcp.local PTR query (193 bytes).
	pkt := mustHex(t, "000084000000000100000003085f61726475696e6f045f746370056c6f63616c00000c000100001194001310636f6d70616e696f6e2d303030303030c00cc02b00210001000000780019000000000ca010636f6d70616e696f6e2d303030303030c01ac02b001000010000119400420e617574685f75706c6f61643d6e6f0d7373685f75706c6f61643d6e6f0c7463705f636865636b3d6e6f17626f6172643d646f697445535033326465766b69745631c05000010001000000780004c0a80401")
	records := map[string]*ServiceRecord{}
	parseMDNSResponses(pkt, records)
	rec, ok := records["companion-000000"]
	if !ok {
		t.Fatalf("instance record missing, got %v", records)
	}
	if rec.Port != 3232 {
		t.Errorf("port = %d, want 3232", rec.Port)
	}
	if rec.Host != "companion-000000.local" {
		t.Errorf("host = %q, want companion-000000.local", rec.Host)
	}
	if rec.IP != "192.168.4.1" {
		t.Errorf("IP = %q, want 192.168.4.1 (A record follows SRV target, not instance)", rec.IP)
	}
}

func mustHex(t *testing.T, s string) []byte {
	t.Helper()
	b := make([]byte, 0, len(s)/2)
	for i := 0; i+1 < len(s); i += 2 {
		hi := strings.IndexByte("0123456789abcdef", s[i])
		lo := strings.IndexByte("0123456789abcdef", s[i+1])
		if hi < 0 || lo < 0 {
			t.Fatalf("bad hex at %d", i)
		}
		b = append(b, byte(hi<<4|lo))
	}
	return b
}
