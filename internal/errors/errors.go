// Package errors defines structured, typed error codes for Companion CLI.
//
// Design mirrors arduino-cli's approach of replacing bare string errors with
// machine-parseable codes + actionable suggestions — so the IDE can:
//   1. Display error codes in the console (searchable in docs)
//   2. Generate auto-fix suggestions without fragile regex
//   3. Translate messages to other languages via code lookup
//   4. Route errors to the right UI panel automatically
//
// Pattern from: arduino-cli/rpc/cc/arduino/cli/commands/v1/commands.proto
package errors

import (
	"fmt"
	"strings"
)

// ── Error codes ────────────────────────────────────────────────────

// Code is a machine-readable error identifier.
type Code string

const (
	// Compile errors
	ErrCompile         Code = "COMPILE_ERROR"
	ErrCompileWarning  Code = "COMPILE_WARNING"
	ErrMissingLibrary  Code = "MISSING_LIBRARY"
	ErrMissingHeader   Code = "MISSING_HEADER"
	ErrSyntaxError     Code = "SYNTAX_ERROR"
	ErrUndeclaredIdent Code = "UNDECLARED_IDENTIFIER"
	ErrTypeMismatch    Code = "TYPE_MISMATCH"
	ErrLinkError       Code = "LINK_ERROR"

	// Board / FQBN errors
	ErrInvalidFQBN      Code = "INVALID_FQBN"
	ErrBoardNotFound    Code = "BOARD_NOT_FOUND"
	ErrCoreNotInstalled Code = "CORE_NOT_INSTALLED"
	ErrToolchainMissing Code = "TOOLCHAIN_MISSING"

	// Upload errors
	ErrUploadFailed   Code = "UPLOAD_FAILED"
	ErrBridgeTimeout  Code = "BRIDGE_TIMEOUT"
	ErrBridgeRefused  Code = "BRIDGE_REFUSED"
	ErrBinaryNotFound Code = "BINARY_NOT_FOUND"

	// Config errors
	ErrConfigInvalid Code = "CONFIG_INVALID"
	ErrConfigMissing Code = "CONFIG_MISSING"

	// General
	ErrInternal Code = "INTERNAL_ERROR"
	ErrNotFound Code = "NOT_FOUND"
	ErrTimeout  Code = "TIMEOUT"
)

// ── Severity ───────────────────────────────────────────────────────

type Severity string

const (
	SeverityError   Severity = "error"
	SeverityWarning Severity = "warning"
	SeverityNote    Severity = "note"
)

// ── CompanionError ─────────────────────────────────────────────────

// CompanionError is a structured, machine-readable error.
// All functions in companion-cli should return this type instead of
// bare strings so the IDE can properly route and display them.
type CompanionError struct {
	Code       Code              `json:"code"`
	Severity   Severity          `json:"severity"`
	Message    string            `json:"message"`
	Suggestion string            `json:"suggestion,omitempty"`
	File       string            `json:"file,omitempty"`
	Line       int               `json:"line,omitempty"`
	Column     int               `json:"column,omitempty"`
	Context    map[string]string `json:"context,omitempty"`
	Wrapped    error             `json:"-"`
}

func (e *CompanionError) Error() string {
	var b strings.Builder
	b.WriteString(fmt.Sprintf("[%s] %s", e.Code, e.Message))
	if e.Suggestion != "" {
		b.WriteString(fmt.Sprintf("\n  Suggestion: %s", e.Suggestion))
	}
	if e.File != "" {
		loc := e.File
		if e.Line > 0 {
			loc = fmt.Sprintf("%s:%d", loc, e.Line)
			if e.Column > 0 {
				loc = fmt.Sprintf("%s:%d", loc, e.Column)
			}
		}
		b.WriteString(fmt.Sprintf("\n  Location: %s", loc))
	}
	return b.String()
}

func (e *CompanionError) Unwrap() error { return e.Wrapped }

// Is allows errors.Is() matching on Code
func (e *CompanionError) Is(target error) bool {
	t, ok := target.(*CompanionError)
	if !ok {
		return false
	}
	return e.Code == t.Code
}

// ── Constructors ───────────────────────────────────────────────────

func New(code Code, message string) *CompanionError {
	return &CompanionError{Code: code, Severity: SeverityError, Message: message}
}

func Newf(code Code, format string, args ...interface{}) *CompanionError {
	return New(code, fmt.Sprintf(format, args...))
}

func Wrap(code Code, err error, message string) *CompanionError {
	return &CompanionError{
		Code:     code,
		Severity: SeverityError,
		Message:  message,
		Wrapped:  err,
	}
}

func Wrapf(code Code, err error, format string, args ...interface{}) *CompanionError {
	return Wrap(code, err, fmt.Sprintf(format, args...))
}

// ── Fluent builder methods ─────────────────────────────────────────

func (e *CompanionError) WithSuggestion(s string) *CompanionError {
	e.Suggestion = s
	return e
}

func (e *CompanionError) WithLocation(file string, line, col int) *CompanionError {
	e.File = file
	e.Line = line
	e.Column = col
	return e
}

func (e *CompanionError) WithContext(key, value string) *CompanionError {
	if e.Context == nil {
		e.Context = map[string]string{}
	}
	e.Context[key] = value
	return e
}

func (e *CompanionError) AsWarning() *CompanionError {
	e.Severity = SeverityWarning
	return e
}

// ── Well-known error factories ─────────────────────────────────────
//
// These replace the ad-hoc fmt.Errorf() calls throughout the codebase
// with typed, actionable errors that the IDE can handle intelligently.

func MissingLibrary(libName string) *CompanionError {
	return New(ErrMissingLibrary, fmt.Sprintf("Library '%s' is not installed", libName)).
		WithSuggestion(fmt.Sprintf("Install it: companion lib install \"%s\"", libName)).
		WithContext("library", libName)
}

func MissingHeader(header string) *CompanionError {
	return New(ErrMissingHeader, fmt.Sprintf("Cannot find header file: %s", header)).
		WithSuggestion("Check that the library providing this header is installed").
		WithContext("header", header)
}

func InvalidFQBN(fqbn string) *CompanionError {
	return New(ErrInvalidFQBN, fmt.Sprintf("Invalid board name (FQBN): %s", fqbn)).
		WithSuggestion("Format: vendor:architecture:board  e.g. arduino:avr:uno").
		WithContext("fqbn", fqbn)
}

func BoardNotFound(fqbn string) *CompanionError {
	return New(ErrBoardNotFound, fmt.Sprintf("Board '%s' is not installed", fqbn)).
		WithSuggestion(fmt.Sprintf("Install the platform first: companion board install %s", fqbn)).
		WithContext("fqbn", fqbn)
}

func CoreNotInstalled(platform string) *CompanionError {
	return New(ErrCoreNotInstalled, fmt.Sprintf("Platform '%s' is not installed", platform)).
		WithSuggestion(fmt.Sprintf("Install: companion board install %s", platform)).
		WithContext("platform", platform)
}

func ToolchainMissing(toolchain string) *CompanionError {
	return New(ErrToolchainMissing, fmt.Sprintf("Toolchain not found: %s", toolchain)).
		WithSuggestion("Run 'companion board update-index' then install the board platform")
}

func UploadFailed(reason string) *CompanionError {
	return New(ErrUploadFailed, fmt.Sprintf("Upload failed: %s", reason)).
		WithSuggestion("Check that the bridge is powered and on the correct IP address")
}

func BridgeTimeout(host string, port int) *CompanionError {
	return New(ErrBridgeTimeout, fmt.Sprintf("Bridge at %s:%d did not respond", host, port)).
		WithSuggestion("Ensure the ESP32 bridge is powered and connected to WiFi").
		WithContext("host", host).
		WithContext("port", fmt.Sprintf("%d", port))
}

// ── Error analysis helpers ─────────────────────────────────────────

// AnalyzeGCCOutput scans raw GCC output and returns a slice of structured
// CompanionErrors. This replaces ad-hoc regex parsing scattered across the codebase.
func AnalyzeGCCOutput(output string) []*CompanionError {
	var errs []*CompanionError
	seen := map[string]bool{}

	lines := strings.Split(output, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		// Check for known pattern matches that imply specific error codes
		ce := classifyGCCLine(line)
		if ce != nil {
			key := fmt.Sprintf("%s:%d:%d:%s", ce.File, ce.Line, ce.Column, ce.Message)
			if !seen[key] {
				seen[key] = true
				errs = append(errs, ce)
			}
		}
	}
	return errs
}

// classifyGCCLine applies known patterns to a GCC output line to infer
// the most specific error code and suggestion.
func classifyGCCLine(line string) *CompanionError {
	lower := strings.ToLower(line)

	// "No such file or directory" → missing header
	if strings.Contains(lower, "no such file or directory") {
		if idx := strings.Index(line, "#include"); idx >= 0 {
			hdr := extractQuoted(line[idx:])
			if hdr != "" {
				return MissingHeader(hdr)
			}
		}
		// "fatal error: WiFiNINA.h: No such file or directory" — extract
		// the header directly from the fatal-error message.
		if idx := strings.Index(line, "fatal error:"); idx >= 0 {
			rest := line[idx+len("fatal error:"):]
			rest = strings.TrimSpace(rest)
			if colon := strings.Index(rest, ":"); colon > 0 {
				hdr := strings.TrimSpace(rest[:colon])
				if hdr != "" && !strings.Contains(hdr, " ") {
					return MissingHeader(hdr)
				}
			}
		}
		return New(ErrMissingHeader, line)
	}

	// "was not declared in this scope" → undeclared identifier
	if strings.Contains(lower, "was not declared in this scope") {
		return New(ErrUndeclaredIdent, line).
			WithSuggestion("Check spelling, case, and that the relevant #include is present")
	}

	// "undefined reference to" → link error (often a missing library)
	if strings.Contains(lower, "undefined reference to") {
		sym := extractSingleQuoted(line)
		ce := New(ErrLinkError, line)
		if sym != "" {
			ce.WithSuggestion(fmt.Sprintf("Symbol '%s' is undefined — check that all source files are included", sym))
		}
		return ce
	}

	// "invalid conversion" / "cannot convert" → type mismatch
	if strings.Contains(lower, "invalid conversion") || strings.Contains(lower, "cannot convert") {
		return New(ErrTypeMismatch, line).
			WithSuggestion("Check that variable types match. Arduino's String vs char* is a common cause")
	}

	return nil
}

// ── String helpers ─────────────────────────────────────────────────

func extractQuoted(s string) string {
	for _, pair := range [][2]rune{{'<', '>'}, {'"', '"'}, {'\'', '\''}} {
		open, close := pair[0], pair[1]
		start := strings.IndexRune(s, open)
		if start < 0 {
			continue
		}
		end := strings.IndexRune(s[start+1:], close)
		if end >= 0 {
			return s[start+1 : start+1+end]
		}
	}
	return ""
}

func extractSingleQuoted(s string) string {
	start := strings.Index(s, "'")
	if start < 0 {
		return ""
	}
	end := strings.Index(s[start+1:], "'")
	if end < 0 {
		return ""
	}
	return s[start+1 : start+1+end]
}
