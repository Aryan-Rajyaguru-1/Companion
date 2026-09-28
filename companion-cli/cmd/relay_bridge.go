package cmd

// relay_bridge.go — the category-2 remote transport.
//
// `companion relay bridge` pairs with a remote bridge device through the hub
// and exposes it as a LOCAL TCP socket. That is the whole trick: esptool
// (socket://), avrdude (net:), `companion upload --host/--port` and the IDE
// all speak the bridge protocol over TCP — so once the remote bridge is a
// local socket, every one of those tools works UNCHANGED against a bridge
// that is anywhere on the internet. No new upload code, no protocol changes.

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/url"
	"os"
	"time"

	"github.com/companion-ide/companion-cli/internal/relay"
	"github.com/gorilla/websocket"
	"github.com/spf13/cobra"
)

// dialRelayBridge pairs with a remote bridge device and exposes it as a
// local TCP socket on an ephemeral 127.0.0.1 port. The returned closer ends
// the pipe (which also clears the hub pairing via the agent disconnect).
//
// Used by `upload --ota-mode remote` for bridge targets: the MCU-specific
// uploaders shell out to esptool (socket://) and avrdude (net:) with a socket
// URL, and subprocesses cannot use an in-process net.Conn — so the remote
// bridge becomes a local socket and those tools work unchanged.
func dialRelayBridge(ctx context.Context, hubBase, token, deviceID, secret string) (int, func(), error) {
	u, err := url.Parse(hubBase)
	if err != nil {
		return 0, nil, fmt.Errorf("bad hub URL: %w", err)
	}
	u.Path = "/agent"
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()

	ws, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return 0, nil, fmt.Errorf("dial hub agent port: %w", err)
	}
	req, _ := json.Marshal(map[string]any{
		"kind": relay.KindPipeReq, "device": deviceID, "secret": secret,
	})
	if err := ws.WriteMessage(websocket.TextMessage, req); err != nil {
		ws.Close()
		return 0, nil, fmt.Errorf("pipe_req: %w", err)
	}
	ws.SetReadDeadline(time.Now().Add(10 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		ws.Close()
		return 0, nil, fmt.Errorf("pipe_ack: %w", err)
	}
	var ack struct {
		Kind  string `json:"kind"`
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &ack); err != nil {
		ws.Close()
		return 0, nil, fmt.Errorf("pipe_ack parse: %w", err)
	}
	ws.SetReadDeadline(time.Time{})
	if ack.Kind == relay.KindPushResult && !ack.OK {
		ws.Close()
		return 0, nil, fmt.Errorf("hub rejected the pipe: %s", ack.Error)
	}
	if ack.Kind != relay.KindPushAck || !ack.OK {
		ws.Close()
		return 0, nil, fmt.Errorf("unexpected hub reply: %s", raw)
	}

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		ws.Close()
		return 0, nil, fmt.Errorf("local listen: %w", err)
	}
	// Sequential accept+pipe: the bridge firmware serves ONE client at a
	// time, and concurrent ws.ReadMessage on one socket is not allowed.
	go func() {
		for {
			tcp, err := ln.Accept()
			if err != nil {
				return
			}
			pipeConn(ctx, ws, tcp)
		}
	}()
	port := ln.Addr().(*net.TCPAddr).Port
	return port, func() { ln.Close(); ws.Close() }, nil
}

// pipeConn pumps bytes bidirectionally between a local TCP client and the
// remote bridge device (through the hub's paired websocket). Either side
// closing ends the pipe; the hub clears the pairing on the agent's
// disconnect so the device is immediately reusable.
func pipeConn(ctx context.Context, ws *websocket.Conn, tcp net.Conn) error {
	defer tcp.Close()
	done := make(chan error, 2)

	// TCP client → device (binary frames through the hub).
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := tcp.Read(buf)
			if n > 0 {
				if werr := ws.WriteMessage(websocket.BinaryMessage, buf[:n]); werr != nil {
					done <- werr
					return
				}
			}
			if err != nil {
				done <- nil // client hung up — normal end
				return
			}
		}
	}()

	// Device → TCP client (binary frames from the hub).
	go func() {
		for {
			mt, payload, err := ws.ReadMessage()
			if err != nil {
				done <- nil // device link or hub gone
				return
			}
			if mt != websocket.BinaryMessage {
				continue // protocol frames are never target bytes
			}
			if _, err := tcp.Write(payload); err != nil {
				done <- err
				return
			}
		}
	}()

	select {
	case err := <-done:
		return err
	case <-ctx.Done():
		return nil
	}
}

func newRelayBridgeCmd() *cobra.Command {
	var (
		hubURL       string
		token        string
		deviceID     string
		deviceSecret string
		listenAddr   string
	)
	cmd := &cobra.Command{
		Use:   "bridge",
		Short: "Expose a remote bridge device as a local TCP socket",
		Long: `Pair with a bridge device through the relay hub and expose it as a
LOCAL TCP socket, so every tool that speaks the bridge protocol over TCP works
unchanged against a bridge that is anywhere on the internet:

  companion relay bridge --hub wss://ota.example.com \
    --device esp32-bridge-01 --listen 127.0.0.1:3333

  # then, unchanged from the LAN flow:
  companion upload --host 127.0.0.1 --port 3333 --fqbn arduino:avr:uno --mcu avr
  python3 -m esptool --chip esp32 --port socket://127.0.0.1:3333 ...
  avrdude -P net:127.0.0.1:3333 ...

The bridge device dials the hub itself (outbound), so no inbound ports are
needed anywhere. Pairing uses the same per-device secret as OTA pushes.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			if deviceSecret == "" {
				deviceSecret = os.Getenv("COMPANION_RELAY_DEVICE_SECRET")
			}
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
				"kind": relay.KindPipeReq, "device": deviceID, "secret": deviceSecret,
			})
			if err := ws.WriteMessage(websocket.TextMessage, req); err != nil {
				return fmt.Errorf("pipe_req: %w", err)
			}
			ws.SetReadDeadline(time.Now().Add(10 * time.Second))
			_, raw, err := ws.ReadMessage()
			if err != nil {
				return fmt.Errorf("pipe_ack: %w", err)
			}
			var ack struct {
				Kind  string `json:"kind"`
				OK    bool   `json:"ok"`
				Error string `json:"error"`
			}
			if err := json.Unmarshal(raw, &ack); err != nil {
				return fmt.Errorf("pipe_ack parse: %w", err)
			}
			if ack.Kind == relay.KindPushResult && !ack.OK {
				return fmt.Errorf("hub rejected the pipe: %s", ack.Error)
			}
			if ack.Kind != relay.KindPushAck || !ack.OK {
				return fmt.Errorf("unexpected hub reply: %s", raw)
			}
			ws.SetReadDeadline(time.Time{})

			ln, err := net.Listen("tcp", listenAddr)
			if err != nil {
				return fmt.Errorf("listen on %s: %w", listenAddr, err)
			}
			defer ln.Close()
			printInfo(fmt.Sprintf("Remote bridge %s → local socket %s  (Ctrl-C to stop)",
				colorBold(deviceID), colorTeal(ln.Addr().String())))
			printInfo("Point esptool / avrdude / `companion upload --host` at that address.")

			ctx, cancel := context.WithCancel(cmd.Context())
			defer cancel()
			for {
				tcp, err := ln.Accept()
				if err != nil {
					return err
				}
				// The bridge firmware serves ONE client at a time; pipe until
				// this client (or the device link) drops, then accept again.
				go func() {
					if err := pipeConn(ctx, ws, tcp); err != nil {
						printError("bridge pipe: " + err.Error())
					}
				}()
			}
		},
	}
	cmd.Flags().StringVar(&hubURL, "hub", "", "hub base URL (ws:// or wss:// host)")
	cmd.Flags().StringVar(&token, "token", "", "agent token (prefer COMPANION_RELAY_AGENTS_TOKEN)")
	cmd.Flags().StringVar(&deviceID, "device", "", "target bridge device id")
	cmd.Flags().StringVar(&deviceSecret, "device-secret", "",
		"that device's provisioning secret (prefer COMPANION_RELAY_DEVICE_SECRET)")
	cmd.Flags().StringVar(&listenAddr, "listen", "127.0.0.1:3333",
		"local address to expose the remote bridge on")
	cmd.MarkFlagRequired("hub")
	cmd.MarkFlagRequired("device")
	return cmd
}
