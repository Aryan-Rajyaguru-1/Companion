package bridge

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"errors"
	"io"
	"net"
	"testing"
	"time"
)

// startFakeBridge runs one handler against one accepted TCP connection. It is
// enough for the client tests; the proxy test opens exactly one upstream.
func startFakeBridge(t *testing.T, handle func(net.Conn)) (string, int) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(func() { _ = ln.Close() })
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		handle(conn)
	}()
	addr := ln.Addr().(*net.TCPAddr)
	return "127.0.0.1", addr.Port
}

func readExact(t *testing.T, conn net.Conn, n int) ([]byte, bool) {
	t.Helper()
	_ = conn.SetReadDeadline(time.Now().Add(3 * time.Second))
	buf := make([]byte, n)
	if _, err := io.ReadFull(conn, buf); err != nil {
		t.Errorf("read %d bytes: %v", n, err)
		return nil, false
	}
	return buf, true
}

// serveChallenge sends a challenge and validates the client's HMAC against
// expectedKey, replying AUTH_OK or AUTH_FAIL. It asserts that the client's
// first frame is AUTH_BEGIN, which is the ordering the firmware depends on.
func serveChallenge(t *testing.T, conn net.Conn, expectedKey string, nonce []byte, expectMatch bool) bool {
	t.Helper()
	first, ok := readExact(t, conn, 3)
	if !ok {
		return false
	}
	want := []byte{ctrlA, ctrlB, CmdAuthBegin}
	if !bytes.Equal(first, want) {
		t.Errorf("first frame = % x, want auth begin % x", first, want)
		return false
	}
	if _, err := conn.Write(append([]byte{ctrlA, ctrlB, CmdAuthChallenge}, nonce...)); err != nil {
		t.Errorf("write challenge: %v", err)
		return false
	}

	response, ok := readExact(t, conn, 3+authNonceLen)
	if !ok {
		return false
	}
	if !bytes.Equal(response[:3], []byte{ctrlA, ctrlB, CmdAuthResponse}) {
		t.Errorf("response frame = % x, want auth response", response[:3])
		return false
	}
	mac := hmac.New(sha256.New, []byte(expectedKey))
	mac.Write(nonce)
	if !hmac.Equal(response[3:], mac.Sum(nil)) {
		if expectMatch {
			t.Errorf("client HMAC does not match expected key")
		}
		_, _ = conn.Write([]byte{ctrlA, ctrlB, CmdAuthFail})
		return false
	}
	if _, err := conn.Write([]byte{ctrlA, ctrlB, CmdAuthOK}); err != nil {
		t.Errorf("write auth ok: %v", err)
		return false
	}
	return true
}

func TestConnectAuthenticatesAndQueries(t *testing.T) {
	const key = "correct horse battery staple"
	nonce := bytes.Repeat([]byte{0x42}, authNonceLen)

	host, port := startFakeBridge(t, func(conn net.Conn) {
		if !serveChallenge(t, conn, key, nonce, true) {
			return
		}
		query, ok := readExact(t, conn, 3)
		if !ok {
			return
		}
		if !bytes.Equal(query, []byte{ctrlA, ctrlB, CmdQuery}) {
			t.Errorf("query frame = % x", query)
			return
		}
		_, _ = conn.Write([]byte("Companion Bridge v1\n"))
	})

	c := New(host, port, key)
	if err := c.Connect(); err != nil {
		t.Fatalf("Connect: %v", err)
	}
	defer c.Close()

	info, err := c.Query()
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if info != "Companion Bridge v1" {
		t.Fatalf("Query = %q", info)
	}
}

func TestNoAuthConnectSkipsProbe(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		frame, ok := readExact(t, conn, 7)
		if !ok {
			return
		}
		if !bytes.Equal(frame[:3], []byte{ctrlA, ctrlB, CmdSetBaud}) {
			t.Errorf("first frame = % x, want SET_BAUD with no auth probe", frame[:3])
			return
		}
	})

	c := NewNoAuth(host, port)
	if err := c.Connect(); err != nil {
		t.Fatalf("Connect: %v", err)
	}
	defer c.Close()
	if err := c.SetBaud(115200); err != nil {
		t.Fatalf("SetBaud: %v", err)
	}
}

func TestConnectWrongKeyIsRejected(t *testing.T) {
	nonce := bytes.Repeat([]byte{0x11}, authNonceLen)
	host, port := startFakeBridge(t, func(conn net.Conn) {
		serveChallenge(t, conn, "the-right-key", nonce, false)
	})

	c := New(host, port, "the-wrong-key")
	if err := c.Connect(); !errors.Is(err, ErrAuthRejected) {
		t.Fatalf("Connect = %v, want ErrAuthRejected", err)
	}
}

func TestConnectWithoutKeyIsRejected(t *testing.T) {
	nonce := bytes.Repeat([]byte{0x22}, authNonceLen)
	host, port := startFakeBridge(t, func(conn net.Conn) {
		hdr, ok := readExact(t, conn, 3)
		if !ok {
			return
		}
		if !bytes.Equal(hdr, []byte{ctrlA, ctrlB, CmdAuthBegin}) {
			t.Errorf("first frame = % x", hdr)
			return
		}
		_, _ = conn.Write(append([]byte{ctrlA, ctrlB, CmdAuthChallenge}, nonce...))
	})

	c := New(host, port, "")
	if err := c.Connect(); !errors.Is(err, ErrAuthKeyRequired) {
		t.Fatalf("Connect = %v, want ErrAuthKeyRequired", err)
	}
}

func TestLegacyFirmwareWithoutKeyFallsBack(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		if _, ok := readExact(t, conn, 3); !ok { // consume AUTH_BEGIN probe
			return
		}
		// Old firmware ignores the probe. Answer the later query.
		query, ok := readExact(t, conn, 3)
		if !ok {
			return
		}
		if !bytes.Equal(query, []byte{ctrlA, ctrlB, CmdQuery}) {
			t.Errorf("query after fallback = % x", query)
			return
		}
		_, _ = conn.Write([]byte("legacy bridge\n"))
	})

	c := New(host, port, "")
	if err := c.Connect(); err != nil {
		t.Fatalf("Connect: %v", err)
	}
	defer c.Close()

	info, err := c.Query()
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if info != "legacy bridge" {
		t.Fatalf("Query = %q", info)
	}
}

func TestLegacyFirmwareDoesNotFallbackWhenConnectionCloses(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		// Consume the probe, then close. A closed socket is not the same as
		// legacy firmware timing out because it ignored the probe.
		_, _ = readExact(t, conn, 3)
	})

	c := New(host, port, "")
	if err := c.Connect(); err == nil {
		t.Fatal("Connect succeeded after the bridge closed during the auth probe")
	}
}

func TestLegacyFirmwareWithKeyFailsClosed(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		_, _ = readExact(t, conn, 3) // AUTH_BEGIN; old firmware says nothing
		time.Sleep(250 * time.Millisecond)
	})

	c := New(host, port, "a-configured-key")
	c.authProbe = 100 * time.Millisecond
	if err := c.Connect(); !errors.Is(err, ErrAuthUnsupported) {
		t.Fatalf("Connect = %v, want ErrAuthUnsupported", err)
	}
}

func TestLegacyUARTPreservedDuringProbe(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		if _, ok := readExact(t, conn, 3); !ok { // AUTH_BEGIN
			return
		}
		// Legacy target output that happens to arrive while we probe.
		_, _ = conn.Write([]byte("hi\n"))
	})

	c := New(host, port, "")
	if err := c.Connect(); err != nil {
		t.Fatalf("Connect: %v", err)
	}
	defer c.Close()

	buf := make([]byte, 3)
	if _, err := io.ReadFull(c, buf); err != nil {
		t.Fatalf("Read pending UART bytes: %v", err)
	}
	if string(buf) != "hi\n" {
		t.Fatalf("pending UART = %q", string(buf))
	}
}

// A legacy bridge can forward target boot output while the client probes for
// auth support. That output is not a status reply: Query must still send
// CMD_QUERY, and must not prefix the pending UART bytes to the status.
func TestQueryDoesNotMixPendingUARTIntoStatus(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		if _, ok := readExact(t, conn, 3); !ok { // AUTH_BEGIN
			return
		}
		if _, err := conn.Write([]byte("hi\n")); err != nil { // exactly the probe length
			return
		}
		query, ok := readExact(t, conn, 3)
		if !ok {
			return
		}
		if !bytes.Equal(query, []byte{ctrlA, ctrlB, CmdQuery}) {
			t.Errorf("query frame = % x", query)
			return
		}
		_, _ = conn.Write([]byte("legacy bridge\r\n"))
	})

	c := New(host, port, "")
	if err := c.Connect(); err != nil {
		t.Fatalf("Connect: %v", err)
	}
	defer c.Close()

	info, err := c.Query()
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if info != "legacy bridge" {
		t.Fatalf("Query = %q, want the status line without boot output", info)
	}

	// The target bytes stay queued for the monitor path.
	buf := make([]byte, 3)
	if _, err := io.ReadFull(c, buf); err != nil {
		t.Fatalf("Read pending UART bytes: %v", err)
	}
	if string(buf) != "hi\n" {
		t.Fatalf("pending UART = %q", string(buf))
	}
}

func TestMonitorDeliversPendingProbeBytes(t *testing.T) {
	host, port := startFakeBridge(t, func(conn net.Conn) {
		if _, ok := readExact(t, conn, 3); !ok { // AUTH_BEGIN
			return
		}
		if _, err := conn.Write([]byte("hi\n")); err != nil {
			return
		}
		if _, ok := readExact(t, conn, 7); !ok { // SET_BAUD frame
			return
		}
		_, _ = conn.Write([]byte("there\n"))
	})

	var got bytes.Buffer
	done := make(chan error, 1)
	go func() {
		done <- Monitor(MonitorConfig{
			Host: host,
			Port: port,
			Baud: 115200,
		}, make(chan string), func(b []byte) { got.Write(b) })
	}()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Monitor: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Monitor did not stop after the bridge closed")
	}
	if got.String() != "hi\nthere\n" {
		t.Fatalf("monitor output = %q", got.String())
	}
}

func TestLocalProxyAuthenticatesAndPipes(t *testing.T) {
	const key = "proxy-test-key"
	nonce := bytes.Repeat([]byte{0x33}, authNonceLen)

	host, port := startFakeBridge(t, func(conn net.Conn) {
		if !serveChallenge(t, conn, key, nonce, true) {
			return
		}
		buf := make([]byte, 1024)
		for {
			n, err := conn.Read(buf)
			if n > 0 {
				if _, werr := conn.Write(buf[:n]); werr != nil {
					return
				}
			}
			if err != nil {
				return
			}
		}
	})

	proxy, err := StartLocalProxy(host, port, key, func(err error) {
		t.Errorf("proxy error: %v", err)
	})
	if err != nil {
		t.Fatalf("StartLocalProxy: %v", err)
	}
	defer proxy.Close()

	local, err := net.Dial("tcp", proxy.Addr())
	if err != nil {
		t.Fatalf("dial proxy: %v", err)
	}
	defer local.Close()

	payload := []byte("raw-uart-bytes")
	if _, err := local.Write(payload); err != nil {
		t.Fatalf("write proxy: %v", err)
	}
	_ = local.SetReadDeadline(time.Now().Add(3 * time.Second))
	got := make([]byte, len(payload))
	if _, err := io.ReadFull(local, got); err != nil {
		t.Fatalf("read proxy: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Fatalf("proxy echoed %q, want %q", got, payload)
	}
}

func TestLocalProxyRequiresKey(t *testing.T) {
	if _, err := StartLocalProxy("127.0.0.1", 1, "", nil); err == nil {
		t.Fatal("StartLocalProxy accepted an empty key")
	}
}

func TestLocalProxyReportsAuthenticationFailure(t *testing.T) {
	nonce := bytes.Repeat([]byte{0x44}, authNonceLen)
	host, port := startFakeBridge(t, func(conn net.Conn) {
		serveChallenge(t, conn, "the-right-key", nonce, false)
	})

	failures := make(chan error, 1)
	proxy, err := StartLocalProxy(host, port, "the-wrong-key", func(err error) {
		failures <- err
	})
	if err != nil {
		t.Fatalf("StartLocalProxy: %v", err)
	}
	defer proxy.Close()

	local, err := net.Dial("tcp", proxy.Addr())
	if err != nil {
		t.Fatalf("dial proxy: %v", err)
	}
	defer local.Close()

	select {
	case err := <-failures:
		if !errors.Is(err, ErrAuthRejected) {
			t.Fatalf("proxy failure = %v, want ErrAuthRejected", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("proxy did not report the authentication failure")
	}
}
