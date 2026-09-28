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

// pairRelayBridge dials the hub's agent port and asks for a transparent pipe to
// the device. The returned websocket IS the pairing: the caller owns it and
// must close it when the session ends, which is what makes the hub unpair the
// device immediately.
//
// One pairing per local client, deliberately. A long-lived socket reused across
// clients leaves the previous pipe's reader goroutine blocked in
// ws.ReadMessage when its client hangs up; the next client's reader then
// competes with it for frames, and the orphan can swallow the first one. The
// ESP32 bridge firmware also serves ONE client at a time, so a fresh pairing
// per connection matches what the device can actually do — and it survives the
// bridge rebooting between sessions, which a reused socket could not.
func pairRelayBridge(hubBase, token, deviceID, secret string) (*websocket.Conn, error) {
	u, err := url.Parse(hubBase)
	if err != nil {
		return nil, fmt.Errorf("bad hub URL: %w", err)
	}
	u.Path = "/agent"
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()

	ws, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return nil, fmt.Errorf("dial hub agent port: %w", err)
	}
	req, _ := json.Marshal(map[string]any{
		"kind": relay.KindPipeReq, "device": deviceID, "secret": secret,
	})
	if err := ws.WriteMessage(websocket.TextMessage, req); err != nil {
		ws.Close()
		return nil, fmt.Errorf("pipe_req: %w", err)
	}
	ws.SetReadDeadline(time.Now().Add(10 * time.Second))
	_, raw, err := ws.ReadMessage()
	if err != nil {
		ws.Close()
		return nil, fmt.Errorf("pipe_ack: %w", err)
	}
	var ack struct {
		Kind  string `json:"kind"`
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &ack); err != nil {
		ws.Close()
		return nil, fmt.Errorf("pipe_ack parse: %w", err)
	}
	ws.SetReadDeadline(time.Time{})
	if ack.Kind == relay.KindPushResult && !ack.OK {
		ws.Close()
		return nil, fmt.Errorf("hub rejected the pipe: %s", ack.Error)
	}
	if ack.Kind != relay.KindPushAck || !ack.OK {
		ws.Close()
		return nil, fmt.Errorf("unexpected hub reply: %s", raw)
	}
	return ws, nil
}

// pairRelayBridgeWithRetry pairs, retrying briefly. The previous session's
// agent socket is closed asynchronously, so a client that reconnects
// immediately (esptool does exactly this across a chip reset) can reach the
// hub before it has finished unpairing and be told "already paired to another
// agent". That is a race, not a real conflict, so a few short retries turn a
// spurious failure into a normal one — while a genuine conflict (a real
// concurrent session) still fails fast after the retries are spent.
func pairRelayBridgeWithRetry(hubBase, token, deviceID, secret string) (*websocket.Conn, error) {
	const attempts = 4
	var err error
	for i := 0; i < attempts; i++ {
		if i > 0 {
			time.Sleep(150 * time.Millisecond)
		}
		var ws *websocket.Conn
		ws, err = pairRelayBridge(hubBase, token, deviceID, secret)
		if err == nil {
			return ws, nil
		}
	}
	return nil, err
}

// serveRelayBridgeClients accepts local connections on ln and gives each one a
// fresh pairing with the remote bridge. Clients are served SEQUENTIALLY: the
// bridge firmware holds one UART session at a time, and one websocket cannot
// carry two concurrent readers.
func serveRelayBridgeClients(ctx context.Context, ln net.Listener, hubBase, token, deviceID, secret string, onErr func(error)) {
	for {
		tcp, err := ln.Accept()
		if err != nil {
			return // listener closed: the caller is shutting down
		}
		if ctx.Err() != nil {
			tcp.Close()
			return
		}
		ws, perr := pairRelayBridgeWithRetry(hubBase, token, deviceID, secret)
		if perr != nil {
			tcp.Close()
			if onErr != nil {
				onErr(perr)
			}
			continue
		}
		_ = pipeConn(ctx, ws, tcp)
		ws.Close() // ends the pairing; the hub unpairs the device for the next client
	}
}

// dialRelayBridge exposes a remote bridge as a local TCP socket on an ephemeral
// 127.0.0.1 port, and returns that port plus a closer.
//
// Used by `upload --ota-mode remote` for bridge targets: the MCU-specific
// uploaders shell out to esptool (socket://) and avrdude (net:) with a socket
// URL, and subprocesses cannot use an in-process net.Conn — so the remote
// bridge becomes a local socket and those tools work unchanged.
func dialRelayBridge(ctx context.Context, hubBase, token, deviceID, secret string) (int, func(), error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, nil, fmt.Errorf("local listen: %w", err)
	}
	go serveRelayBridgeClients(ctx, ln, hubBase, token, deviceID, secret, nil)
	return ln.Addr().(*net.TCPAddr).Port, func() { ln.Close() }, nil
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
			if _, err := url.Parse(hubURL); err != nil {
				return fmt.Errorf("bad --hub: %w", err)
			}
			ln, err := net.Listen("tcp", listenAddr)
			if err != nil {
				return fmt.Errorf("listen on %s: %w", listenAddr, err)
			}
			defer ln.Close()
			printInfo(fmt.Sprintf("Remote bridge %s → local socket %s  (Ctrl-C to stop)",
				colorBold(deviceID), colorTeal(ln.Addr().String())))
			printInfo("Point esptool / avrdude / `companion upload --host` at that address.")

			// Same pairing path as `upload --ota-mode remote` — one call,
			// shared: the handshake used to be copy-pasted here, which is how
			// the two drifted (this one also spawned a goroutine per client
			// while the shared comment said the pipe must be sequential).
			ctx, cancel := context.WithCancel(cmd.Context())
			defer cancel()
			serveRelayBridgeClients(ctx, ln, hubURL, token, deviceID, deviceSecret,
				func(err error) { printError("bridge pipe: " + err.Error()) })
			return nil
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
