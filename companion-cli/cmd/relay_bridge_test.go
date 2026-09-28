package cmd

import (
	"context"
	"encoding/json"
	"net"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/companion-ide/companion-cli/internal/relay"
	"github.com/gorilla/websocket"
)

// startEchoBridgeDevice stands in for an esp32_bridge running in
// RELAY_MODE_REMOTE: it registers with a secret and echoes every binary frame
// straight back, which is what the UART path does with target bytes.
func startEchoBridgeDevice(t *testing.T, wsURL, id, secret string) {
	t.Helper()
	ws, _, err := websocket.DefaultDialer.Dial(wsURL+"/device?token=dev-tok", nil)
	if err != nil {
		t.Fatalf("bridge device dial: %v", err)
	}
	t.Cleanup(func() { ws.Close() })
	hello, _ := json.Marshal(map[string]any{
		"kind": relay.KindDeviceHello, "id": id, "version": "test", "secret": secret,
	})
	if err := ws.WriteMessage(websocket.TextMessage, hello); err != nil {
		t.Fatalf("bridge device hello: %v", err)
	}
	ws.SetReadDeadline(time.Now().Add(5 * time.Second))
	if _, raw, err := ws.ReadMessage(); err != nil {
		t.Fatalf("bridge device welcome: %v", err)
	} else if !strings.Contains(string(raw), `"ok":true`) {
		t.Fatalf("bridge device refused: %s", raw)
	}
	go func() {
		for {
			mt, payload, err := ws.ReadMessage()
			if err != nil {
				return
			}
			if mt != websocket.BinaryMessage {
				continue // control frames (push_start, pong) are not target bytes
			}
			_ = ws.WriteMessage(websocket.BinaryMessage, payload)
		}
	}()
}

// Two clients in a row must BOTH be served. The pairing used to be a
// long-lived socket whose reader goroutine stayed blocked after the first
// client hung up, so the second client's frames could be swallowed by that
// orphan — one pairing per client is what makes the second session work.
func TestServeRelayBridgeClientsServesSequentialClients(t *testing.T) {
	hub := relay.NewHub(relay.Config{DevicesToken: "dev-tok", AgentsToken: "agent-tok"})
	srv := httptest.NewServer(hub.Handler())
	defer srv.Close()
	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http")

	startEchoBridgeDevice(t, wsURL, "bridge-01", "bridge-secret")

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go serveRelayBridgeClients(ctx, ln, wsURL, "agent-tok", "bridge-01", "bridge-secret", nil)

	for i := 0; i < 3; i++ {
		conn, err := net.Dial("tcp", ln.Addr().String())
		if err != nil {
			t.Fatalf("client %d dial: %v", i, err)
		}
		payload := []byte{0xEF, 0xBE, byte(i + 1), 0x00, 0xFF}
		if _, err := conn.Write(payload); err != nil {
			t.Fatalf("client %d write: %v", i, err)
		}
		conn.SetReadDeadline(time.Now().Add(5 * time.Second))
		buf := make([]byte, len(payload))
		if _, err := readFull(conn, buf); err != nil {
			t.Fatalf("client %d echo: %v", i, err)
		}
		for j := range payload {
			if buf[j] != payload[j] {
				t.Fatalf("client %d: echo mismatch: got %v want %v", i, buf, payload)
			}
		}
		conn.Close()
	}
}

// A wrong device secret must not yield a working local socket: the pairing is
// where the bridge's identity is checked, so a failed pairing has to fail the
// client rather than leave a listener that accepts and then does nothing.
func TestServeRelayBridgeClientsRejectsWrongSecret(t *testing.T) {
	hub := relay.NewHub(relay.Config{DevicesToken: "dev-tok", AgentsToken: "agent-tok"})
	srv := httptest.NewServer(hub.Handler())
	defer srv.Close()
	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http")

	startEchoBridgeDevice(t, wsURL, "bridge-02", "real-secret")

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errs := make(chan error, 8)
	go serveRelayBridgeClients(ctx, ln, wsURL, "agent-tok", "bridge-02", "wrong-secret",
		func(err error) {
			select {
			case errs <- err:
			default:
			}
		})

	conn, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer conn.Close()
	conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	if _, err := conn.Write([]byte{0x01}); err == nil {
		buf := make([]byte, 1)
		if _, err := readFull(conn, buf); err == nil {
			t.Fatal("echoed a byte despite a rejected secret — the pipe must not exist")
		}
	}
	select {
	case perr := <-errs:
		if !strings.Contains(perr.Error(), "secret") {
			t.Fatalf("expected a secret rejection, got: %v", perr)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("expected the pairing failure to be reported")
	}
}

func readFull(conn net.Conn, buf []byte) (int, error) {
	read := 0
	for read < len(buf) {
		n, err := conn.Read(buf[read:])
		read += n
		if err != nil {
			return read, err
		}
	}
	return read, nil
}
