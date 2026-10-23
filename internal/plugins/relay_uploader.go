package plugins

// relayUploader is the first-party uploader plugin for the Companion relay
// transport: companion.uploader.relay.
//
// It exists so the relay is a PLUGIN rather than a special case bolted into the
// upload command. Anything that consumes Companion's plugin API — the CLI, a
// third-party tool, a future IDE — can now list and invoke "push this image to
// a board that dials out through my hub" without knowing anything about the
// relay, and a user can swap in a JTAG/OpenOCD uploader beside it.
//
// Selection is EXPLICIT (--uploader companion.uploader.relay), never automatic:
// UploaderFor() returns the first uploader claiming an FQBN, and a relay
// uploader claiming every ESP32 would silently shadow the LAN ArduinoOTA
// uploader that most users want. It is registered last for the same reason.
//
// Configuration comes from the environment rather than plugin config, matching
// the rest of the relay surface and keeping secrets out of config.yaml:
//   COMPANION_RELAY_HUB            wss://host
//   COMPANION_RELAY_AGENTS_TOKEN   agent token
//   COMPANION_RELAY_DEVICE_SECRET  the target board's provisioning secret
// The device id is the uploader's Host (so `--host esp32-node-01` selects it),
// matching how the other uploaders take their target.
import (
	"context"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/companion-ide/companion-cli/internal/relay"
)

type relayUploader struct {
	cfg PluginConfig
}

func (*relayUploader) ID() string      { return "companion.uploader.relay" }
func (*relayUploader) Name() string    { return "Companion Relay Uploader (push over the internet)" }
func (*relayUploader) Version() string { return "1.0.0" }

func (u *relayUploader) Init(cfg PluginConfig) error {
	u.cfg = cfg
	return nil
}

// SupportsFQBN claims every core: the relay protocol is transport-level, and
// the board (not the CLI) decides what it accepts. The uploader is opt-in, so
// claiming everything costs nothing.
func (*relayUploader) SupportsFQBN(string) bool { return true }

func (u *relayUploader) Upload(ctx context.Context, opts UploadOptions, w io.Writer) error {
	hub := firstNonEmpty(
		os.Getenv("COMPANION_RELAY_HUB"),
		u.cfg.Options["relay_hub"],
	)
	if hub == "" {
		return fmt.Errorf("relay uploader needs a hub: set COMPANION_RELAY_HUB or pass --relay-hub")
	}
	device := strings.TrimSpace(opts.Host)
	if device == "" {
		return fmt.Errorf("relay uploader needs a device id: pass --host <device-id>")
	}
	token := firstNonEmpty(os.Getenv("COMPANION_RELAY_AGENTS_TOKEN"), u.cfg.Options["relay_token"])
	if token == "" {
		return fmt.Errorf("relay uploader needs an agent token: set COMPANION_RELAY_AGENTS_TOKEN")
	}
	secret := firstNonEmpty(os.Getenv("COMPANION_RELAY_DEVICE_SECRET"), u.cfg.Options["relay_device_secret"])
	if secret == "" {
		return fmt.Errorf("relay uploader needs the device's provisioning secret: set COMPANION_RELAY_DEVICE_SECRET " +
			"(the board prints it on first boot). It is never taken from a command-line flag — a flag value is visible in ps output.")
	}
	if opts.BinaryPath == "" {
		return fmt.Errorf("relay uploader needs a built image (compile first, or pass --no-verify with a --binary)")
	}
	// Stream carries the uploader's progress writer so a plugin consumer sees
	// the same output the CLI prints.
	stream := &ota.StreamOptions{
		OnProgress: func(sent, total int64) {
			if total > 0 {
				fmt.Fprintf(w, "\r  %d%% (%d/%d KB)", sent*100/total, sent/1024, total/1024)
			}
		},
	}
	info, err := relay.PushToDevice(ctx, relay.PushRequest{
		Hub: hub, Token: token, Device: device, Secret: secret,
		ImagePath: opts.BinaryPath, Stream: stream,
	})
	if err != nil {
		return err
	}
	fmt.Fprintf(w, "\n  ✓ %s is now running %s", device, versionOrUnknown(info.Version))
	return nil
}

// versionOrUnknown keeps a missing version honest: "" means the board did not
// report one, which is NOT the same as being up to date.
func versionOrUnknown(v string) string {
	if strings.TrimSpace(v) == "" {
		return "unknown version"
	}
	return v
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v)
		}
	}
	return ""
}
