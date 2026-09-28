package cmd

import (
	"encoding/json"
	"fmt"
	"github.com/companion-ide/companion-cli/internal/relay"
	"github.com/spf13/cobra"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
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
			// Announce the size, then delegate the whole exchange. This used
			// to be a third copy of the pairing + streaming sequence (the
			// fleet path and the uploader plugin each had one); now there is
			// exactly one implementation, in internal/relay.PushToDevice.
			if fi, serr := os.Stat(args[0]); serr == nil {
				fmt.Printf("push accepted — streaming %d bytes to %s…\n", fi.Size(), deviceID)
			}
			if _, err := relay.PushToDevice(cmd.Context(), relay.PushRequest{
				Hub:       hubURL,
				Token:     token,
				Device:    deviceID,
				Secret:    deviceSecret,
				ImagePath: args[0],
			}); err != nil {
				return err
			}
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
					IP      string `json:"ip"`
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
				// The IP is the board's own LAN address: the relay is one-way
				// (the board dials out), so this is how you find it for a
				// local recovery push — `companion ota upload <ip> --ota-mode
				// local` — when the hub is the thing that is unreachable.
				ip := d.IP
				if ip == "" {
					ip = "ip unknown (older firmware)"
				}
				fmt.Printf("%-22s %-16s v%-12s %s\n", d.ID, ip, d.Version, state)
			}
			return nil
		},
	}
	devicesCmd.Flags().StringVar(&hubURL, "hub", "", "hub base URL (ws:// or wss:// host)")
	devicesCmd.Flags().StringVar(&token, "token", "", "agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
	devicesCmd.MarkFlagRequired("hub")
	relayCmd.AddCommand(devicesCmd)

	relayCmd.AddCommand(newRelayBridgeCmd()) // category-2 remote: bridge over the hub

	return relayCmd
}
