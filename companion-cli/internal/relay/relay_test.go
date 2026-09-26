package relay

// End-to-end loopback test: a live hub over real WebSockets, with a
// simulated device (speaking the ArduinoOTA bare-ACK wire protocol) and an
// agent pushing a firmware image through PushDevice. Validates the whole
// pairing/forwarding/data pipeline without hardware.

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/gorilla/websocket"
)

// fakeRemoteDevice behaves like an ESP32 running the relay firmware: it
// registers, then during a push reads the header + chunks and replies with
// bare decimal ACKs and a final bare "OK" — no newlines anywhere.
type fakeRemoteDevice struct {
	id       string
	gotSize  int64
	gotMD5   string
	chunks   int
	firmware []byte
}

func dialDevice(t *testing.T, url, token, id, secret string) (*websocket.Conn, *fakeRemoteDevice) {
	t.Helper()
	ws, _, err := websocket.DefaultDialer.Dial(url+"/device?token="+token, nil)
	if err != nil {
		t.Fatalf("device dial: %v", err)
	}
	hello, _ := json.Marshal(map[string]any{
		"kind": KindDeviceHello, "id": id, "version": "1.0.3",
		"secret":   secret,
		"frame_kb": 8, // negotiated data-frame size, as the real firmware sends
	})
	if err := ws.WriteMessage(websocket.TextMessage, hello); err != nil {
		t.Fatalf("device hello: %v", err)
	}
	ws.SetReadDeadline(time.Now().Add(5 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		t.Fatalf("device welcome: %v", err)
	}
	var w map[string]any
	json.Unmarshal(raw, &w)
	if w["ok"] != true {
		t.Fatalf("device not welcomed: %v", w)
	}
	return ws, &fakeRemoteDevice{id: id}
}

// runDeviceLoop consumes push_start, then the header + data frames, ACKing
// bare counts and finishing with bare "OK" — mirroring the ESP32 Update
// loop. `fail` makes it reject mid-stream with device error text. When done
// is non-nil it is closed after the first completed push so the caller can
// synchronize (e.g. send agent-side push_done before the second push).
func runDeviceLoop(t *testing.T, ws *websocket.Conn, d *fakeRemoteDevice, fail bool, done chan<- struct{}) {
	t.Helper()
	ws.SetReadDeadline(time.Now().Add(15 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		return
	}
	var start struct {
		Kind string `json:"kind"`
		Size int64  `json:"size"`
		MD5  string `json:"md5"`
	}
	if err := json.Unmarshal(raw, &start); err != nil || start.Kind != KindPushStart {
		t.Errorf("device: expected push_start, got %s", raw)
		return
	}
	d.gotSize, d.gotMD5 = start.Size, start.MD5

	written := int64(0)
	firstDataFrame := true
	for written < d.gotSize {
		ws.SetReadDeadline(time.Now().Add(10 * time.Second))
		_, payload, err := ws.ReadMessage()
		if err != nil {
			return
		}
		// The agent's PushDevice prepends a "<size> <md5>\n" ASCII header on
		// the data pipe; strip it (the real firmware does the same).
		if firstDataFrame {
			firstDataFrame = false
			if idx := bytes.IndexByte(payload, '\n'); idx >= 0 && idx < 80 {
				payload = payload[idx+1:]
			}
		}
		n := int64(len(payload))
		if n == 0 {
			continue
		}
		if written+n > d.gotSize {
			n = d.gotSize - written
		}
		d.firmware = append(d.firmware, payload[:n]...)
		written += n
		d.chunks++
		if fail {
			ws.WriteMessage(websocket.BinaryMessage, []byte("ERROR flash failed"))
			return
		}
		// ACK the running byte total (bare decimal, no framing) — mirroring
		// the ESP32 Update loop.
		ws.WriteMessage(websocket.BinaryMessage, []byte(strconv.FormatInt(written, 10)))
	}
	sum := md5.Sum(d.firmware)
	if hex.EncodeToString(sum[:]) != d.gotMD5 {
		ws.WriteMessage(websocket.BinaryMessage, []byte("ERROR md5 mismatch"))
		return
	}
	ws.WriteMessage(websocket.BinaryMessage, []byte("OK"))
	// push_done (text control frame): explicit end-of-push signal so the hub
	// clears the busy pairing — the device stays connected and immediately
	// pushable again. Real firmware sends this right after its bare "OK".
	doneMsg, _ := json.Marshal(map[string]string{"kind": KindPushDone})
	ws.WriteMessage(websocket.TextMessage, doneMsg)
	if done != nil {
		d.chunks = 0 // fresh counters for the next push on this socket
		d.firmware = nil
		close(done)
	}
}

// wsNetConn adapts one side of a websocket into a net.Conn for PushDevice:
// Writes are binary frames; Reads return binary frame payloads.
//
// The pump feeds a channel (NOT an io.Pipe): the quiet-period timeout must
// not poison the stream — after a timeout the next reply must still arrive.
// (An earlier io.Pipe version closed the shared writer on timeout, killing
// the pump and losing every later ACK.)
type wsNetConn struct {
	ws         *websocket.Conn
	ch         chan []byte
	done       chan struct{}
	rdDeadline time.Time
}

// errWSTimeout fakes a net timeout error so relayReplyReader treats an
// enforced read deadline as a quiet period, not a fatal error.
type errWSTimeout struct{}

func (errWSTimeout) Error() string   { return "ws read timeout" }
func (errWSTimeout) Timeout() bool   { return true }
func (errWSTimeout) Temporary() bool { return true }

func newWSNetConn(ws *websocket.Conn) *wsNetConn {
	c := &wsNetConn{ws: ws, ch: make(chan []byte, 64), done: make(chan struct{})}
	go func() { // pump BINARY frames into the channel; swallow text/control
		for {
			mt, payload, err := ws.ReadMessage()
			if err != nil {
				return
			}
			if mt != websocket.BinaryMessage {
				continue // protocol frame — never firmware bytes
			}
			select {
			case c.ch <- payload:
			case <-c.done:
				return
			}
		}
	}()
	return c
}

func (c *wsNetConn) Read(b []byte) (int, error) {
	// Channel pump with deadline: wait for the next payload, a close, or
	// the reader's read deadline (PushDevice's quiet-period logic depends
	// on timeouts surfacing as net timeout errors).
	if c.rdDeadline.IsZero() {
		select {
		case p, ok := <-c.ch:
			if !ok {
				return 0, io.EOF
			}
			return copy(b, p), nil
		case <-c.done:
			return 0, io.EOF
		}
	}
	d := time.Until(c.rdDeadline)
	if d <= 0 {
		return 0, errWSTimeout{}
	}
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case p, ok := <-c.ch:
		if !ok {
			return 0, io.EOF
		}
		return copy(b, p), nil
	case <-c.done:
		return 0, io.EOF
	case <-timer.C:
		return 0, errWSTimeout{}
	}
}

func (c *wsNetConn) Write(b []byte) (int, error) {
	if err := c.ws.WriteMessage(websocket.BinaryMessage, b); err != nil {
		return 0, err
	}
	return len(b), nil
}
func (c *wsNetConn) Close() error {
	select {
	case <-c.done:
	default:
		close(c.done)
	}
	return c.ws.Close()
}
func (c *wsNetConn) LocalAddr() net.Addr                { return pipeAddr{} }
func (c *wsNetConn) RemoteAddr() net.Addr               { return pipeAddr{} }
func (c *wsNetConn) SetDeadline(t time.Time) error      { c.rdDeadline = t; return nil }
func (c *wsNetConn) SetReadDeadline(t time.Time) error  { c.rdDeadline = t; return nil }
func (c *wsNetConn) SetWriteDeadline(t time.Time) error { return nil }

type pipeAddr struct{}

func (pipeAddr) Network() string { return "pipe" }
func (pipeAddr) String() string  { return "relay-data" }

func md5sum(b []byte) string {
	s := md5.Sum(b)
	return hex.EncodeToString(s[:])
}

// agentPush drives the agent side: push_req → push_ack → the REAL
// PushDevice() over the websocket data pipe. A FRESH agent socket is used per
// push: the data-phase pump owns ReadMessage for the socket's lifetime, so a
// second push on the same socket would have two competing readers.
func agentPush(t *testing.T, wsURL, token, devID, devSecret string, img []byte) error {
	t.Helper()
	ws, _, err := websocket.DefaultDialer.Dial(wsURL+"/agent?token="+token, nil)
	if err != nil {
		t.Fatalf("agent dial: %v", err)
	}
	defer ws.Close()
	req, _ := json.Marshal(map[string]any{
		"kind": KindPushReq, "device": devID, "secret": devSecret,
		"size": len(img), "md5": md5sum(img),
	})
	if err := ws.WriteMessage(websocket.TextMessage, req); err != nil {
		t.Fatalf("push_req: %v", err)
	}
	ws.SetReadDeadline(time.Now().Add(5 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		t.Fatalf("push_ack read: %v", err)
	}
	var ack struct {
		Kind  string `json:"kind"`
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &ack); err != nil {
		t.Fatalf("push_ack parse: %v (%s)", err, raw)
	}
	// Offline/unknown device is a deliberate hub-level rejection: the hub
	// answers push_result{ok:false} instead of push_ack, and no data socket
	// is ever opened. Surface it as a clean Go error, not a test failure.
	if ack.Kind == KindPushResult && !ack.OK {
		return fmt.Errorf("hub rejected push: %s", ack.Error)
	}
	if ack.Kind != KindPushAck || !ack.OK {
		t.Fatalf("expected push_ack ok, got %s", raw)
	}
	// Clear the push_ack deadline on the RAW socket, wrap it, and run the
	// data phase — mirroring the real CLI: parse the negotiated frame size
	// from push_ack and stream with it (8 KiB advertised, 1024 legacy).
	ws.SetReadDeadline(time.Time{})
	defer ws.Close()
	frameKB := FrameKBFromAck(raw)
	return PushDeviceStream(context.Background(), func() *wsNetConn {
		c := newWSNetConn(ws) // …then spawn the pump with a clean slate
		c.rdDeadline = time.Time{}
		return c
	}(), bytes.NewReader(img), int64(len(img)), &ota.StreamOptions{ChunkBytes: frameKB})
}

// TestFrameKBFromAck covers the negotiation parser: advertised values pass
// through clamped to [1,8] KiB, and anything absent/garbage/zero keeps the
// legacy 1024-byte frame (ChunkBytes 0 → PushStream's default).
func TestFrameKBFromAck(t *testing.T) {
	cases := []struct {
		name string
		json string
		want int
	}{
		{"advertised 8 KiB", `{"ok":true,"device":"d","frame_kb":8}`, 8192},
		{"advertised 1 KiB", `{"ok":true,"frame_kb":1}`, 1024},
		{"over-ceiling clamped", `{"ok":true,"frame_kb":64}`, 8192},
		{"absent keeps legacy", `{"ok":true,"device":"d"}`, 0},
		{"zero keeps legacy", `{"ok":true,"frame_kb":0}`, 0},
		{"garbage keeps legacy", `not json`, 0},
	}
	for _, tc := range cases {
		if got := FrameKBFromAck([]byte(tc.json)); got != tc.want {
			t.Errorf("%s: FrameKBFromAck = %d, want %d", tc.name, got, tc.want)
		}
	}
}

func TestRelayEndToEnd(t *testing.T) {
	hub := NewHub(Config{DevicesToken: "dev-tok", AgentsToken: "agent-tok"})
	srv := httptest.NewServer(hub.Handler())
	defer srv.Close()
	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http")

	// Two devices: one flashes successfully, one fails mid-push. The success
	// device provisions a per-device secret (boards without one keep working:
	// secret checks only apply when the device presented one at hello).
	devWS, dev := dialDevice(t, wsURL, "dev-tok", "dev-alpha", "s3cr3t-alpha")
	defer devWS.Close()
	go runDeviceLoop(t, devWS, dev, false, nil)

	failWS, failDev := dialDevice(t, wsURL, "dev-tok", "dev-beta", "")
	defer failWS.Close()
	go runDeviceLoop(t, failWS, failDev, true, nil)

	deadline := time.Now().Add(5 * time.Second)
	for len(hub.DeviceIDs()) < 2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if ids := hub.DeviceIDs(); len(ids) != 2 {
		t.Fatalf("expected 2 registered devices, got %v", ids)
	}

	// Authed /health lists both devices with their busy flags.
	req, _ := http.NewRequest("GET", srv.URL+"/health?token=agent-tok", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("health: %v", err)
	}
	var health struct {
		OK      bool         `json:"ok"`
		Devices []DeviceInfo `json:"devices"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		t.Fatalf("health parse: %v", err)
	}
	resp.Body.Close()
	if !health.OK || len(health.Devices) != 2 {
		t.Fatalf("expected authed health with 2 devices, got %+v", health)
	}
	// Unauthenticated callers get liveness only — no device inventory.
	resp2, err := http.Get(srv.URL + "/health")
	if err != nil {
		t.Fatalf("unauth health: %v", err)
	}
	var bare map[string]any
	if err := json.NewDecoder(resp2.Body).Decode(&bare); err != nil {
		t.Fatalf("unauth health parse: %v", err)
	}
	resp2.Body.Close()
	if _, hasDevices := bare["devices"]; hasDevices {
		t.Fatalf("unauthenticated /health must not list devices: %v", bare)
	}

	img := make([]byte, 64*1024) // 64 chunks at 1 KiB
	for i := range img {
		img[i] = byte(i*7 + i>>8)
	}

	// 1. Success path: real PushDevice over the relay (with device secret).
	if err := agentPush(t, wsURL, "agent-tok", "dev-alpha", "s3cr3t-alpha", img); err != nil {
		t.Fatalf("PushDevice success path: %v", err)
	}
	if !bytes.Equal(dev.firmware, img) {
		t.Fatalf("device firmware mismatch: got %d bytes, want %d", len(dev.firmware), len(img))
	}
	// The device advertises frame_kb=8 at hello and the hub relays it in
	// push_ack, so the agent streamed 8 KiB frames: 64 KiB / 8 KiB = 8
	// frames, not the 64 the legacy 1 KiB frame size would produce.
	if dev.chunks != 8 {
		t.Errorf("negotiated frame size not used: device saw %d frames, want 8 (8 KiB each)", dev.chunks)
	}
	t.Logf("✓ success path: %d bytes in %d frames (negotiated 8 KiB), md5 verified by device", len(img), dev.chunks)

	// 1b. Secret gate: wrong secret is rejected without touching the device.
	if err := agentPush(t, wsURL, "agent-tok", "dev-alpha", "wrong-secret", img); err == nil {
		t.Fatal("expected wrong-secret push to be rejected, got nil")
	} else if !strings.Contains(err.Error(), "secret") {
		t.Fatalf("expected secret rejection, got: %v", err)
	}
	t.Logf("✓ per-device secret enforced")

	// 2. Failure path: device rejects mid-stream → error surfaces.
	err = agentPush(t, wsURL, "agent-tok", "dev-beta", "", img)
	if err == nil {
		t.Fatal("expected failure-path push to error, got nil")
	}
	if !strings.Contains(err.Error(), "flash failed") {
		t.Fatalf("expected device error text in failure, got: %v", err)
	}
	t.Logf("✓ failure path surfaced correctly: %v", err)

	// 3. Offline path: unknown device id fails cleanly.
	err = agentPush(t, wsURL, "agent-tok", "dev-ghost", "", img)
	if err == nil {
		t.Fatal("expected offline-path push to error, got nil")
	}
	t.Logf("✓ offline path surfaced correctly: %v", err)

	// 4. push_done clears the pairing: after a completed push the same device
	// is immediately pushable again without a reconnect. The CLI-side agent
	// sends push_done right after PushDevice sees "OK" (mirroring what the
	// real `relay push` command does), so simulate that here too.
	devWS2, dev2 := dialDevice(t, wsURL, "dev-tok", "dev-alpha2", "")
	defer devWS2.Close()
	firstDone := make(chan struct{})
	go func() {
		runDeviceLoop(t, devWS2, dev2, false, firstDone)
		runDeviceLoop(t, devWS2, dev2, false, nil)
	}()
	time.Sleep(200 * time.Millisecond)
	small := img[:4096]
	sendAgentPushDone := func() {
		ws, _, err := websocket.DefaultDialer.Dial(wsURL+"/agent?token=agent-tok", nil)
		if err != nil {
			t.Fatalf("push_done agent dial: %v", err)
		}
		defer ws.Close()
		done, _ := json.Marshal(map[string]string{"kind": KindPushDone})
		ws.SetWriteDeadline(time.Now().Add(5 * time.Second))
		if err := ws.WriteMessage(websocket.TextMessage, done); err != nil {
			t.Fatalf("push_done write: %v", err)
		}
	}
	if err := agentPush(t, wsURL, "agent-tok", "dev-alpha2", "", small); err != nil {
		t.Fatalf("first push for push_done check: %v", err)
	}
	// The device's own push_done already cleared the hub pairing; the
	// agent-side push_done (what real `relay push` sends) is idempotent.
	// Wait for the device loop to finish the first push before asserting.
	select {
	case <-firstDone:
	case <-time.After(10 * time.Second):
		t.Fatal("device did not finish first push")
	}
	sendAgentPushDone()
	if err := agentPush(t, wsURL, "agent-tok", "dev-alpha2", "", small); err != nil {
		t.Fatalf("second push after push_done should succeed, got: %v", err)
	}
	t.Logf("✓ push_done clears pairing: same device pushable twice in a row")
}
