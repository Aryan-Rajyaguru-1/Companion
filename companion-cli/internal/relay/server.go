package relay

import (
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

// Handler returns the hub's HTTP routes:
//
//	GET /device?token=…  — a device registers (expects device_hello first)
//	GET /agent?token=…   — an IDE/CLI agent connects (agent_hello first)
//	GET /health          — liveness + connected device count
func (h *Hub) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/device", h.serveDeviceWS)
	mux.HandleFunc("/agent", h.serveAgentWS)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"ok":      true,
			"devices": h.DeviceIDs(),
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
	a := &agentConn{conn: conn{ws: ws}, closed: make(chan struct{})}
	h.agentLoop(a)
}

// deviceLoop is the read side of a device connection. The first frame must
// be device_hello; during an active push, the device's binary frames (its
// bare-ACK replies) are forwarded to the paired agent's socket.
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

	// First frame must be device_hello.
	d.ws.SetReadDeadline(time.Now().Add(h.cfg.ReadTimeout))
	_, raw, err := d.ws.ReadMessage()
	if err != nil {
		return
	}
	var hello struct {
		Kind string `json:"kind"`
		ID   string `json:"id"`
		Ver  string `json:"version"`
	}
	if err := json.Unmarshal(raw, &hello); err != nil || hello.Kind != KindDeviceHello {
		h.nudge(d, "first frame must be device_hello")
		return
	}
	d.id = normalizeID(hello.ID)
	d.version = hello.Ver
	if d.id == "" {
		h.nudge(d, "device id required")
		return
	}

	h.mu.Lock()
	if old, ok := h.devices[d.id]; ok {
		old.close() // superseded re-registration
	}
	h.devices[d.id] = d
	h.mu.Unlock()
	h.send2(d, KindWelcome, map[string]any{"ok": true, "id": d.id})
	log.Printf("[relay] device registered: %s (v%s)", d.id, hello.Ver)

	for {
		mt, payload, err := d.ws.ReadMessage()
		if err != nil {
			return
		}
		if mt != websocket.BinaryMessage {
			continue // control/text stray — ACKs are binary only
		}
		h.mu.Lock()
		a := d.agent
		h.mu.Unlock()
		if a == nil {
			continue // stray frame with no push in flight
		}
		_ = a.sendBinary(payload)
	}
}

// agentLoop is the read side of an agent connection: push requests come in,
// results (forwarded from the device side or local errors) go out.
func (h *Hub) agentLoop(a *agentConn) {
	defer func() {
		h.mu.Lock()
		if a.device != nil {
			a.device.agent = nil
		}
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
		}
		if err := json.Unmarshal(raw, &req); err != nil {
			continue
		}
		switch req.Kind {
		case KindPushReq:
			h.startPush(a, req.Device, req.Size, req.MD5)
		case KindStatus:
			log.Printf("[relay/agent %s] status frame", a.name)
		default:
			h.nudgeAgent(a, "unknown kind: "+req.Kind)
		}
	}
}

// startPush validates and pairs a push: device online? not busy? If ok, the
// device receives push_start (size+md5) and the agent receives push_ack.
// Firmware flows agent→hub→device as binary frames; the device's bare-ACK
// replies flow device→hub→agent the same way, so the agent-side reader sees
// exactly the byte stream a LAN ArduinoOTA device would emit.
func (h *Hub) startPush(a *agentConn, devID string, size int64, md5 string) {
	devID = normalizeID(devID)
	h.mu.Lock()
	d := h.devices[devID]
	if d == nil {
		h.mu.Unlock()
		h.pushResult(a, devID, "device not online: "+devID)
		return
	}
	if d.busy {
		h.mu.Unlock()
		h.pushResult(a, devID, "device busy with another push")
		return
	}
	d.busy = true
	d.agent = a
	a.device = d
	h.mu.Unlock()

	h.send2(d, KindPushStart, map[string]any{"size": size, "md5": md5})
	_ = h.send2(a, KindPushAck, map[string]any{"ok": true, "device": devID})
}

// pushResult delivers a terminal push outcome to an agent.
func (h *Hub) pushResult(a *agentConn, devID, msg string) {
	h.send2(a, KindPushResult, map[string]any{
		"ok": msg == "", "device": devID, "error": msg,
	})
}

// finishPush tears down pairing after a push ends (success or failure).
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