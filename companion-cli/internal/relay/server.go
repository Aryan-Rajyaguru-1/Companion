package relay

import (
	"crypto/subtle"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 4096,
	// Origin checking is meaningless for non-browser clients; tokens guard.
	CheckOrigin: func(r *http.Request) bool { return true },
}

// maxWSMessage caps a single inbound websocket message. Data frames are
// negotiated at most 8 KiB, so 1 MiB is ~100x headroom for a real client while
// stopping a peer (or anyone who got past the token) from making the hub
// allocate an arbitrary amount of memory for one frame. Applied per connection
// right after the upgrade — gorilla has no Upgrader-level limit.
const maxWSMessage = 1 << 20

// Handler returns the hub's HTTP routes:
//
//	GET /device?token=…  — a device registers (expects device_hello first)
//	GET /agent?token=…   — an IDE/CLI agent connects (agent_hello first)
//	GET /health          — liveness; with a valid role token, also the
//	                       connected-device list (relay devices / fleet preflight)
func (h *Hub) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/device", h.serveDeviceWS)
	mux.HandleFunc("/agent", h.serveAgentWS)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		// Unauthenticated callers (uptime monitors, tunnel probes) get a
		// minimal liveness body — no device inventory. Token-holders get
		// the full status surface.
		tok := r.URL.Query().Get("token")
		authed := h.authed(tok, h.cfg.AgentsToken) || h.authed(tok, h.cfg.DevicesToken)
		if !authed {
			json.NewEncoder(w).Encode(map[string]any{"ok": true})
			return
		}
		json.NewEncoder(w).Encode(map[string]any{
			"ok":      true,
			"devices": h.ListDevices(),
			"time":    time.Now().UTC(),
		})
	})
	return mux
}

func (h *Hub) serveDeviceWS(w http.ResponseWriter, r *http.Request) {
	if !h.authed(r.URL.Query().Get("token"), h.cfg.DevicesToken) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	ws.SetReadLimit(maxWSMessage)
	d := &deviceConn{conn: conn{ws: ws}, closed: make(chan struct{})}
	h.deviceLoop(d)
}

func (h *Hub) serveAgentWS(w http.ResponseWriter, r *http.Request) {
	if !h.authed(r.URL.Query().Get("token"), h.cfg.AgentsToken) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	ws, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	ws.SetReadLimit(maxWSMessage)
	a := &agentConn{conn: conn{ws: ws}, closed: make(chan struct{})}
	h.agentLoop(a)
}

// deviceLoop is the read side of a device connection. The first frame must
// be device_hello; during an active push, the device's binary frames (its
// bare-ACK replies) are forwarded to the paired agent's socket.
//
// Deadlock discipline: NO blocking read on this socket may carry a deadline
// shorter than the full push. The data phase is a stop-and-wait loop whose
// per-hop RTT is unbounded over the internet path (Cloudflare edge hops,
// tunnel QUIC, agent stalls); a single read deadline expiring mid-push looks
// exactly like a disconnect, and the old 30s hello deadline fired precisely
// there. The hello frame (a small JSON text frame the board sends
// immediately) keeps the only deadline; the steady-state loop and agent
// loop rely on TCP close/WS close frames to detect real disconnects.
func (h *Hub) deviceLoop(d *deviceConn) {
	defer func() {
		h.mu.Lock()
		if cur := h.devices[d.id]; cur == d {
			delete(h.devices, d.id)
		}
		h.mu.Unlock()
		if d.agent != nil {
			h.pushResult(d.agent, d.id, "device disconnected mid-push")
		}
		h.finishPush(d)
		d.close()
	}()

	// First frame must be device_hello. The deadline applies to this hello
	// read ONLY: it guards against half-open sockets that never identify,
	// and is cleared before the steady-state loop (see the discipline note
	// on deviceLoop) so a long stop-and-wait push is never mistaken for a
	// dead connection.
	d.ws.SetReadDeadline(time.Now().Add(h.cfg.ReadTimeout))
	_, raw, err := d.ws.ReadMessage()
	d.ws.SetReadDeadline(time.Time{})
	if err != nil {
		return
	}
	var hello struct {
		Kind    string `json:"kind"`
		ID      string `json:"id"`
		Ver     string `json:"version"`
		Secret  string `json:"secret"`
		FrameKB int    `json:"frame_kb"` // optional: negotiated data-frame size (KiB)
		IP      string `json:"ip"`       // optional: the board's LAN address (LAN OTA recovery)
	}
	if err := json.Unmarshal(raw, &hello); err != nil || hello.Kind != KindDeviceHello {
		h.nudge(d, "first frame must be device_hello")
		return
	}
	d.id = normalizeID(hello.ID)
	d.version = hello.Ver
	d.secret = hello.Secret // per-device identity, checked at push time
	d.frameKB = hello.FrameKB
	d.ip = hello.IP
	if d.id == "" {
		h.nudge(d, "device id required")
		return
	}
	// A device MUST present a secret. An empty one used to mean "no check":
	// Pair skipped verification entirely, so anyone holding the devices token
	// could register a board with an empty secret and receive its pushes — and,
	// since pipe mode carries raw UART bytes, its whole flashing session.
	if d.secret == "" {
		log.Printf("[relay] rejected device hello with an empty secret (id=%q)", d.id)
		h.nudge(d, "device_hello must carry a provisioning secret")
		return
	}

	h.mu.Lock()
	if old, ok := h.devices[d.id]; ok && old != d {
		// Re-registration is normal (a reconnect after a drop) — but only from
		// the SAME board. Superseding on id alone let any holder of the devices
		// token evict the incumbent by reusing its id and take its place, which
		// is a complete takeover of that board's identity.
		if subtle.ConstantTimeCompare([]byte(old.secret), []byte(d.secret)) != 1 {
			h.mu.Unlock()
			log.Printf("[relay] rejected registration for %s: id already held by a board with a different secret", d.id)
			h.nudge(d, "device id already registered with a different secret")
			return
		}
		old.close() // same board, fresh connection — supersede it
	}
	h.devices[d.id] = d
	h.mu.Unlock()
	h.send2(d, KindWelcome, map[string]any{"ok": true, "id": d.id})
	log.Printf("[relay] device registered: %s (v%s, secret %s)", d.id, hello.Ver,
		map[bool]string{true: "present", false: "none"}[hello.Secret != ""])

	for {
		mt, payload, err := d.ws.ReadMessage()
		if err != nil {
			return
		}
		if mt == websocket.TextMessage {
			// Control text frame on the device socket: push_done is the
			// board's explicit end-of-push signal — clear pairing so the
			// device is immediately pushable again.
			var msg struct {
				Kind string `json:"kind"`
			}
			if err := json.Unmarshal(payload, &msg); err == nil && msg.Kind == KindPushDone {
				// Board's explicit end-of-push (sent right after its bare
				// "OK"). Idempotent with the agent-side push_done: either
				// path clears the pairing; the board stays connected.
				h.mu.Lock()
				a := d.agent
				h.mu.Unlock()
				if a != nil {
					h.send2(a, KindPushDone, map[string]any{"device": d.id})
				}
				h.finishPush(d)
			}
			// Heartbeat: the board's zombie-link watchdog pings every 15s and
			// demands a pong within 10s. A connection can die without a close
			// frame (tunnel QUIC drop, hub crash) — without this reply the
			// board would either sit on a dead socket reporting link=1 (its
			// old bug) or, with the watchdog, re-dial forever. Answer it.
			if err == nil && msg.Kind == KindPing {
				log.Printf("[relay] heartbeat ping from %s → pong sent", d.id)
				_ = h.send2(d, KindPong, map[string]any{"ok": true})
			}
			continue
		}
		if mt != websocket.BinaryMessage {
			continue // stray frame type
		}
		h.mu.Lock()
		a := d.agent
		h.mu.Unlock()
		if a == nil {
			continue // stray frame with no push in flight
		}
		if err := a.sendBinary(payload); err != nil {
			log.Printf("[relay] agent socket write failed for %s: %v", d.id, err)
			return // agent gone — end this device read loop, pairing stays busy until it reconnects
		}
	}
}

// agentLoop is the read side of an agent connection: push requests come in,
// results (forwarded from the device side or local errors) go out.
func (h *Hub) agentLoop(a *agentConn) {
	defer func() {
		h.finishPushAgent(a)
		h.mu.Lock()
		delete(h.agents, a)
		h.mu.Unlock()
		a.close()
	}()

	h.mu.Lock()
	h.agents[a] = struct{}{}
	h.mu.Unlock()

	for {
		mt, raw, err := a.ws.ReadMessage()
		if err != nil {
			return
		}
		if mt == websocket.BinaryMessage {
			// Agent → device firmware bytes during a push. Forward on the
			// device socket; the device reads them as image data.
			h.mu.Lock()
			d := a.device
			h.mu.Unlock()
			if d == nil {
				continue
			}
			_ = d.sendBinary(raw)
			continue
		}
		var req struct {
			Kind   string `json:"kind"`
			Device string `json:"device"`
			Size   int64  `json:"size"`
			MD5    string `json:"md5"`
			Secret string `json:"secret"`
		}
		if err := json.Unmarshal(raw, &req); err != nil {
			continue
		}
		switch req.Kind {
		case KindPushReq:
			h.startPush(a, req.Device, req.Secret, req.Size, req.MD5)
		case KindPipeReq:
			h.startPipe(a, req.Device, req.Secret)
		case KindPushDone:
			// Agent confirms PushDevice saw the device's bare "OK" (the
			// board also emits its own push_done on the device socket —
			// belt and suspenders). Either path idempotently clears the
			// pairing so the board is immediately pushable again.
			h.finishPushAgent(a)
		case KindStatus:
			log.Printf("[relay/agent %s] status frame", a.name)
		default:
			h.nudgeAgent(a, "unknown kind: "+req.Kind)
		}
	}
}

// startPush validates and pairs a push via Hub.Pair: device online? not
// busy? not paired elsewhere? secret matches? If ok, the device receives
// push_start (size+md5) and the agent receives push_ack. Firmware flows
// agent→hub→device as binary frames; the device's bare-ACK replies flow
// device→hub→agent the same way, so the agent-side reader sees exactly the
// byte stream a LAN ArduinoOTA device would emit.
func (h *Hub) startPush(a *agentConn, devID, secret string, size int64, md5 string) {
	err := h.Pair(a, PairRequest{DeviceID: devID, Secret: secret})
	if err != nil {
		h.pushResult(a, devID, err.Error())
		return
	}
	devID = normalizeID(devID)
	h.mu.Lock()
	d := h.devices[devID]
	h.mu.Unlock()
	if d == nil { // raced with disconnect; Pair already cleaned up
		return
	}

	h.send2(d, KindPushStart, map[string]any{"size": size, "md5": md5})
	ackBody := map[string]any{"ok": true, "device": devID}
	// Relay the device's negotiated frame size so the agent can amortize the
	// per-ACK round trip (the stop-and-wait lever). Absent for legacy
	// firmware, which keeps the 1024-byte ArduinoOTA frame.
	if d.frameKB > 0 {
		ackBody["frame_kb"] = d.frameKB
	}
	// The firmware the board is running RIGHT NOW, and its LAN address. Both
	// are learned only at pairing time, and both are what a fleet needs to
	// roll out safely: "skip what is already current" is impossible without
	// the version, and the LAN address is what a local recovery push needs.
	if d.version != "" {
		ackBody["version"] = d.version
	}
	if d.ip != "" {
		ackBody["ip"] = d.ip
	}
	_ = h.send2(a, KindPushAck, ackBody)
}

// startPipe pairs an agent with a device for a TRANSPARENT byte pipe — the
// bridge mode. The agent's uploader/monitor speaks its own protocol straight
// over the pipe (esptool socket://, avrdude net:, raw UART streams), so there
// is no push_start and no stop-and-wait ACK contract; the device is a dumb
// byte relay. Pairing checks are identical to startPush: online? not busy?
// not paired elsewhere? per-device secret matches?
func (h *Hub) startPipe(a *agentConn, devID, secret string) {
	if err := h.Pair(a, PairRequest{DeviceID: devID, Secret: secret}); err != nil {
		h.pushResult(a, devID, err.Error())
		return
	}
	_ = h.send2(a, KindPushAck, map[string]any{"ok": true, "device": normalizeID(devID)})
}

// pushResult delivers a terminal push outcome to an agent.
func (h *Hub) pushResult(a *agentConn, devID, msg string) {
	h.send2(a, KindPushResult, map[string]any{
		"ok": msg == "", "device": devID, "error": msg,
	})
}

// finishPush tears down pairing after a push ends (success or failure).
// The board stays connected and is immediately pushable again.
func (h *Hub) finishPush(d *deviceConn) {
	h.mu.Lock()
	a := d.agent
	d.busy = false
	d.agent = nil
	if a != nil {
		a.device = nil
	}
	h.mu.Unlock()
}

// finishPushAgent tears down pairing from the agent side: the push_done
// control frame arrives on the agent socket (the board also emits its own
// push_done on the device socket — belt and suspenders), or the agent
// disconnects. Either way the device goes idle but stays connected.
func (h *Hub) finishPushAgent(a *agentConn) {
	h.mu.Lock()
	d := a.device
	a.device = nil
	if d != nil && d.agent == a {
		d.agent = nil
		d.busy = false
	}
	h.mu.Unlock()
}

// send2 wraps conn.send, tagging the body with its kind. Works for both
// role conns since both embed conn.
func (h *Hub) send2(c any, kind string, body map[string]any) error {
	switch t := c.(type) {
	case *deviceConn:
		body["kind"] = kind
		return t.send(body)
	case *agentConn:
		body["kind"] = kind
		return t.send(body)
	}
	return nil
}

func (h *Hub) nudge(d *deviceConn, msg string) {
	h.send2(d, KindWelcome, map[string]any{"ok": false, "error": msg})
}

func (h *Hub) nudgeAgent(a *agentConn, msg string) {
	h.send2(a, KindStatus, map[string]any{"error": msg})
}
