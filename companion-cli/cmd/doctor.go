package cmd

// doctor — one command that answers "why doesn't my upload work?".
//
// Every check mirrors something an upload actually does, so a green run means
// the pieces an upload touches are present. A missing OPTIONAL tool is a
// warning (an AVR-only user never needs esptool); a missing board toolchain is
// a failure, because nothing compiles without one.

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/companion-ide/companion-cli/internal/uploader"
	"github.com/spf13/cobra"
)

func newDoctorCmd() *cobra.Command {
	var hub string

	cmd := &cobra.Command{
		Use:   "doctor",
		Short: "Check the toolchain, tools and credentials an upload depends on",
		Long: `Diagnose the environment Companion's compile and upload paths depend on,
in the order a first upload would hit it:

  config      where it lives, and who can read it
  toolchain   installed board platforms (nothing compiles without one)
  tools       esptool / avrdude / Python — the same resolution an upload uses
  relay       the hub's /health, when --hub is given (optional)

Exit status is non-zero when a required piece is missing.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, cfgPath, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return err
			}
			failures := 0

			fmt.Printf("\n%s\n", colorTeal(colorBold("Companion doctor")))

			// ── Config ───────────────────────────────────────────────
			fmt.Printf("\n%s\n", colorBold("Config"))
			if fi, serr := os.Stat(cfgPath); serr == nil {
				if mode := fi.Mode().Perm(); mode&0o077 != 0 {
					printWarn(fmt.Sprintf("%s — mode %04o; it can hold tokens (chmod 600 it)", cfgPath, mode))
				} else {
					printSuccess(fmt.Sprintf("%s (mode %04o)", cfgPath, mode))
				}
			} else {
				printInfo(fmt.Sprintf("%s — not created yet, defaults in use", cfgPath))
			}
			printStep("packages:  " + cfg.PackagesDir())
			printStep("libraries: " + cfg.LibrariesDir())

			// ── Toolchain ────────────────────────────────────────────
			fmt.Printf("\n%s\n", colorBold("Board toolchain"))
			installed, lerr := boards.NewManager(cfg).ListInstalled()
			switch {
			case lerr != nil:
				failures++
				printError("cannot read installed platforms: " + lerr.Error())
			case len(installed) == 0:
				failures++
				printError("no board platform installed — nothing can compile yet")
				printStep("fix: companion board update-index")
				printStep("     companion board install esp32:esp32")
			default:
				ids := make([]string, 0, len(installed))
				for _, p := range installed {
					ids = append(ids, p.ID)
				}
				printSuccess(fmt.Sprintf("%d platform(s): %s", len(installed), strings.Join(ids, ", ")))
			}

			// ── External tools ───────────────────────────────────────
			fmt.Printf("\n%s\n", colorBold("External tools"))
			for _, t := range uploader.Tools(cfg) {
				if t.Found {
					printSuccess(fmt.Sprintf("%s — %s", t.Name, t.Detail))
					continue
				}
				printWarn(fmt.Sprintf("%s not usable (%s) — needed for %s", t.Name, t.Detail, t.Needed))
				if t.Hint != "" {
					printStep("fix: " + t.Hint)
				}
			}

			// ── Relay (optional) ─────────────────────────────────────
			if hub != "" {
				fmt.Printf("\n%s\n", colorBold("Relay"))
				if err := doctorCheckHub(hub); err != nil {
					printWarn("hub check: " + err.Error())
				}
			}

			fmt.Println()
			if failures > 0 {
				return fmt.Errorf("doctor found %d blocking problem(s)", failures)
			}
			printSuccess("no blocking problems — the pieces an upload needs are present")
			return nil
		},
	}
	cmd.Flags().StringVar(&hub, "hub", "",
		"also check a relay hub's /health (ws:// or wss:// URL); set COMPANION_RELAY_AGENTS_TOKEN to see its device inventory")
	return cmd
}

// doctorCheckHub reports whether a relay hub answers /health. Unauthenticated
// callers get liveness only (the hub deliberately hides its inventory), so a
// token in the environment upgrades the answer to the online device list.
func doctorCheckHub(hub string) error {
	u, err := url.Parse(hub)
	if err != nil {
		return fmt.Errorf("bad --hub %q: %w", hub, err)
	}
	switch u.Scheme {
	case "ws":
		u.Scheme = "http"
	case "wss":
		u.Scheme = "https"
	case "http", "https":
		// already an HTTP(S) URL — fine
	default:
		return fmt.Errorf("unexpected scheme %q — use ws:// or wss://", u.Scheme)
	}
	u.Path = "/health"
	q := u.Query()
	authed := false
	if tok := relayTokenFromEnv(); tok != "" {
		q.Set("token", tok)
		authed = true
	}
	u.RawQuery = q.Encode()

	cl := &http.Client{Timeout: 12 * time.Second}
	full := u.String()
	resp, err := cl.Get(full)
	if err != nil {
		return fmt.Errorf("%s unreachable: %s", u.Host,
			redactURLToken(err.Error(), full, q.Encode()))
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("HTTP %d from %s", resp.StatusCode, u.Host)
	}
	var health struct {
		OK      bool `json:"ok"`
		Devices []struct {
			ID string `json:"id"`
		} `json:"devices"`
	}
	if err := json.Unmarshal(body, &health); err != nil || !health.OK {
		return fmt.Errorf("unexpected body from %s: %s", u.Host, strings.TrimSpace(string(body)))
	}
	if len(health.Devices) > 0 {
		ids := make([]string, 0, len(health.Devices))
		for _, d := range health.Devices {
			ids = append(ids, d.ID)
		}
		printSuccess(fmt.Sprintf("%s is up — %d device(s) online: %s",
			u.Host, len(ids), strings.Join(ids, ", ")))
		return nil
	}
	if !authed {
		printSuccess(u.Host + " is up (no token set, so the device list is hidden — set COMPANION_RELAY_AGENTS_TOKEN to see it)")
		return nil
	}
	printSuccess(u.Host + " is up — no devices online right now")
	return nil
}

// relayTokenFromEnv reads either relay token from the environment. Both are
// tried because /health accepts either, and both can see the inventory.
func relayTokenFromEnv() string {
	for _, k := range []string{"COMPANION_RELAY_AGENTS_TOKEN", "COMPANION_RELAY_DEVICES_TOKEN"} {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return ""
}

// redactURLToken replaces a query string inside error text with a placeholder.
// Net errors quote the full URL they failed on, and that URL carries the relay
// token — this text is printed to terminals and pasted into bug reports, so
// the secret must never survive into it.
func redactURLToken(text, fullURL, query string) string {
	if query == "" || fullURL == "" {
		return text
	}
	return strings.Replace(text, fullURL, strings.Replace(fullURL, query, "token=…", 1), 1)
}
