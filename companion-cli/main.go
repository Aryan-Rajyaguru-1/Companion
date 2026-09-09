// Companion CLI
// An original command-line tool for the Companion IDE wireless Arduino programmer.
// Inspired by the arduino-cli architecture but written entirely from scratch.
//
// License: MIT — fully owned by you, no GPL obligations.
//
// Architecture overview (inspired by arduino-cli, not derived):
//   cmd/         — cobra command definitions
//   internal/
//     config/    — YAML config file (~/.companion-cli/config.yaml)
//     boards/    — board index parsing, platform install/search
//     compiler/  — GCC toolchain invocation, build pipeline
//     libraries/ — library index, install, resolve
//     uploader/  — WiFi bridge uploader (TCP control protocol)
//     bridge/    — TCP bridge client + serial monitor

package main

import (
	"github.com/companion-ide/companion-cli/cmd"
)

func main() {
	cmd.Execute()
}
