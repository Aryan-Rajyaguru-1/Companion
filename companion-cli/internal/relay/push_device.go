package relay

// push_device.go — pushing an image to a relay device, in ONE place.
//
// This used to live in cmd, which meant only the CLI could do it. The uploader
// plugin needs the identical sequence, and cmd cannot be imported from a
// package the CLI depends on. Both callers now use PushToDevice, so "what the
// plugin does" and "what `relay push` does" cannot drift — the same argument
// for extracting the shared link code on the firmware side.

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"time"

	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/gorilla/websocket"
)

// PushRequest is one push to one device.
type PushRequest struct {
	Hub       string // base URL, ws:// or wss://
	Token     string // agent token
	Device    string // device id
	Secret    string // the device's provisioning secret
	ImagePath string // the .bin to send
	// Stream carries progress reporting and transport tuning (chunk size,
	// timeouts). nil is fine.
	Stream *ota.StreamOptions
}

// (The return type is the package's DeviceInfo, the same shape /health
// reports: Version and IP come from the pairing, and are empty for legacy
// firmware or on paths that cannot report them. Callers must treat "" as
// "unknown", never as "up to date".)

// PushToDevice pushes an image to a device through the hub and returns what the
// board reported at pairing (its running firmware version and its LAN address).
//
// The whole exchange: dial the agent port, ask to be paired (online? not busy?
// not paired elsewhere? secret matches?), stream the image in the
// stop-and-wait frame size the board advertised, wait for its MD5-verified
// "OK", then release the pairing.
func PushToDevice(ctx context.Context, req PushRequest) (DeviceInfo, error) {
	var info DeviceInfo // Version/IP filled from the ack below
	if req.Token == "" {
		return info, fmt.Errorf("agent token required: --token or COMPANION_RELAY_AGENTS_TOKEN")
	}
	img, err := os.ReadFile(req.ImagePath)
	if err != nil {
		return info, fmt.Errorf("read image: %w", err)
	}
	sum := md5.Sum(img)
	md5hex := hex.EncodeToString(sum[:])

	u, err := url.Parse(req.Hub)
	if err != nil {
		return info, fmt.Errorf("bad hub URL: %w", err)
	}
	u.Path = "/agent"
	q := u.Query()
	q.Set("token", req.Token)
	u.RawQuery = q.Encode()

	ws, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return info, fmt.Errorf("dial hub agent port: %w", err)
	}
	defer ws.Close()

	pair, _ := json.Marshal(map[string]any{
		"kind": KindPushReq, "device": req.Device,
		"secret": req.Secret,
		"size":   len(img), "md5": md5hex,
	})
	if err := ws.WriteMessage(websocket.TextMessage, pair); err != nil {
		return info, fmt.Errorf("push_req: %w", err)
	}
	ws.SetReadDeadline(time.Now().Add(10 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		return info, fmt.Errorf("push_ack: %w", err)
	}
	var ack struct {
		Kind  string `json:"kind"`
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &ack); err != nil {
		return info, fmt.Errorf("push_ack parse: %w", err)
	}
	if ack.Kind == KindPushResult && !ack.OK {
		return info, fmt.Errorf("hub rejected push: %s", ack.Error)
	}
	if ack.Kind != KindPushAck || !ack.OK {
		return info, fmt.Errorf("unexpected hub reply: %s", raw)
	}
	ws.SetReadDeadline(time.Time{})

	info.Version, info.IP = DeviceFromAck(raw)

	so := req.Stream
	if so == nil {
		so = &ota.StreamOptions{}
	}
	// Frame size: negotiated at hello and relayed via push_ack. A caller-set
	// ChunkBytes wins; otherwise use the device's advertised value, or the
	// legacy 1024-byte frame when absent.
	if frameKB := FrameKBFromAck(raw); frameKB > 0 {
		cloned := *so
		if cloned.ChunkBytes <= 0 {
			cloned.ChunkBytes = frameKB
		}
		so = &cloned
	}

	// 30 min: stop-and-wait over the tunnel plus the final MD5/flash window.
	pctx, cancel := context.WithTimeout(ctx, 30*time.Minute)
	defer cancel()
	if err := PushDeviceStream(pctx, newAgentPipe(ws), bytes.NewReader(img), int64(len(img)), so); err != nil {
		return info, fmt.Errorf("push to %s failed: %w", req.Device, err)
	}
	doneMsg, _ := json.Marshal(map[string]string{"kind": KindPushDone})
	_ = ws.WriteMessage(websocket.TextMessage, doneMsg)
	return info, nil
}
