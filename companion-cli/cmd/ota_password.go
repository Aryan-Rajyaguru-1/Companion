package cmd

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

// resolveOTAPassword implements the audit-F002 secret precedence for OTA
// credentials: explicit --ota-password flag wins, then the
// COMPANION_OTA_PASSWORD environment variable, then --ota-password-stdin.
// The flag is kept for scripting but the help text steers users toward the
// safer paths (a password in argv is visible via ps and shell history).
func resolveOTAPassword(cmd *cobra.Command, flagVal, stdinVal string, stdin bool) (string, error) {
	if flagVal != "" {
		return flagVal, nil
	}
	if env := os.Getenv("COMPANION_OTA_PASSWORD"); env != "" {
		return env, nil
	}
	if stdin {
		raw, err := io.ReadAll(os.Stdin)
		if err != nil {
			return "", fmt.Errorf("read OTA password from stdin: %w", err)
		}
		pw := strings.TrimSpace(string(raw))
		if pw == "" {
			return "", fmt.Errorf("empty OTA password on stdin")
		}
		return pw, nil
	}
	_ = stdinVal
	return "", nil
}
