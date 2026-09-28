package cmd

// mcp.go — `companion mcp`: a Model Context Protocol server, so any AI agent
// (Claude Desktop, Cursor, an IDE assistant, your own agent loop) or any
// program can drive the controller over one standard interface.
//
// Design: every tool is a THIN ADAPTER over an existing CLI command, built
// fresh per call from the same constructor the shell uses. No tool re-implements
// compile/upload/relay logic, so an agent and a human cannot get different
// behaviour — the same flags, the same errors, the same safety checks. The
// alternative (tools calling internal packages directly) would fork into a
// second implementation, which is the drift shape that has bitten this project
// twice already (--ota-mode, the relay handshake).
//
// Transport is MCP over stdio: newline-delimited JSON-RPC 2.0, which is what
// desktop MCP hosts spawn.
//
// Safety: this hands the host machine's toolchain to whatever connects, so the
// tools that flash hardware are refused unless the operator opts in with
// --allow-upload. Read-only tools work out of the box. Secrets never appear in
// a tool schema: the relay tools read them from the environment, so an agent
// never handles a credential.

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/spf13/cobra"
)

// mcpProtocolVersion is what we advertise when a client does not ask. If a
// client names a version we echo it back: refusing a newer client's version
// breaks clients that are otherwise compatible.
const mcpProtocolVersion = "2024-11-05"

// ── JSON-RPC plumbing ─────────────────────────────────────────────────────

type mcpRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type mcpError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    any    `json:"data,omitempty"`
}

type mcpResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Result  any             `json:"result,omitempty"`
	Error   *mcpError       `json:"error,omitempty"`
}

// JSON-RPC error codes used here.
const (
	mcpParseError     = -32700
	mcpMethodNotFound = -32601
	mcpInvalidParams  = -32602
)

// mcpTool is one advertised tool: name, description, JSON Schema for its
// arguments, and the handler that runs it.
type mcpTool struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"inputSchema"`

	// destructive marks a tool that writes to the machine's disk or flashes
	// hardware. Those are gated behind --allow-upload.
	destructive bool
	handler     func(ctx context.Context, args map[string]any) (string, error)
}

// mcpServer holds the tool table and the operator's policy.
type mcpServer struct {
	hub         string
	allowUpload bool
	tools       map[string]*mcpTool
	order       []string

	// callMu serialises tool execution: the toolchain is shared, and output
	// from two concurrent compiles would interleave into one transcript.
	callMu sync.Mutex
}

func newMCPServer(hub string, allowUpload bool) *mcpServer {
	s := &mcpServer{hub: hub, allowUpload: allowUpload, tools: map[string]*mcpTool{}}
	for _, t := range s.defaultTools() {
		s.tools[t.Name] = t
		s.order = append(s.order, t.Name)
	}
	return s
}

// ── argument helpers ──────────────────────────────────────────────────────

func strArg(args map[string]any, key string) string {
	if v, ok := args[key].(string); ok {
		return strings.TrimSpace(v)
	}
	return ""
}

func boolArg(args map[string]any, key string) bool {
	v, _ := args[key].(bool)
	return v
}

func intArg(args map[string]any, key string) (int, bool) {
	switch v := args[key].(type) {
	case float64: // JSON numbers decode as float64
		return int(v), true
	case int:
		return v, true
	}
	return 0, false
}

// runCLI builds a fresh command from the same constructor the shell uses and
// runs it with args, returning everything it printed. Fresh per call on
// purpose: a shared command tree would carry flag state from one agent call
// into the next.
//
// Capturing matters more than it looks. The CLI's print helpers write straight
// to os.Stdout with fmt.Println, bypassing cobra's writers — so a plain
// cmd.SetOut() capture returns an empty transcript AND, worse, the command's
// output lands on the protocol channel and corrupts the JSON-RPC stream (the
// client then sees garbage between responses). So os.Stdout/os.Stderr are
// swapped for pipes for the duration of the call and restored afterwards.
// Callers hold callMu, so the process-global swap is never concurrent.
func runCLI(c *cobra.Command, args []string) (string, error) {
	var cobraBuf bytes.Buffer
	c.SetOut(&cobraBuf)
	c.SetErr(&cobraBuf)
	c.SetArgs(args)

	origOut, origErr := os.Stdout, os.Stderr
	outR, outW, err := os.Pipe()
	if err != nil {
		return "", c.Execute()
	}
	errR, errW, err := os.Pipe()
	if err != nil {
		outR.Close()
		outW.Close()
		return "", c.Execute()
	}
	os.Stdout, os.Stderr = outW, errW

	var outBuf, errBuf syncBuffer
	outDone := make(chan struct{})
	errDone := make(chan struct{})
	go func() { io.Copy(&outBuf, outR); close(outDone) }()
	go func() { io.Copy(&errBuf, errR); close(errDone) }()

	runErr := c.Execute()

	outW.Close()
	errW.Close()
	os.Stdout, os.Stderr = origOut, origErr
	<-outDone
	<-errDone
	outR.Close()
	errR.Close()

	var parts []string
	for _, s := range []string{cobraBuf.String(), outBuf.String(), errBuf.String()} {
		// Strip colour: the CLI colours unconditionally, and escape codes in
		// a tool result are noise an LLM has to spend tokens on.
		if t := strings.TrimRight(stripANSI(s), "\n"); t != "" {
			parts = append(parts, t)
		}
	}
	return strings.Join(parts, "\n"), runErr
}

// stripANSI reuses the compile command's own colour regex rather than
// declaring a second one.
func stripANSI(s string) string { return ansiRE.ReplaceAllString(s, "") }

// syncBuffer is a bytes.Buffer safe for the one writer/one reader pair above.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

// ── the tool table ────────────────────────────────────────────────────────

func (s *mcpServer) defaultTools() []*mcpTool {
	return []*mcpTool{
		{
			Name: "companion_doctor",
			Description: "Check the local Companion environment: installed board platforms, " +
				"esptool/avrdude/Python detection, config file permissions. Run this first " +
				"when an upload is about to fail.",
			InputSchema: map[string]any{"type": "object", "properties": map[string]any{}},
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				return runCLI(newDoctorCmd(), nil)
			},
		},
		{
			Name: "companion_list_ports",
			Description: "List serial ports with board-match confidence (which port is likely " +
				"an Uno/ESP32/STM32 board).",
			InputSchema: map[string]any{"type": "object", "properties": map[string]any{}},
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				return runCLI(newBoardCmd(), []string{"list-ports"})
			},
		},
		{
			Name:        "companion_board_list",
			Description: "List installed board platforms and their versions.",
			InputSchema: map[string]any{"type": "object", "properties": map[string]any{}},
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				return runCLI(newBoardCmd(), []string{"list"})
			},
		},
		{
			Name: "companion_compile",
			Description: "Compile an Arduino sketch and return the compiler diagnostics, so the " +
				"caller can read the errors and fix the source.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"sketch_dir":      map[string]any{"type": "string", "description": "sketch folder (defaults to the current directory)"},
					"fqbn":            map[string]any{"type": "string", "description": "board FQBN, e.g. arduino:avr:uno or esp32:esp32:esp32"},
					"main_ino":        map[string]any{"type": "string", "description": "compile only this .ino when the folder holds several sketches"},
					"export_binaries": map[string]any{"type": "boolean", "description": "copy the built binary next to the sketch"},
				},
				"required": []string{"fqbn"},
			},
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				var a []string
				if dir := strArg(args, "sketch_dir"); dir != "" {
					a = append(a, dir)
				}
				a = append(a, "--fqbn", strArg(args, "fqbn"))
				if m := strArg(args, "main_ino"); m != "" {
					a = append(a, "--main-ino", m)
				}
				if boolArg(args, "export_binaries") {
					a = append(a, "--export-binaries")
				}
				return runCLI(newCompileCmd(), a)
			},
		},
		{
			Name: "companion_upload",
			Description: "Compile and upload a sketch to a target through the ESP32 bridge " +
				"(Uno, Nano, STM32, ESP32). Writes to disk and flashes hardware, so it " +
				"needs --allow-upload on the server.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"sketch_dir": map[string]any{"type": "string", "description": "sketch folder (defaults to the current directory)"},
					"binary":     map[string]any{"type": "string", "description": "pre-built binary to flash instead of compiling"},
					"fqbn":       map[string]any{"type": "string", "description": "board FQBN (required when uploading from source)"},
					"mcu":        map[string]any{"type": "string", "description": "esp32 | esp8266 | avr | stm32 | generic"},
					"host":       map[string]any{"type": "string", "description": "bridge address (default 192.168.4.1 in AP mode)"},
					"port":       map[string]any{"type": "integer", "description": "bridge TCP port (default 3333)"},
					"baud":       map[string]any{"type": "integer", "description": "UART baud rate for the upload"},
				},
			},
			destructive: true,
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				var a []string
				if dir := strArg(args, "sketch_dir"); dir != "" {
					a = append(a, dir)
				}
				if b := strArg(args, "binary"); b != "" {
					a = append(a, "--binary", b)
				}
				if f := strArg(args, "fqbn"); f != "" {
					a = append(a, "--fqbn", f)
				}
				if m := strArg(args, "mcu"); m != "" {
					a = append(a, "--mcu", m)
				}
				if h := strArg(args, "host"); h != "" {
					a = append(a, "--host", h)
				}
				if p, ok := intArg(args, "port"); ok {
					a = append(a, fmt.Sprintf("--port=%d", p))
				}
				if bd, ok := intArg(args, "baud"); ok {
					a = append(a, fmt.Sprintf("--baud=%d", bd))
				}
				return runCLI(newUploadCmd(), a)
			},
		},
		{
			Name: "companion_relay_devices",
			Description: "List the boards currently online on a self-hosted Companion relay " +
				"hub, with their firmware version. Use to confirm a board is reachable " +
				"before a remote push.",
			InputSchema: map[string]any{"type": "object", "properties": map[string]any{}},
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				if s.hub == "" {
					return "", fmt.Errorf("no relay hub configured — start the server with --hub wss://your-host")
				}
				return runCLI(newRelayCmd(), []string{"devices", "--hub", s.hub})
			},
		},
		{
			Name: "companion_relay_push",
			Description: "Push a firmware image to a board through the relay hub, from " +
				"anywhere on the internet (the board dials out; no inbound ports needed). " +
				"The device secret is read from COMPANION_RELAY_DEVICE_SECRET — it is " +
				"never passed through this interface. Flashes hardware, so it needs " +
				"--allow-upload on the server.",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"device":     map[string]any{"type": "string", "description": "device id on the hub"},
					"image_path": map[string]any{"type": "string", "description": "path to the .bin firmware image"},
				},
				"required": []string{"device", "image_path"},
			},
			destructive: true,
			handler: func(ctx context.Context, args map[string]any) (string, error) {
				if s.hub == "" {
					return "", fmt.Errorf("no relay hub configured — start the server with --hub wss://your-host")
				}
				device, image := strArg(args, "device"), strArg(args, "image_path")
				if device == "" || image == "" {
					return "", fmt.Errorf("device and image_path are both required")
				}
				// Check the credential BEFORE dialling the hub. Without this the
				// agent only sees "device secret required (pass --device-secret)",
				// which is a CLI flag it cannot set and says nothing about the
				// environment variable that would fix it.
				if os.Getenv("COMPANION_RELAY_DEVICE_SECRET") == "" {
					return "", fmt.Errorf(
						"COMPANION_RELAY_DEVICE_SECRET is not set in the server's environment. " +
							"It is the per-board provisioning secret (printed by the board on first boot). " +
							"Export it before starting the server — it is deliberately never passed through this interface.")
				}
				return runCLI(newRelayCmd(),
					[]string{"push", "--hub", s.hub, "--device", device, image})
			},
		},
	}
}

// ── protocol loop ─────────────────────────────────────────────────────────

// serve runs the stdio loop until EOF, handling one request at a time.
func (s *mcpServer) serve(in io.Reader, out io.Writer) error {
	sc := bufio.NewScanner(in)
	sc.Buffer(make([]byte, 0, 64*1024), 8*1024*1024) // a compile transcript can be large
	enc := json.NewEncoder(out)
	ctx := context.Background()

	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var req mcpRequest
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			_ = enc.Encode(mcpResponse{JSONRPC: "2.0",
				Error: &mcpError{Code: mcpParseError, Message: "invalid JSON: " + err.Error()}})
			continue
		}
		resp, reply := s.dispatch(ctx, req)
		if !reply {
			continue // a notification never gets a response
		}
		if err := enc.Encode(resp); err != nil {
			return err
		}
	}
	return sc.Err()
}

// dispatch handles one request. The bool is false for notifications, which by
// the JSON-RPC spec never get a reply.
func (s *mcpServer) dispatch(ctx context.Context, req mcpRequest) (mcpResponse, bool) {
	resp := mcpResponse{JSONRPC: "2.0", ID: req.ID}
	isNotification := len(req.ID) == 0
	reply := func() (mcpResponse, bool) {
		if isNotification {
			return resp, false
		}
		return resp, true
	}

	switch req.Method {
	case "initialize":
		version := mcpProtocolVersion
		var p struct {
			ProtocolVersion string `json:"protocolVersion"`
		}
		if len(req.Params) > 0 && json.Unmarshal(req.Params, &p) == nil && p.ProtocolVersion != "" {
			version = p.ProtocolVersion
		}
		resp.Result = map[string]any{
			"protocolVersion": version,
			"capabilities":    map[string]any{"tools": map[string]any{}},
			"serverInfo":      map[string]any{"name": "companion", "version": CLIVersion},
		}

	case "notifications/initialized", "initialized":
		return reply()

	case "ping":
		resp.Result = map[string]any{}

	case "tools/list":
		list := make([]*mcpTool, 0, len(s.order))
		for _, n := range s.order {
			list = append(list, s.tools[n])
		}
		resp.Result = map[string]any{"tools": list}

	case "tools/call":
		var p struct {
			Name      string         `json:"name"`
			Arguments map[string]any `json:"arguments"`
		}
		if len(req.Params) == 0 || json.Unmarshal(req.Params, &p) != nil {
			resp.Error = &mcpError{Code: mcpInvalidParams, Message: "tools/call needs {name, arguments}"}
			break
		}
		tool, known := s.tools[p.Name]
		if !known {
			resp.Error = &mcpError{Code: mcpMethodNotFound, Message: "unknown tool: " + p.Name}
			break
		}
		if tool.destructive && !s.allowUpload {
			// Refused as a TOOL error, not a protocol error: the client asked
			// for something real, and the honest answer is "not permitted",
			// with the fix in the message.
			resp.Result = map[string]any{
				"content": []map[string]any{{"type": "text", "text": fmt.Sprintf(
					"%s flashes hardware and is disabled on this server. Restart it with --allow-upload to enable it.",
					tool.Name)}},
				"isError": true,
			}
			break
		}
		s.runTool(ctx, tool, p.Arguments, &resp)

	default:
		if isNotification {
			return resp, false
		}
		resp.Error = &mcpError{Code: mcpMethodNotFound, Message: "unsupported method: " + req.Method}
	}
	return reply()
}

// runTool executes a tool into resp. A panic inside a tool must not take the
// server — and the agent's whole session — down with it.
func (s *mcpServer) runTool(ctx context.Context, tool *mcpTool, args map[string]any, resp *mcpResponse) {
	fail := func(msg string) {
		resp.Result = map[string]any{
			"content": []map[string]any{{"type": "text", "text": msg}},
			"isError": true,
		}
	}
	s.callMu.Lock()
	defer s.callMu.Unlock()
	defer func() {
		if r := recover(); r != nil {
			fail(fmt.Sprintf("tool %s panicked: %v", tool.Name, r))
		}
	}()

	if args == nil {
		args = map[string]any{}
	}
	// Bound every call: a hung compile or an unreachable hub must come back as
	// an error the agent can report, not a wedged session.
	ctx, cancel := context.WithTimeout(ctx, 20*time.Minute) // a cold ESP32 build
	defer cancel()

	type outcome struct {
		text string
		err  error
	}
	done := make(chan outcome, 1)
	go func() {
		text, err := tool.handler(ctx, args)
		done <- outcome{text, err}
	}()

	select {
	case res := <-done:
		if res.err != nil {
			fail(res.err.Error())
			return
		}
		resp.Result = map[string]any{
			"content": []map[string]any{{"type": "text", "text": res.text}},
		}
	case <-ctx.Done():
		fail(fmt.Sprintf("%s timed out: %v", tool.Name, ctx.Err()))
	}
}

// ── command ───────────────────────────────────────────────────────────────

func newMCPCmd() *cobra.Command {
	var (
		hub         string
		allowUpload bool
	)
	cmd := &cobra.Command{
		Use:   "mcp",
		Short: "Run a Model Context Protocol server (stdio) so any AI agent can drive Companion",
		Long: `Expose Companion to any AI agent or program over the Model Context Protocol.

MCP hosts (Claude Desktop, Cursor, an IDE assistant, your own agent loop) spawn
this command and speak JSON-RPC over stdin/stdout. Tools:

  companion_doctor         check the local toolchain and tools
  companion_list_ports     serial ports and likely board matches
  companion_board_list     installed board platforms
  companion_compile        compile a sketch, return diagnostics
  companion_upload         flash a target through the bridge  (--allow-upload)
  companion_relay_devices  boards online on a self-hosted relay hub
  companion_relay_push     push firmware over the internet   (--allow-upload)

Each tool is a thin adapter over the matching CLI command, so an agent and a
human get identical behaviour. Relay secrets come from the environment
(COMPANION_RELAY_AGENTS_TOKEN / COMPANION_RELAY_DEVICE_SECRET), never from
this interface.

Client config (Claude Desktop / Cursor): command "companion", args ["mcp"].
For the remote tools add --hub wss://your-host; to let the agent flash
hardware, add --allow-upload.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			// stdout IS the protocol channel, so every diagnostic goes to
			// stderr: a stray print on stdout would corrupt the stream.
			srv := newMCPServer(hub, allowUpload)
			fmt.Fprintf(os.Stderr,
				"companion mcp: %d tools, hub=%q, upload=%v (protocol on stdout)\n",
				len(srv.order), hub, allowUpload)
			return srv.serve(os.Stdin, os.Stdout)
		},
	}
	cmd.Flags().StringVar(&hub, "hub", "", "relay hub base URL (ws:// or wss://) for the remote tools")
	cmd.Flags().BoolVar(&allowUpload, "allow-upload", false,
		"allow the tools that flash hardware (companion_upload, companion_relay_push)")
	return cmd
}
