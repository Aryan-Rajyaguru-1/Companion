package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/companion-ide/companion-cli/internal/sketch"
	"github.com/spf13/cobra"
)

// ── Profile command group ────────────────────────────────────────
//
// Profiles pin a board + library set in sketch.yaml so any teammate (or CI)
// reproduces the exact build with `companion compile --profile <name>`.

func newProfileCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "profile",
		Short: "Manage per-sketch build profiles (sketch.yaml)",
		Long: `Profiles pin a target board and library set inside the sketch's
sketch.yaml so builds are reproducible and shareable.

Example sketch.yaml:
  default_profile: prod
  profiles:
    prod:
      fqbn: esp32:esp32:esp32
      port: 192.168.4.1:3333
      libraries:
        - WiFiManager@2.0.17

Then build with:  companion compile --profile prod`,
	}
	cmd.AddCommand(
		newProfileNewCmd(),
		newProfileListCmd(),
		newProfileDeleteCmd(),
		newProfileSetDefaultCmd(),
		newProfileLibCmd(),
	)
	return cmd
}

func profileSketchDir(args []string) (string, error) {
	dir := "."
	if len(args) > 0 {
		dir = args[0]
	}
	abs, err := filepath.Abs(dir)
	if err != nil {
		return "", err
	}
	if info, err := os.Stat(abs); err != nil || !info.IsDir() {
		return "", fmt.Errorf("not a directory: %s", abs)
	}
	return abs, nil
}

func newProfileDeleteCmd() *cobra.Command {
	return &cobra.Command{
		Use:     "delete <name> [sketch-dir]",
		Aliases: []string{"remove", "rm"},
		Short:   "Delete a profile",
		Args:    cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args[1:])
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			if _, ok := sf.Profiles[args[0]]; !ok {
				return fmt.Errorf("profile %q not found", args[0])
			}
			delete(sf.Profiles, args[0])
			if sf.DefaultProfile == args[0] {
				sf.DefaultProfile = ""
			}
			return sf.SaveTo(dir)
		},
	}
}

func newProfileSetDefaultCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "set-default <name> [sketch-dir]",
		Short: "Set which profile is used when --profile is omitted",
		Args:  cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args[1:])
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			if _, ok := sf.Profiles[args[0]]; !ok {
				return fmt.Errorf("profile %q not found", args[0])
			}
			sf.DefaultProfile = args[0]
			if err := sf.SaveTo(dir); err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Default profile is now %s", colorBold(args[0])))
			return nil
		},
	}
}

func newProfileNewCmd() *cobra.Command {
	var (
		fqbn string
		port string
	)
	cmd := &cobra.Command{
		Use:   "new <name> [sketch-dir]",
		Short: "Create a new build profile",
		Args:  cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args[1:])
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			sf.SetProfile(args[0], sketch.Profile{FQBN: fqbn, Port: port})
			if err := sf.SaveTo(dir); err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Profile %s created in %s",
				colorBold(args[0]), colorDim(filepath.Join(dir, "sketch.yaml"))))
			return nil
		},
	}
	cmd.Flags().StringVar(&fqbn, "fqbn", "", "Fully Qualified Board Name for this profile")
	cmd.Flags().StringVar(&port, "port", "", "Default bridge host:port for this profile")
	_ = cmd.MarkFlagRequired("fqbn")
	return cmd
}

func newProfileListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list [sketch-dir]",
		Short: "List profiles defined in sketch.yaml",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args)
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			switch {
			case len(sf.Profiles) == 0 && sf.FQBN != "":
				fmt.Printf("  %-16s fqbn=%s %s\n", colorBold("(legacy)"), colorTeal(sf.FQBN), colorDim("(add named profiles for reproducible builds)"))
			case len(sf.Profiles) == 0:
				printInfo("No profiles — create one: companion profile new myboard --fqbn arduino:avr:uno")
			default:
				for name, p := range sf.Profiles {
					marker := " "
					if name == sf.DefaultProfile {
						marker = "*"
					}
					fmt.Printf(" %s%-15s fqbn=%s", marker, colorBold(name), colorTeal(p.FQBN))
					if len(p.Libraries) > 0 {
						fmt.Printf("  libs=[%s]", strings.Join(p.Libraries, ", "))
					}
					fmt.Println()
				}
			}
			return nil
		},
	}
}
func newProfileLibCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "lib",
		Short: "Pin or unpin libraries in a profile",
	}
	cmd.AddCommand(newProfileLibAddCmd(), newProfileLibRemoveCmd())
	return cmd
}

func newProfileLibAddCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "add <profile> <library[@version]> [sketch-dir]",
		Short: "Pin a library to a profile",
		Args:  cobra.RangeArgs(2, 3),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args[2:])
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			p, err := sf.Resolve(args[0])
			if err != nil {
				return err
			}
			if !p.AddLibrary(args[1]) {
				printWarn(fmt.Sprintf("%s already pinned", args[1]))
				return nil
			}
			sf.SetProfile(args[0], *p)
			if err := sf.SaveTo(dir); err != nil {
				return err
			}
			printSuccess(fmt.Sprintf("Pinned %s to profile %s", colorTeal(args[1]), colorBold(args[0])))
			return nil
		},
	}
}

func newProfileLibRemoveCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "remove <profile> <library> [sketch-dir]",
		Short: "Unpin a library from a profile",
		Args:  cobra.RangeArgs(2, 3),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir, err := profileSketchDir(args[2:])
			if err != nil {
				return err
			}
			sf, err := sketch.Load(dir)
			if err != nil {
				return err
			}
			p, err := sf.Resolve(args[0])
			if err != nil {
				return err
			}
			if !p.RemoveLibrary(args[1]) {
				return fmt.Errorf("%q is not pinned in profile %q", args[1], args[0])
			}
			sf.SetProfile(args[0], *p)
			return sf.SaveTo(dir)
		},
	}
}
