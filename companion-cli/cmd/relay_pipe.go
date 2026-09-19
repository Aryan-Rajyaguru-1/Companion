package cmd

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
	"net/url"
	"os"
	"time"

	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/relay"
	"github.com/gorilla/websocket"
)

// RelayPushFunc builds a fleet.PushFunc that pushes imagePath to one registry
// device through the relay hub (remote OTA). It mirrors `relay push`: dial
// the agent port, send push_req carrying the device's stored Secret, stream
// the image with PushDevice, then send push_done so the hub clears the
// pairing. hubBase is the --hub base URL (ws:// or wss://); token is the
// agent token (COMPANION_RELAY_AGENTS_TOKEN fallback handled by the caller).
func RelayPushFunc(hubBase, token, imagePath string) fleet.PushFunc {
	return func(ctx context.Context, d fleet.Device) error {
		return relayPushOne(ctx, hubBase, token, d, imagePath)
	}
}

// relayPushOne is the per-device remote push used by both RelayPushFunc
// (fleet) and, in future, the `upload --ota-mode remote` path. It shares the
// exact wire steps of `relay push` so behaviour stays identical.
func relayPushOne(ctx context.Context, hubBase, token string, d fleet.Device, imagePath string) error {
	if token == "" {
		return fmt.Errorf("agent token required: --token or COMPANION_RELAY_AGENTS_TOKEN")
	}
	img, err := os.ReadFile(imagePath)
	if err != nil {
		return fmt.Errorf("read image: %w", err)
	}
	sum := md5.Sum(img)
	md5hex := hex.EncodeToString(sum[:])

	u, err := url.Parse(hubBase)
	if err != nil {
		return fmt.Errorf("bad hub URL: %w", err)
	}
	u.Path = "/agent"
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()

	ws, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return fmt.Errorf("dial hub agent port: %w", err)
	}
	defer ws.Close()

	req, _ := json.Marshal(map[string]any{
		"kind": relay.KindPushReq, "device": d.Key(),
		"secret": d.Secret,
		"size":   len(img), "md5": md5hex,
	})
	if err := ws.WriteMessage(websocket.TextMessage, req); err != nil {
		return fmt.Errorf("push_req: %w", err)
	}
	ws.SetReadDeadline(time.Now().Add(10 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		return fmt.Errorf("push_ack: %w", err)
	}
	var ack struct {
		Kind  string `json:"kind"`
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &ack); err != nil {
		return fmt.Errorf("push_ack parse: %w", err)
	}
	if ack.Kind == relay.KindPushResult && !ack.OK {
		return fmt.Errorf("hub rejected push: %s", ack.Error)
	}
	if ack.Kind != relay.KindPushAck || !ack.OK {
		return fmt.Errorf("unexpected hub reply: %s", raw)
	}
	ws.SetReadDeadline(time.Time{})
	pipe := newAgentPipe(ws)
	pctx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()
	if err := relay.PushDevice(pctx, pipe, bytes.NewReader(img), int64(len(img))); err != nil {
		return fmt.Errorf("push to %s failed: %w", d.Key(), err)
	}
	doneMsg, _ := json.Marshal(map[string]string{"kind": relay.KindPushDone})
	_ = ws.WriteMessage(websocket.TextMessage, doneMsg)
	return nil
}

// relayHTTPServer is a thin net/http wrapper so cmd stays stdlib-only
// (the relay package itself exposes only the Handler).
type relayHTTPServer struct {
	addr string
	h    http.Handler
}

func (s *relayHTTPServer) serve() error {
	srv := &http.Server{Addr: s.addr, Handler: s.h}
	return srv.ListenAndServe()
}

// agentPipe adapts the agent websocket into a net.Conn for PushDevice.
// Binary frames carry the data stream; text/protocol frames are swallowed
// (same demux the loopback test validates).
type agentPipe struct {
	ws         *websocket.Conn
	ch         chan []byte
	done       chan struct{}
	rdDeadline time.Time
}

type wsTimeoutErr struct{}

func (wsTimeoutErr) Error() string   { return "ws read timeout" }
func (wsTimeoutErr) Timeout() bool   { return true }
func (wsTimeoutErr) Temporary() bool { return true }

func newAgentPipe(ws *websocket.Conn) *agentPipe {
	p := &agentPipe{ws: ws, ch: make(chan []byte, 64), done: make(chan struct{})}
	go func() {
		for {
			mt, payload, err := ws.ReadMessage()
			if err != nil {
				return
			}
			if mt != websocket.BinaryMessage {
				continue
			}
			select {
			case p.ch <- payload:
			case <-p.done:
				return
			}
		}
	}()
	return p
}

func (p *agentPipe) Read(b []byte) (int, error) {
	if p.rdDeadline.IsZero() {
		select {
		case buf, ok := <-p.ch:
			if !ok {
				return 0, io.EOF
			}
			return copy(b, buf), nil
		case <-p.done:
			return 0, io.EOF
		}
	}
	d := time.Until(p.rdDeadline)
	if d <= 0 {
		return 0, wsTimeoutErr{}
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case buf := <-p.ch:
		return copy(b, buf), nil
	case <-p.done:
		return 0, io.EOF
	case <-t.C:
		return 0, wsTimeoutErr{}
	}
}

func (p *agentPipe) Write(b []byte) (int, error) {
	if err := p.ws.WriteMessage(websocket.BinaryMessage, b); err != nil {
		return 0, err
	}
	return len(b), nil
}

func (p *agentPipe) Close() error {
	select {
	case <-p.done:
	default:
		close(p.done)
	}
	return p.ws.Close()
}

func (p *agentPipe) LocalAddr() net.Addr                { return agentPipeAddr{} }
func (p *agentPipe) RemoteAddr() net.Addr               { return agentPipeAddr{} }
func (p *agentPipe) SetDeadline(t time.Time) error      { p.rdDeadline = t; return nil }
func (p *agentPipe) SetReadDeadline(t time.Time) error  { p.rdDeadline = t; return nil }
func (p *agentPipe) SetWriteDeadline(t time.Time) error { return nil }

type agentPipeAddr struct{}

func (agentPipeAddr) Network() string { return "relay" }
func (agentPipeAddr) String() string  { return "relay-agent-pipe" }
