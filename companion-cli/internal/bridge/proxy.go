package bridge

import (
	"fmt"
	"io"
	"net"
	"sync"
)

// LocalProxy exposes an authenticated bridge as a plain localhost TCP socket
// for tools that cannot speak the bridge's HMAC handshake. esptool
// (socket://) and avrdude (net:) connect here; the proxy authenticates to the
// real bridge and then pipes raw bytes in both directions.
//
// The listener binds 127.0.0.1 only. Each accepted connection performs a
// fresh challenge-response, because the firmware authenticates every TCP
// connection independently.
type LocalProxy struct {
	ln      net.Listener
	host    string
	port    int
	key     string
	onError func(error)

	closeOnce sync.Once
}

// StartLocalProxy starts a loopback proxy for a keyed bridge. The returned
// proxy must be closed by the caller. onError, when non-nil, receives
// authentication or upstream connection failures from proxied clients.
func StartLocalProxy(host string, port int, key string, onError func(error)) (*LocalProxy, error) {
	if key == "" {
		return nil, fmt.Errorf("a bridge key is required for the authenticated proxy")
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("starting bridge proxy listener: %w", err)
	}

	p := &LocalProxy{
		ln:      ln,
		host:    host,
		port:    port,
		key:     key,
		onError: onError,
	}
	go p.serve()
	return p, nil
}

// Addr returns the loopback host:port tools should connect to.
func (p *LocalProxy) Addr() string {
	return p.ln.Addr().String()
}

// Close stops accepting new proxied connections. Existing connections finish
// when either side closes.
func (p *LocalProxy) Close() error {
	var err error
	p.closeOnce.Do(func() {
		err = p.ln.Close()
	})
	return err
}

func (p *LocalProxy) serve() {
	for {
		local, err := p.ln.Accept()
		if err != nil {
			return // listener closed
		}
		go p.handle(local)
	}
}

func (p *LocalProxy) handle(local net.Conn) {
	defer local.Close()

	remote := New(p.host, p.port, p.key)
	if err := remote.Connect(); err != nil {
		if p.onError != nil {
			p.onError(err)
		}
		return
	}
	defer remote.Close()

	done := make(chan struct{}, 2)
	go func() {
		_, _ = io.Copy(remote, local)
		done <- struct{}{}
	}()
	go func() {
		_, _ = io.Copy(local, remote)
		done <- struct{}{}
	}()

	// Either direction ending closes both sides, which unblocks the peer copy.
	<-done
	local.Close()
	remote.Close()
	<-done
}
