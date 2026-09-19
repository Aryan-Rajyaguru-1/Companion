package cmd

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

	// companion relay push --hub ws://host:8931 --token T --device ID image.bin
	var (
		hubURL   string
		token    string
		deviceID string
	)
	pushCmd := &cobra.Command{
		Use:   "push <image.bin>",
		Short: "Push a firmware image to a remote device through the hub",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
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
				"size": len(img), "md5": md5hex,
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
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
			defer cancel()
			if err := relay.PushDevice(ctx, pipe, bytes.NewReader(img), int64(len(img))); err != nil {
				return fmt.Errorf("push failed: %w", err)
			}
			fmt.Printf("✓ remote push complete — %s rebooting into new firmware\n", deviceID)
			return nil
		},
	}
	pushCmd.Flags().StringVar(&hubURL, "hub", "", "hub base URL (ws://host:port)")
	pushCmd.Flags().StringVar(&token, "token", "", "agent token")
	pushCmd.Flags().StringVar(&deviceID, "device", "", "target device id")
	pushCmd.MarkFlagRequired("hub")
	pushCmd.MarkFlagRequired("device")
	relayCmd.AddCommand(pushCmd)

	return relayCmd
}
