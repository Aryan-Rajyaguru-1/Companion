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
// invite, consumes exactly size bytes, ACKs each chunk with its length, and
// sends the final verdict.
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
		fmt.Fprintf(conn, "%d\n", n)
		if rerr != nil {
			return
		}
		got += int64(n)
		d.gotChunks++
	}
	if fail {
		conn.Write([]byte("ERROR flash failed\n"))
		return
	}
	conn.Write([]byte("OK\n"))
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
