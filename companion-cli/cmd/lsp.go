package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	"github.com/spf13/cobra"
)

// newLSPCmd launches clangd with a fresh compile_commands.json for the sketch.
// This closes the Arduino-cli #849 gap end-to-end: real language-server
// IntelliSense (go-to-definition, hover, diagnostics) inside any editor that
// speaks the Language Server Protocol.
func newLSPCmd() *cobra.Command {
	var fqbnFlag string
	cmd := &cobra.Command{
		Use:   "lsp [sketch-dir]",
		Short: "Launch clangd over a generated compile_commands.json",
		Long: `Generate compile_commands.json for the sketch and hand it to clangd.

  companion lsp [sketch-dir]

The first run compiles the sketch (cached objects make this cheap) and exports
every translation unit's exact compile command into the sketch build folder.
Then clangd is launched with that database, so editors (VS Code, vim, Emacs,
or Companion IDE itself) get real C/C++ IntelliSense.

Install clangd:  apt install clangd   |   brew install llvm   |   winget install llvm`,
		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			dir := "."
			if len(args) > 0 {
				dir = args[0]
			}
			sketchDir, err := filepath.Abs(dir)
			if err != nil {
				return err
			}

			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return fmt.Errorf("config: %w", err)
			}
			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}

			rp, err := applyProfile(cfg, sketchDir, "")
			if err != nil {
				return err
			}
			fqbn := ""
			if rp != nil {
				fqbn = rp.FQBN
			}
			if fqbn == "" {
				fqbn = readSketchFQBN(sketchDir)
			}
			if fqbnFlag != "" {
				fqbn = fqbnFlag // explicit --fqbn wins over sketch.yaml/profile
			}
			if fqbn == "" {
				return fmt.Errorf("no board configured for %s — set fqbn in sketch.yaml or pass --fqbn", sketchDir)
			}

			buildDir := filepath.Join(sketchDir, "build", ".intellisense")
			os.MkdirAll(buildDir, 0o755)

			printInfo(fmt.Sprintf("Generating compile_commands.json for %s…", colorTeal(fqbn)))
			bm := boards.NewManager(cfg)
			cmp := compiler.New(cfg, bm, func(s string) {})
			cmp.SetPlugins(pluginRegistry(cfg))
			result, err := cmp.Build(compiler.Options{
				SketchDir:              sketchDir,
				FQBN:                   fqbn,
				BuildDir:               buildDir,
				Warnings:               "none",
				Verbose:                false,
				LibraryDirs:            profileLibDirs(rp),
				CaptureCompileCommands: true,
			})
			if err != nil {
				return fmt.Errorf("compile: %w", err)
			}
			if result.CompileCommandsPath == "" {
				return fmt.Errorf("compile_commands.json was not produced — check the sketch compiles")
			}
			printSuccess("compile_commands.json ready")

			clangd, err := exec.LookPath("clangd")
			if err != nil {
				return fmt.Errorf("clangd not found in PATH — install it (apt install clangd / brew install llvm)\n"+
					"    compile commands are ready at: %s", result.CompileCommandsPath)
			}

			printInfo(fmt.Sprintf("Launched clangd — serve it to your editor on stdio (build dir: %s)", buildDir))
			c := exec.CommandContext(cmd.Context(), clangd, "--compile-commands-dir="+buildDir)
			c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
			if err := c.Run(); err != nil {
				if cmd.Context().Err() != nil {
					return nil // cancelled (client closed)
				}
				return fmt.Errorf("clangd exited: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&fqbnFlag, "fqbn", "",
		"Fully Qualified Board Name, e.g. esp32:esp32:XIAO_ESP32S3 (overrides sketch.yaml)")
	return cmd
}
