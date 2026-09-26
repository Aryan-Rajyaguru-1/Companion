// Package relay implements remote OTA: a WebSocket relay ("hub") that
// bridges push clients (IDE/CLI) to registered ESP32-class devices over the
// public internet.
//
// Topology — every connection is DIALLED OUTBOUND by its initiator, so the
// system traverses NAT/firewalls everywhere (no port forwarding, works on
// any network): devices and agents dial the hub, which is published through
// a Cloudflare Tunnel (wss://…) or any reverse proxy terminating TLS.
//
//	               wss (outbound)                    wss (outbound)
//	  ESP32 device ──────────────► RELAY HUB ◄────────────── IDE / CLI
//	  (ArduinoOTA-style              (Jetson)                (push client)
//	   Update loop)
//
// Wire protocol (protocol.go): small JSON control frames on the control
// side of each connection; firmware bytes flow over a dedicated paired
// data side, hub ↔ device, with the device ACKing counts exactly like
// ArduinoOTA does on LAN (bare decimal + final "OK"), so the device-side
// firmware reuses the same Update write/ACK state machine.
package relay

// Message kinds exchanged as single-line JSON on WebSocket connections.
const (
	// agent → hub: register an authenticated agent session.
	KindAgentHello = "agent_hello"
	// device → hub: first frame after connect; announces identity.
	KindDeviceHello = "device_hello"
	// hub → both: ack/nack carrying ok + error text.
	KindWelcome = "welcome"
	// agent → hub: request a push to a device id.
	KindPushReq = "push_req"
	// hub → agent: push accepted/rejected (device online, token valid).
	KindPushAck = "push_ack"
	// hub → device: incoming push (image size + md5 follow on data side).
	KindPushStart = "push_start"
	// both: app-level status lines (logs from device, errors either side).
	KindStatus = "status"
	// hub → agent: push outcome (device rebooted / error).
	KindPushResult = "push_result"
	// device → hub: sent after a completed push (post-"OK") so the hub can
	// clear busy/pairing without waiting for a reconnect.
	KindPushDone = "push_done"
	// device → hub: heartbeat ping (the board's zombie-link watchdog).
	KindPing = "ping"
	// hub → device: heartbeat pong — proves the link is alive end-to-end.
	KindPong = "pong"
	// hub → device: shutdown notice (device should idle its relay link).
	KindBye = "bye"
)
