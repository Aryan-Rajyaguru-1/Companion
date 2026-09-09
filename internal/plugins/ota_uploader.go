// First-party uploader: companion.uploader.ota — pushes a compiled .bin to any
// ArduinoOTA-capable device (ESP32/ESP8266) over WiFi. This is Companion's
// differentiator and ships as a plugin so third parties can replace or extend
// it with JTAG/OpenOCD/other transports.
package plugins

import (
	"context"
	"fmt"
	"io"
	"strings"

	"github.com/companion-ide/companion-cli/internal/ota"
)

// otaUploader is the built-in ArduinoOTA uploader plugin.
type otaUploader struct{}

func (*otaUploader) ID() string      { return "companion.uploader.ota" }
func (*otaUploader) Name() string    { return "ArduinoOTA Wireless Uploader" }
func (*otaUploader) Version() string { return "1.0.0" }
func (*otaUploader) Init(cfg PluginConfig) error {
	return nil
}

// SupportsFQBN claims auto-OTA-capable cores.
func (*otaUploader) SupportsFQBN(fqbn string) bool {
	return strings.HasPrefix(fqbn, "esp32:") || strings.HasPrefix(fqbn, "esp8266:")
}

// Upload streams the firmware image to the device using ota.Push.
func (*otaUploader) Upload(ctx context.Context, opts UploadOptions, w io.Writer) error {
	if opts.Host == "" {
		return fmt.Errorf("no OTA host — pass --host <ip> or use `companion ota discover`")
	}
	port := opts.Port
	if port <= 0 {
		port = 3232
	}
	if err := ota.Probe(opts.Host, port); err != nil {
		return err
	}

	// Password travels through ExtraFlags as "ota-password=<value>".
	password := ""
	for _, f := range opts.ExtraFlags {
		if strings.HasPrefix(f, "ota-password=") {
			password = strings.TrimPrefix(f, "ota-password=")
		}
	}

	fmt.Fprintf(w, "» Streaming firmware to %s:%d via ArduinoOTA\n", opts.Host, port)
	return ota.Push(ctx, ota.Options{
		ImagePath:  opts.BinaryPath,
		DeviceIP:   opts.Host,
		DevicePort: port,
		Password:   password,
		OnProgress: func(sent, total int64) {
			fmt.Fprintf(w, "\r  OTA: %d / %d bytes (%.0f%%)   ",
				sent, total, float64(sent)/float64(total)*100)
		},
		OnMessage: func(s string) { fmt.Fprintf(w, "  %s\n", s) },
	})
}
