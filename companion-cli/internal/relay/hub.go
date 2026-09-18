package relay

import (
	"encoding/json"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Config holds hub server settings.
type Config struct {
	DevicesToken string        // shared token devices must present ("*" disables auth)
	AgentsToken  string        // shared token agents must present ("*" disables auth)
	ReadTimeout  time.Duration // per-control-frame deadline (0 → 30s)
}

// Hub is the relay server: it holds device and agent connections and pairs
// pushes between them. Devices and agents never see each other's sockets;
// the hub forwards push data between the paired pair.
type Hub struct {
	cfg Config

	mu      sync.Mutex
	devices map[string]*deviceConn // by device id
	agents  map[*agentConn]struct{}
}

// NewHub builds a Hub with the given config.
func NewHub(cfg Config) *Hub {
	if cfg.ReadTimeout <= 0 {
		cfg.ReadTimeout = 30 * time.Second
	}
	return &Hub{
		cfg:     cfg,
		devices: make(map[string]*deviceConn),
		agents:  make(map[*agentConn]struct{}),
	}
}

// conn is the shared websocket plumbing for both roles. Writes are
// serialized per connection; reads belong to each role's own loop (which
// handles push-state forwarding of binary frames).
type conn struct {
	ws *websocket.Conn
	wr sync.Mutex
}

func (c *conn) send(v any) error {
	c.wr.Lock()
	defer c.wr.Unlock()
	c.ws.SetWriteDeadline(time.Now().Add(10 * time.Second))
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return c.ws.WriteMessage(websocket.TextMessage, b)
}

func (c *conn) sendBinary(p []byte) error {
	c.wr.Lock()
	defer c.wr.Unlock()
	c.ws.SetWriteDeadline(time.Now().Add(30 * time.Second))
	return c.ws.WriteMessage(websocket.BinaryMessage, p)
}

// authed checks a presented token against the configured role token.
// A token of "*" in config disables auth for that role (dev only).
func (h *Hub) authed(presented, configured string) bool {
	if configured == "*" {
		return true
	}
	if presented == "" || configured == "" {
		return false
	}
	if len(presented) != len(configured) {
		return false
	}
	var v byte
	for i := 0; i < len(presented); i++ {
		v |= presented[i] ^ configured[i]
	}
	return v == 0
}

// deviceConn is one registered device link.
type deviceConn struct {
	conn
	id      string
	token   string
	busy    bool
	agent   *agentConn // set during an active push
	closed  chan struct{}
	once    sync.Once
	version string
}

func (d *deviceConn) close() {
	d.once.Do(func() { close(d.closed); d.ws.Close() })
}

// agentConn is one push-client (IDE/CLI) link.
type agentConn struct {
	conn
	name   string
	device *deviceConn // set during an active push
	closed chan struct{}
	once   sync.Once
}

func (a *agentConn) close() {
	a.once.Do(func() { close(a.closed); a.ws.Close() })
}

// DeviceIDs snapshots the currently connected device ids (status surface).
func (h *Hub) DeviceIDs() []string {
	h.mu.Lock()
	defer h.mu.Unlock()
	out := make([]string, 0, len(h.devices))
	for id := range h.devices {
		out = append(out, id)
	}
	return out
}

func normalizeID(s string) string { return strings.ToLower(strings.TrimSpace(s)) }

