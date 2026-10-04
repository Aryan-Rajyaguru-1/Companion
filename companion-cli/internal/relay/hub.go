package relay

import (
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"log"
	"sort"
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

// DeviceInfo is a status/health snapshot of one connected device.
type DeviceInfo struct {
	ID      string `json:"id"`
	IP      string `json:"ip,omitempty"` // board's LAN address, for --ota-mode local
	Version string `json:"version,omitempty"`
	Busy    bool   `json:"busy"`
}

// Hub is the relay server: it holds device and agent connections and pairs
// pushes between them. Devices and agents never see each other's sockets;
// the hub forwards push data between the paired pair.
type Hub struct {
	cfg Config

	mu      sync.Mutex
	devices map[string]*deviceConn // by device id
	agents  map[*agentConn]struct{}

	// knownSecrets remembers the secret each device id has presented, and
	// outlives the connection that presented it.
	//
	// Checking h.devices[id] is not enough, because that map holds only boards
	// connected *right now*. A board that is powered off or has lost the network
	// is simply absent, so anyone holding the devices token could claim its id
	// with a secret of their own — and then the genuine board, coming back with
	// its real secret, would fail the same-secret check and be locked out of its
	// own identity, while the squatter collected its pushes. An entry here is
	// never removed and never overwritten, so the first secret to claim an id
	// owns it for the lifetime of the hub process.
	knownSecrets map[string]string
}

// NewHub builds a Hub with the given config.
func NewHub(cfg Config) *Hub {
	if cfg.ReadTimeout <= 0 {
		cfg.ReadTimeout = 30 * time.Second
	}
	// "*" disables auth for that role. It is a development convenience, and a
	// deployed config that still has it makes the hub an open proxy for
	// firmware — say so loudly at startup rather than discovering it later.
	if cfg.DevicesToken == "*" || cfg.AgentsToken == "*" {
		roles := []string{}
		if cfg.DevicesToken == "*" {
			roles = append(roles, "devices")
		}
		if cfg.AgentsToken == "*" {
			roles = append(roles, "agents")
		}
		log.Printf("*** WARNING: auth DISABLED for %s — a wildcard token accepts every client. "+
			"Never run a deployed hub this way. ***", strings.Join(roles, " and "))
	}
	return &Hub{
		cfg:          cfg,
		devices:      make(map[string]*deviceConn),
		agents:       make(map[*agentConn]struct{}),
		knownSecrets: make(map[string]string),
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
// A token of "*" in config disables auth for that role (dev only) — NewHub
// shouts about it at startup, because a wildcard left in a deployed config
// turns the hub into an open proxy for firmware.
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
	secret  string // per-device secret presented in device_hello ("" = none yet)
	busy    bool
	agent   *agentConn // set during an active push
	closed  chan struct{}
	once    sync.Once
	version string
	// frameKB is the max data-frame size (in KiB) the device advertised at
	// hello. The relay path is stop-and-wait, so this is the chunk÷RTT lever:
	// a board that accepts 8 KiB per frame needs ~8× fewer round-trips than
	// one at 1 KiB. 0 = not advertised (legacy firmware) → keep the 1024-byte
	// ArduinoOTA frame.
	frameKB int
	// ip is the board's own LAN address, advertised at hello. The relay is
	// one-way (the board dials out), so this is how an operator discovers
	// where a board lives — needed for the LAN recovery path.
	ip string
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

// ListDevices snapshots the connected devices with busy/version status.
// Served by the (authenticated) /health endpoint and the `relay devices`
// preflight.
func (h *Hub) ListDevices() []DeviceInfo {
	h.mu.Lock()
	defer h.mu.Unlock()
	out := make([]DeviceInfo, 0, len(h.devices))
	for _, d := range h.devices {
		out = append(out, DeviceInfo{ID: d.id, IP: d.ip, Version: d.version, Busy: d.busy})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// PairRequest is an agent's push request for one device.
type PairRequest struct {
	DeviceID string
	Secret   string // per-device secret; required when the device presented one
}

// Pair validates a push request and, on success, marks the device busy and
// links it to the agent. Checks, in order (all failing closed):
//  1. device known (connected);
//  2. not already busy;
//  3. not already paired to a different agent;
//  4. per-device secret matches the one the board presented at hello.
func (h *Hub) Pair(agent *agentConn, req PairRequest) error {
	id := normalizeID(req.DeviceID)
	h.mu.Lock()
	defer h.mu.Unlock()

	d, ok := h.devices[id]
	if !ok {
		return fmt.Errorf("device %q is not connected", req.DeviceID)
	}
	if d.busy {
		return fmt.Errorf("device %q is busy (another push in progress)", req.DeviceID)
	}
	if d.agent != nil && d.agent != agent {
		return fmt.Errorf("device %q is already paired to another agent", req.DeviceID)
	}
	// The secret is REQUIRED, never optional. An empty stored secret used to
	// skip this block entirely, so a board registered with an empty secret
	// could be pushed to (or piped from) by anyone holding the devices token.
	// deviceLoop now rejects empty secrets at hello, so d.secret is always set —
	// and this must stay strict anyway: a future path that lets a device in
	// without a secret must not silently disable verification here.
	if req.Secret == "" {
		return fmt.Errorf("device secret required (pass --device-secret)")
	}
	if subtle.ConstantTimeCompare([]byte(req.Secret), []byte(d.secret)) != 1 {
		return fmt.Errorf("device secret rejected for %q", req.DeviceID)
	}

	d.busy = true
	d.agent = agent
	agent.device = d
	return nil
}

// Unpair clears busy/pairing for the device linked to an agent — invoked on
// push_done, agent disconnect, or push failure so the board is immediately
// ready for the next push without a reconnect.
func (h *Hub) Unpair(agent *agentConn) {
	if agent == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if d := agent.device; d != nil {
		if d.agent == agent {
			d.agent = nil
			d.busy = false
		}
		agent.device = nil
	}
}

func normalizeID(s string) string { return strings.ToLower(strings.TrimSpace(s)) }
