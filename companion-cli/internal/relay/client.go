package relay

import (
	"context"
	"io"
	"net"
	"time"

	"github.com/companion-ide/companion-cli/internal/ota"
)

// The relay pipe speaks the same ArduinoOTA data-phase protocol as LAN
// pushes (internal/ota) — bare decimal ACK per 1 KiB chunk, bare final "OK"
// — so the device firmware shares one Update state machine for both LAN and
// remote pushes. The wire protocol now lives in exactly one place
// (ota.PushStream); this side only supplies the transport-tuned knobs:
// stop-and-wait over an internet tunnel is ~0.6s per KiB, so the ACK and
// final-OK windows are wider than the LAN defaults.
const (
	ackTimeout    = 60 * time.Second
	finalOKWindow = 120 * time.Second
	writeWait     = 60 * time.Second
)

// PushDevice pushes a firmware image to a remote device over the paired
// data pipe (hub-relayed), using the remote-tuned defaults.
func PushDevice(ctx context.Context, data net.Conn, img io.ReadSeeker, size int64) error {
	return PushDeviceStream(ctx, data, img, size, nil)
}

// PushDeviceStream is PushDevice with caller-supplied tuning — the controller
// side (cmd) passes OnProgress/OnMessage here so a 10+ minute tunnel push
// reports progress instead of looking hung. SendHeader is always forced on:
// the relay path has no UDP invite, so the device parses "<size> <md5>\n"
// from the byte stream itself.
func PushDeviceStream(ctx context.Context, data net.Conn, img io.ReadSeeker, size int64, so *ota.StreamOptions) error {
	// Defaults are 60s per chunk / 120s final-OK / 60s write — the same
	// windows the remote constants below encode, so a nil entry point gets
	// the tunnel-tuned behaviour without duplicating the fill-in logic.
	so = ota.DefaultStreamOptions(so)
	so.SendHeader = true
	return ota.PushStream(ctx, data, img, size, so)
}
