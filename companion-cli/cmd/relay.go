package cmd

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"

	"github.com/companion-ide/companion-cli/internal/relay"
	"github.com/gorilla/websocket"
	"github.com/spf13/cobra"
)

// ── relay hub + relay push (remote OTA over the internet) ────────────

func newRelayCmd() *cobra.Command {
	relayCmd := &cobra.Command{
		Use:   "relay",
		Short: "Remote OTA: run a relay hub or push firmware through one",
	}

	// companion relay hub --listen :8931 --devices-token X --agents-token Y
	var (
		listen       string
		devicesToken string
		agentsToken  string
	)
	hubCmd := &cobra.Command{
		Use:   "hub",
		Short: "Run the relay hub devices and agents dial into",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Same secret-handling rule as the OTA password (audit F002):
			// prefer env over argv, since a flag value is visible in `ps`
			// output and shell history.
			if devicesToken == "" {
				devicesToken = os.Getenv("COMPANION_RELAY_DEVICES_TOKEN")
			}
			if agentsToken == "" {
				agentsToken = os.Getenv("COMPANION_RELAY_AGENTS_TOKEN")
			}
			if devicesToken == "" || agentsToken == "" {
				fmt.Fprintln(os.Stderr,
					"refusing to start with no tokens: set --devices-token/--agents-token "+
						"or COMPANION_RELAY_DEVICES_TOKEN/COMPANION_RELAY_AGENTS_TOKEN "+
						"(use \"*\" only for local lab testing)")
				return fmt.Errorf("hub tokens required")
			}
			if devicesToken == "*" || agentsToken == "*" {
				fmt.Println("⚠ auth DISABLED for one or both roles (\"*\" token) — lab/testing only, never expose this")
			}
			h := relay.NewHub(relay.Config{
				DevicesToken: devicesToken,
				AgentsToken:  agentsToken,
			})
			fmt.Printf("relay hub listening on %s\n", listen)
			fmt.Printf("devices: ws://<host>%s/device?token=...\n", listen)
			fmt.Printf("agents:  ws://<host>%s/agent?token=...\n", listen)
			srv := &relayHTTPServer{addr: listen, h: h.Handler()}
			return srv.serve()
		},
	}
	hubCmd.Flags().StringVar(&listen, "listen", ":8931", "address to listen on")
	hubCmd.Flags().StringVar(&devicesToken, "devices-token", "", "shared token devices must present (prefer COMPANION_RELAY_DEVICES_TOKEN; \"*\" disables auth — lab only)")
	hubCmd.Flags().StringVar(&agentsToken, "agents-token", "", "shared token agents must present (prefer COMPANION_RELAY_AGENTS_TOKEN; \"*\" disables auth — lab only)")
	relayCmd.AddCommand(hubCmd)

	// companion relay push --hub ws://host:8931 --token T --device ID \
	//   --device-secret S image.bin
	var (
		hubURL       string
		token        string
		deviceID     string
		deviceSecret string
	)
	pushCmd := &cobra.Command{
		Use:   "push <image.bin>",
		Short: "Push a firmware image to a remote device through the hub",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			// Prefer env for secrets (same rule as hub tokens / OTA password).
			if deviceSecret == "" {
				deviceSecret = os.Getenv("COMPANION_RELAY_DEVICE_SECRET")
			}
			if token == "" {
				token = os.Getenv("COMPANION_RELAY_AGENTS_TOKEN")
			}
			if token == "" {
				return fmt.Errorf("agent token required: --token or COMPANION_RELAY_AGENTS_TOKEN")
			}
			img, err := os.ReadFile(args[0])
			if err != nil {
				return fmt.Errorf("read image: %w", err)
			}
			sum := md5.Sum(img)
			md5hex := hex.EncodeToString(sum[:])

			u, err := url.Parse(hubURL)
			if err != nil {
				return fmt.Errorf("bad --hub: %w", err)
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
				"kind": relay.KindPushReq, "device": deviceID,
				"secret": deviceSecret,
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
			fmt.Printf("push accepted — streaming %d bytes to %s…\n", len(img), deviceID)
			ws.SetReadDeadline(time.Time{})
			pipe := newAgentPipe(ws)
			// 30 min: stop-and-wait over the tunnel is ~0.6s per 1 KiB chunk
			// (~12 min for a 1.2 MB image) plus the final MD5/flash window.
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
			defer cancel()
			if err := relay.PushDevice(ctx, pipe, bytes.NewReader(img), int64(len(img))); err != nil {
				return fmt.Errorf("push failed: %w", err)
			}
			// PushDevice saw the device's bare "OK". Tell the hub the pairing
			// is over explicitly (the board also sends push_done itself, belt
			// and suspenders), then close the agent socket (deferred).
			doneMsg, _ := json.Marshal(map[string]string{"kind": relay.KindPushDone})
			_ = ws.WriteMessage(websocket.TextMessage, doneMsg)
			fmt.Printf("✓ remote push complete — %s rebooting into new firmware\n", deviceID)
			return nil
		},
	}
	pushCmd.Flags().StringVar(&hubURL, "hub", "", "hub base URL (ws:// or wss:// host)")
	pushCmd.Flags().StringVar(&token, "token", "", "agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
	pushCmd.Flags().StringVar(&deviceID, "device", "", "target device id")
	pushCmd.Flags().StringVar(&deviceSecret, "device-secret", "", "that device's provisioning secret (prefer COMPANION_RELAY_DEVICE_SECRET)")
	pushCmd.MarkFlagRequired("hub")
	pushCmd.MarkFlagRequired("device")
	relayCmd.AddCommand(pushCmd)

	// companion relay devices --hub wss://host --token T
	// Preflight: show which devices are online at the hub before pushing.
	devicesCmd := &cobra.Command{
		Use:   "devices",
		Short: "List devices currently online at the hub",
		RunE: func(cmd *cobra.Command, args []string) error {
			if token == "" {
				token = os.Getenv("COMPANION_RELAY_AGENTS_TOKEN")
			}
			if token == "" {
				return fmt.Errorf("agent token required: --token or COMPANION_RELAY_AGENTS_TOKEN")
			}
			u, err := url.Parse(hubURL)
			if err != nil {
				return fmt.Errorf("bad --hub: %w", err)
			}
			// Accept the same ws:// / wss:// forms the rest of the relay CLI
			// uses (devices/push dial a websocket) — here we only perform an
			// HTTP health read, so map to the matching http scheme.
			switch u.Scheme {
			case "ws":
				u.Scheme = "http"
			case "wss":
				u.Scheme = "https"
			}
			u.Path = "/health"
			q := u.Query()
			q.Set("token", token)
			q.Set("format", "json")
			u.RawQuery = q.Encode()
			hc := &http.Client{Timeout: 10 * time.Second}
			resp, err := hc.Get(u.String())
			if err != nil {
				return fmt.Errorf("hub health: %w", err)
			}
			defer resp.Body.Close()
			body, _ := io.ReadAll(resp.Body)
			if resp.StatusCode != http.StatusOK {
				return fmt.Errorf("hub health: HTTP %d: %s", resp.StatusCode, body)
			}
			var health struct {
				Devices []struct {
					ID      string `json:"id"`
					Version string `json:"version"`
					Busy    bool   `json:"busy"`
				} `json:"devices"`
			}
			if err := json.Unmarshal(body, &health); err != nil {
				return fmt.Errorf("health parse: %w", err)
			}
			if len(health.Devices) == 0 {
				fmt.Println("no devices online")
				return nil
			}
			for _, d := range health.Devices {
				state := "idle"
				if d.Busy {
					state = "busy"
				}
				fmt.Printf("%s  v%s  %s\n", d.ID, d.Version, state)
			}
			return nil
		},
	}
	devicesCmd.Flags().StringVar(&hubURL, "hub", "", "hub base URL (ws:// or wss:// host)")
	devicesCmd.Flags().StringVar(&token, "token", "", "agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
	devicesCmd.MarkFlagRequired("hub")
	relayCmd.AddCommand(devicesCmd)

	return relayCmd
}
