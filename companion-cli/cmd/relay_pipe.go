package cmd

import (
	"io"
	"net"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

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
