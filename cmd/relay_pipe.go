package cmd

import (
	"context"
	"github.com/companion-ide/companion-cli/internal/fleet"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/companion-ide/companion-cli/internal/relay"
	"net/http"
	"time"
)

// relayPushOptions carries CLI-level tuning for the agent-side wire behaviour.
// Defaults are zero values; helpers apply sane fallbacks. Frame size stays
// on the shared stream engine (ota.StreamOptions.ChunkBytes) so transports
// share one data-phase implementation.
type relayPushOptions struct {
	// chunkBytes caps the data chunk size on this push (smaller = gentler
	// on long-RTT paths like Cloudflare tunnels). ≤0 keeps the legacy
	// 1024-byte frame.
	chunkBytes int
	// ackTimeout overrides the per-chunk ACK wait.
	ackTimeout time.Duration
}

// RelayPushFunc builds a fleet.PushFunc that pushes imagePath to one registry
// device through the relay hub (remote OTA). It mirrors `relay push`: dial
// the agent port, send push_req carrying the device's stored Secret, stream
// the image with PushDevice, then send push_done so the hub clears the
// pairing. hubBase is the --hub base URL (ws:// or wss://); token is the
// agent token (COMPANION_RELAY_AGENTS_TOKEN fallback handled by the caller).
func RelayPushFunc(hubBase, token, imagePath string) fleet.PushFunc {
	return RelayPushFuncOpts(hubBase, token, imagePath, nil)
}

// RelayPushFuncOpts is RelayPushFunc with caller-supplied stream tuning, so
// the interactive `upload` and `ota upload` controllers can pass an
// OnProgress/OnMessage callback (fleet/unattended pushes pass nil).
func RelayPushFuncOpts(hubBase, token, imagePath string, so *ota.StreamOptions) fleet.PushFunc {
	return func(ctx context.Context, d fleet.Device) error {
		_, _, err := relayPushOne(ctx, hubBase, token, d, imagePath, so)
		return err
	}
}

// relayHTTPServer is a thin net/http wrapper so cmd stays stdlib-only
// (the relay package itself exposes only the Handler).
type relayHTTPServer struct {
	addr string
	h    http.Handler
}

func (s *relayHTTPServer) serve() error {
	srv := &http.Server{Addr: s.addr, Handler: s.h}
	return srv.ListenAndServe()
}

// agentPipe adapts the agent websocket into a net.Conn for PushDevice.
// Binary frames carry the data stream; text/protocol frames are swallowed
// (same demux the loopback test validates).
type agentPipeAddr struct{}

func (agentPipeAddr) Network() string { return "relay" }
func (agentPipeAddr) String() string  { return "relay-agent-pipe" }

// relayPushOne pushes to one device over the relay and reports what the board
// was running (plus its LAN address) at pairing time.
//
// The wire sequence now lives in internal/relay.PushToDevice, because the
// uploader plugin needs the identical exchange and cmd is not importable from
// a plugin package. This wrapper only maps a registry entry (whose secret lives
// in the registry) onto that call.
func relayPushOne(ctx context.Context, hubBase, token string, d fleet.Device, imagePath string, so *ota.StreamOptions) (version, ip string, err error) {
	info, err := relay.PushToDevice(ctx, relay.PushRequest{
		Hub:       hubBase,
		Token:     token,
		Device:    d.Key(),
		Secret:    d.Secret,
		ImagePath: imagePath,
		Stream:    so,
	})
	return info.Version, info.IP, err
}
