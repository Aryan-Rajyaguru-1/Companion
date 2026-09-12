package cmd

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/compiler"
	"github.com/companion-ide/companion-cli/internal/config"
	cerrors "github.com/companion-ide/companion-cli/internal/errors"
	"github.com/companion-ide/companion-cli/internal/ota"
	"github.com/companion-ide/companion-cli/internal/plugins"
	"github.com/companion-ide/companion-cli/internal/uploader"
	"github.com/spf13/cobra"
)

// ── JSON-RPC types ──────────────────────────────────────────────

type rpcRequest struct {
	ID     interface{}     `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

type rpcResponse struct {
	ID     interface{} `json:"id"`
	Result interface{} `json:"result,omitempty"`
	Error  *rpcError   `json:"error,omitempty"`
}

// rpcError carries both a JSON-RPC numeric code and (when available) a
// machine-readable CompanionError code so clients can route programmatically
// without fragile message parsing.
type rpcError struct {
	Code       int    `json:"code"`
	Message    string `json:"message"`
	ErrCode    string `json:"errCode,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// JSON-RPC error codes (standard subset + companion app range).
const (
	rpcParseError    = -32700
	rpcInvalidParams = -32602
	rpcUnauthorized  = -32001
	rpcInvalidState  = -32002
	rpcServerError   = -32000
)

// ── Stream event types ──────────────────────────────────────────

type streamEvent struct {
	Type       string   `json:"type"`              // "output" | "done" | "error"
	Text       string   `json:"text,omitempty"`    // for "output"
	Success    bool     `json:"success,omitempty"` // for "done"
	BinaryPath string   `json:"binaryPath,omitempty"`
	Output     []string `json:"output,omitempty"` // full output for "done"
	Error      string   `json:"error,omitempty"`  // for "done" failures or "error"
}

// ── Daemon server ───────────────────────────────────────────────

type daemonServer struct {
	cfg      *config.Config
	bm       *boards.Manager
	cache    *compiler.BuildCache
	registry *plugins.Registry

	// Bearer token written to disk for IDE/web/mobile clients.
	tokenPath string
	token     string

	// Bug A: cancelCompile support
	cancelMu   sync.Mutex
	cancelFunc context.CancelFunc

	// Serial monitor hub: one bridge connection, many SSE subscribers.
	serialMu      sync.Mutex
	serialConn    net.Conn
	serialClosed  bool
	serialReaders map[chan serialFrame]struct{}
}

// serialFrame is one chunk received from the target MCU.
type serialFrame struct {
	Data   []byte // raw bytes (may be non-UTF-8)
	Closed bool   // connection dropped
}

func newDaemonServer(cfg *config.Config) (*daemonServer, error) {
	bm := boards.NewManager(cfg)
	cacheDir := compiler.DefaultCacheDir(cfg.Directories.Data)
	cache, err := compiler.NewBuildCache(cacheDir)
	if err != nil {
		return nil, err
	}

	token, err := generateToken()
	if err != nil {
		return nil, fmt.Errorf("generate auth token: %w", err)
	}

	home, _ := os.UserHomeDir()
	daemonDir := filepath.Join(home, config.DirName, "daemon")
	if err := os.MkdirAll(daemonDir, 0o700); err != nil {
		return nil, fmt.Errorf("daemon state dir: %w", err)
	}
	tokenPath := filepath.Join(daemonDir, "auth-token")
	// 0600: only the owning user may read the token.
	if err := os.WriteFile(tokenPath, []byte(token), 0o600); err != nil {
		return nil, fmt.Errorf("write auth token: %w", err)
	}

	reg := pluginRegistry(cfg)
	return &daemonServer{
		cfg:           cfg,
		bm:            bm,
		cache:         cache,
		registry:      reg,
		token:         token,
		tokenPath:     tokenPath,
		serialReaders: make(map[chan serialFrame]struct{}),
	}, nil
}

// generateToken returns 32 bytes of CSPRNG entropy, base64-encoded.
func generateToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}

func (d *daemonServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path

	switch {
	case r.Method == http.MethodGet && path == "/ping":
		// Health check stays unauthenticated but reveals nothing sensitive.
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "version": CLIVersion})
		return
	}

	if !d.authorized(r) {
		w.Header().Set("WWW-Authenticate", `Bearer realm="companion-daemon"`)
		writeRPCError(w, nil, rpcUnauthorized, "missing or invalid bearer token")
		return
	}

	// Versioned API plus legacy paths kept working for the current IDE.
	if strings.HasPrefix(path, "/api/v1/") {
		path = strings.TrimPrefix(path, "/api/v1")
	}

	switch {
	case r.Method == http.MethodPost && path == "/rpc":
		d.handleRPC(w, r)

	// Streaming compile endpoint — real-time output via chunked NDJSON
	case r.Method == http.MethodPost && path == "/stream-compile":
		d.handleStreamCompile(w, r)

	// Streaming wireless upload with live progress events
	case r.Method == http.MethodPost && path == "/upload", r.Method == http.MethodPost && path == "/stream-upload":
		d.handleStreamUpload(w, r)

	// Serial monitor: control + SSE data stream
	case r.Method == http.MethodPost && path == "/serial":
		d.handleSerialControl(w, r)
	case r.Method == http.MethodGet && path == "/serial/send":
		fallthrough
	case r.Method == http.MethodPost && path == "/serial/send":
		d.handleSerialSend(w, r)
	case r.Method == http.MethodGet && path == "/serial/stream":
		d.handleSerialStream(w, r)

	default:
		http.NotFound(w, r)
	}
}

// authorized verifies the Authorization: Bearer <token> header in constant time.
func (d *daemonServer) authorized(r *http.Request) bool {
	h := r.Header.Get("Authorization")
	const prefix = "Bearer "
	if !strings.HasPrefix(h, prefix) {
		return false
	}
	got := strings.TrimSpace(h[len(prefix):])
	return len(got) > 0 &&
		subtle.ConstantTimeCompare([]byte(got), []byte(d.token)) == 1
}

// handleStreamCompile — streaming compile with real-time chunked output
func (d *daemonServer) handleStreamCompile(w http.ResponseWriter, r *http.Request) {
	var p compileParams
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, `{"type":"error","message":"invalid params"}`, 400)
		return
	}
	if p.Warnings == "" {
		p.Warnings = "default"
	}
	p.SketchDir, _ = filepath.Abs(p.SketchDir)

	// Chunked transfer encoding for real-time streaming
	w.Header().Set("Content-Type", "application/x-ndjson")
	w.Header().Set("Transfer-Encoding", "chunked")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)
	flusher, canFlush := w.(http.Flusher)

	sendEvent := func(ev streamEvent) {
		b, _ := json.Marshal(ev)
		fmt.Fprintf(w, "%s\n", b)
		if canFlush {
			flusher.Flush()
		}
	}

	// Cancellation: client disconnect OR compile.cancel RPC kills the
	// toolchain subprocesses through the compiler's exec.CommandContext.
	ctx, cancel := context.WithCancel(context.Background())
	d.cancelMu.Lock()
	d.cancelFunc = cancel
	d.cancelMu.Unlock()
	defer func() {
		cancel()
		d.cancelMu.Lock()
		d.cancelFunc = nil
		d.cancelMu.Unlock()
	}()

	done := make(chan struct{})
	defer close(done)
	go func() {
		select {
		case <-r.Context().Done(): // client went away
			cancel()
		case <-done:
		}
	}()

	var outMu sync.Mutex
	var outputLines []string
	cmp := compiler.NewWithContext(ctx, d.cfg, d.bm, func(line string) {
		outMu.Lock()
		outputLines = append(outputLines, line)
		outMu.Unlock()
		sendEvent(streamEvent{Type: "output", Text: line})
	})
	cmp.SetPlugins(d.registry)
	if d.cfg.Cache.Enabled {
		if bc, err := compiler.NewBuildCache(compiler.DefaultCacheDir(d.cfg.Directories.Data)); err == nil {
			cmp.SetCache(bc)
			defer bc.Evict()
		}
	}

	result, buildErr := cmp.Build(compiler.Options{
		SketchDir:    p.SketchDir,
		FQBN:         p.FQBN,
		Warnings:     p.Warnings,
		Verbose:      p.Verbose,
		ExportBinary: p.ExportBin,
	})

	if ctx.Err() == context.Canceled {
		sendEvent(streamEvent{Type: "cancelled", Success: false, Error: "Compile cancelled"})
		return
	}
	outMu.Lock()
	lines := outputLines
	outMu.Unlock()

	if buildErr != nil {
		sendEvent(streamEvent{
			Type:    "done",
			Success: false,
			Error:   buildErr.Error(),
			Output:  lines,
		})
		return
	}

	sendEvent(streamEvent{
		Type:       "done",
		Success:    true,
		BinaryPath: result.BinaryPath,
		Output:     lines,
	})
}

// ── JSON-RPC handler ─────────────────────────────────────────────

func (d *daemonServer) handleRPC(w http.ResponseWriter, r *http.Request) {
	var req rpcRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeRPCError(w, nil, rpcParseError, "Parse error: "+err.Error())
		return
	}
	result, err := d.dispatch(r.Context(), req.Method, req.Params)
	if err != nil {
		writeAppError(w, req.ID, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rpcResponse{ID: req.ID, Result: result})
}

// writeAppError converts Go errors into structured RPC errors, preserving
// CompanionError code/suggestion when present.
func writeAppError(w http.ResponseWriter, id interface{}, err error) {
	var ce *cerrors.CompanionError
	if errors.As(err, &ce) {
		writeRPCCodedError(w, id, rpcServerError, ce.Error(), string(ce.Code), ce.Suggestion)
		return
	}
	writeRPCError(w, id, rpcServerError, err.Error())
}

func (d *daemonServer) dispatch(ctx context.Context, method string, params json.RawMessage) (interface{}, error) {
	switch method {
	case "version":
		return map[string]string{"version": CLIVersion}, nil

	// Bug A: cancel the in-flight streaming compile
	case "compile.cancel":
		d.cancelMu.Lock()
		if d.cancelFunc != nil {
			d.cancelFunc()
			d.cancelFunc = nil
		}
		d.cancelMu.Unlock()
		return map[string]bool{"cancelled": true}, nil

	case "board.list":
		installed, err := d.bm.ListInstalled()
		if err != nil {
			return nil, err
		}
		return installed, nil

	case "board.listAll", "board.list-all":
		var p struct {
			Query string `json:"query"`
		}
		json.Unmarshal(params, &p)
		all, err := d.bm.ListAllBoards()
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(p.Query) == "" {
			return all, nil
		}
		q := strings.ToLower(p.Query)
		var filtered []boards.BoardEntry
		for _, b := range all {
			if strings.Contains(strings.ToLower(b.Name), q) ||
				strings.Contains(strings.ToLower(b.FQBN), q) {
				filtered = append(filtered, b)
			}
		}
		return filtered, nil

	case "board.search":
		var p struct {
			Query string `json:"query"`
		}
		json.Unmarshal(params, &p)
		return d.bm.Search(p.Query)

	case "board.packages", "board.search-packages":
		var p struct {
			Query string `json:"query"`
		}
		json.Unmarshal(params, &p)
		packages, err := d.bm.SearchPackages(p.Query)
		if err != nil {
			return nil, err
		}
		if len(packages) == 0 && strings.TrimSpace(p.Query) == "" {
			// Lazy-heal missing indexes so the IDE can still show packages on first open.
			if err := d.bm.UpdateIndex(func(string) {}); err == nil {
				packages, err = d.bm.SearchPackages(p.Query)
				if err != nil {
					return nil, err
				}
			}
		}
		return packages, nil

	case "board.update-index":
		var lines []string
		if err := d.bm.UpdateIndex(func(s string) { lines = append(lines, s) }); err != nil {
			return nil, err
		}
		return map[string]interface{}{"ok": true, "lines": lines}, nil

	case "cache.stats":
		return d.cache.Stats(), nil

	case "cache.evict":
		if err := d.cache.Evict(); err != nil {
			return nil, err
		}
		return map[string]bool{"ok": true}, nil

	// ── P4: OTA (network flash via ArduinoOTA wire protocol) ──

	case "ota.discover": // { waitMs? }
		var p struct {
			WaitMs int `json:"waitMs"`
		}
		json.Unmarshal(params, &p)
		wait := 3 * time.Second
		if p.WaitMs > 0 {
			wait = time.Duration(p.WaitMs) * time.Millisecond
		}
		return ota.Discover(ctx, wait), nil

	case "ota.push": // { imagePath, deviceIP, devicePort?, password? }
		var p otaPushParams
		if err := json.Unmarshal(params, &p); err != nil {
			return nil, err
		}
		if p.ImagePath == "" || p.DeviceIP == "" {
			return nil, fmt.Errorf("ota.push needs imagePath and deviceIP")
		}
		if err := ota.Probe(p.DeviceIP, p.DevicePort); err != nil {
			return nil, err
		}
		var lines []string
		var outMu sync.Mutex
		start := time.Now()
		err := ota.Push(ctx, ota.Options{
			ImagePath:  p.ImagePath,
			DeviceIP:   p.DeviceIP,
			DevicePort: p.DevicePort,
			Password:   p.Password,
			OnMessage: func(s string) {
				outMu.Lock()
				lines = append(lines, s)
				outMu.Unlock()
			},
		})
		if err != nil {
			return nil, err
		}
		outMu.Lock()
		collected := lines
		outMu.Unlock()
		return map[string]interface{}{
			"ok":       true,
			"lines":    collected,
			"duration": time.Since(start).Round(time.Millisecond).String(),
		}, nil

	default:
		return nil, fmt.Errorf("unknown method: %s", method)
	}
}

// ── Streaming upload (wireless flash with live progress) ────────

type uploadStreamParams struct {
	BinaryPath string `json:"binaryPath"`
	MCU        string `json:"mcu"`
	Host       string `json:"host"`
	Port       int    `json:"port"`
	Baud       uint32 `json:"baud"`
	FQBN       string `json:"fqbn"`
	Verbose    bool   `json:"verbose"`
}

// otaPushParams are the parameters for the ota.push RPC.
type otaPushParams struct {
	ImagePath  string `json:"imagePath"`
	DeviceIP   string `json:"deviceIP"`
	DevicePort int    `json:"devicePort"`
	Password   string `json:"password"`
}

func (d *daemonServer) handleStreamUpload(w http.ResponseWriter, r *http.Request) {
	var p uploadStreamParams
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeStreamErr(w, "invalid params")
		return
	}

	w.Header().Set("Content-Type", "application/x-ndjson")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)
	flusher, canFlush := w.(http.Flusher)
	sendEvent := func(ev streamEvent) {
		b, _ := json.Marshal(ev)
		fmt.Fprintf(w, "%s\n", b)
		if canFlush {
			flusher.Flush()
		}
	}

	ul := uploader.New(d.cfg, func(line string) {
		sendEvent(streamEvent{Type: "output", Text: line})
	})
	if err := ul.Upload(uploader.Options{
		BinaryPath: p.BinaryPath,
		MCU:        p.MCU,
		Host:       p.Host,
		Port:       p.Port,
		Baud:       p.Baud,
		FQBN:       p.FQBN,
		Verbose:    p.Verbose,
	}); err != nil {
		sendEvent(streamEvent{Type: "done", Success: false, Error: err.Error()})
		return
	}
	sendEvent(streamEvent{Type: "done", Success: true})
}

func writeStreamErr(w http.ResponseWriter, msg string) {
	http.Error(w, fmt.Sprintf(`{"type":"error","message":%q}`, msg), 400)
}

// ── Compile params ──────────────────────────────────────────────

type compileParams struct {
	SketchDir string `json:"sketchDir"`
	FQBN      string `json:"fqbn"`
	ExportBin bool   `json:"exportBin"`
	Verbose   bool   `json:"verbose"`
	Warnings  string `json:"warnings"`
}

func writeRPCError(w http.ResponseWriter, id interface{}, code int, msg string) {
	writeRPCCodedError(w, id, code, msg, "", "")
}

// writeRPCCodedError includes an optional machine-readable CompanionError
// code and suggestion for programmatic client handling.
func writeRPCCodedError(w http.ResponseWriter, id interface{}, code int, msg, errCode, suggestion string) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rpcResponse{
		ID: id,
		Error: &rpcError{
			Code:       code,
			Message:    msg,
			ErrCode:    errCode,
			Suggestion: suggestion,
		},
	})
}

// ── Serial monitor hub ───────────────────────────────────────────
//
// One TCP connection to the ESP32 bridge; any number of clients subscribe
// via GET /serial/stream (SSE). Control happens over POST /serial.

const (
	serialActionConnect    = "connect"
	serialActionDisconnect = "disconnect"
)

func (d *daemonServer) handleSerialControl(w http.ResponseWriter, r *http.Request) {
	var p struct {
		Action string `json:"action"` // connect | disconnect
		Host   string `json:"host"`
		Port   int    `json:"port"`
		Baud   uint32 `json:"baud"`
	}
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeRPCError(w, nil, rpcParseError, "invalid params")
		return
	}

	switch p.Action {
	case serialActionConnect:
		if p.Host == "" || p.Port == 0 {
			writeRPCError(w, nil, rpcInvalidParams, "host and port required")
			return
		}
		if err := d.serialConnect(p.Host, p.Port, p.Baud); err != nil {
			writeAppError(w, nil, err)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"ok": true})

	case serialActionDisconnect:
		d.serialDisconnect()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"ok": true})

	default:
		writeRPCError(w, nil, rpcInvalidParams, "action must be connect|disconnect")
	}
}

func (d *daemonServer) handleSerialSend(w http.ResponseWriter, r *http.Request) {
	var p struct {
		Text       string `json:"text"`
		LineEnding string `json:"lineEnding"`
	}
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeRPCError(w, nil, rpcParseError, "invalid params")
		return
	}
	d.serialMu.Lock()
	conn := d.serialConn
	d.serialMu.Unlock()

	if conn == nil {
		writeRPCError(w, nil, rpcInvalidState, "serial not connected")
		return
	}
	if _, err := conn.Write([]byte(p.Text + p.LineEnding)); err != nil {
		writeAppError(w, nil, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]bool{"ok": true})
}

func (d *daemonServer) serialConnect(host string, port int, baud uint32) error {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()

	// Replace any existing session.
	if d.serialConn != nil {
		d.serialConn.Close()
		d.serialConn = nil
	}
	d.serialClosed = false

	addr := net.JoinHostPort(host, fmt.Sprintf("%d", port))
	conn, err := net.DialTimeout("tcp", addr, 8*time.Second)
	if err != nil {
		return cerrors.BridgeTimeout(host, port)
	}
	if tc, ok := conn.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}
	d.serialConn = conn

	// Configure baud via the bridge control protocol (matches esp32_bridge.ino:
	// prefix 0xEF 0xBE, cmd 0x10, uint32 big-endian baud).
	if baud > 0 {
		conn.Write([]byte{0xEF, 0xBE, 0x10,
			byte(baud >> 24), byte(baud >> 16), byte(baud >> 8), byte(baud)})
	}

	// Reader goroutine: broadcast chunks to all SSE subscribers.
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := conn.Read(buf)
			if n > 0 {
				frame := make([]byte, n)
				copy(frame, buf[:n])
				d.broadcastSerial(serialFrame{Data: frame})
			}
			if err != nil {
				d.broadcastSerial(serialFrame{Closed: true})
				return
			}
		}
	}()
	return nil
}

func (d *daemonServer) broadcastSerial(f serialFrame) {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()
	if f.Closed {
		d.serialClosed = true
	}
	for ch := range d.serialReaders {
		select {
		case ch <- f:
		default: // slow subscriber: drop rather than block the reader
		}
	}
}

func (d *daemonServer) serialDisconnect() {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()
	if d.serialConn != nil {
		d.serialConn.Close()
		d.serialConn = nil
	}
}

// handleSerialStream streams target→host bytes as Server-Sent Events.
// Events are JSON lines: {"type":"data","b64":"…"} | {"type":"closed"}.
func (d *daemonServer) handleSerialStream(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}

	ch := make(chan serialFrame, 64)
	d.serialMu.Lock()
	d.serialReaders[ch] = struct{}{}
	closedAlready := d.serialClosed && d.serialConn == nil
	d.serialMu.Unlock()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)

	if closedAlready {
		fmt.Fprint(w, "data: {\"type\":\"closed\"}\n\n")
		flusher.Flush()
		return
	}

	defer func() {
		d.serialMu.Lock()
		delete(d.serialReaders, ch)
		d.serialMu.Unlock()
	}()

	for {
		select {
		case <-r.Context().Done():
			return
		case f := <-ch:
			if f.Closed {
				fmt.Fprint(w, "data: {\"type\":\"closed\"}\n\n")
				flusher.Flush()
				return
			}
			b, _ := json.Marshal(struct {
				Type string `json:"type"`
				B64  string `json:"b64"`
			}{Type: "data", B64: base64.StdEncoding.EncodeToString(f.Data)})
			fmt.Fprintf(w, "data: %s\n\n", b)
			flusher.Flush()
		}
	}
}

// ── Command ─────────────────────────────────────────────────────

func newDaemonCmd() *cobra.Command {
	var (
		port    int
		pidFile string
	)

	cmd := &cobra.Command{
		Use:   "daemon",
		Short: "Start Companion Core Service — the API layer for desktop, web & mobile",
		Long: `Starts the persistent Companion Core Service that all clients talk to.
Compile output and wireless uploads stream in real time; the serial monitor
is multiplexed over Server-Sent Events.

  companion daemon --port 44444

Authentication: a bearer token is generated at startup and written to
~/.companion-cli/daemon/auth-token (mode 0600). Every endpoint except
GET /ping requires "Authorization: Bearer <token>".

Endpoints (also served under /api/v1/):
  POST /rpc              JSON-RPC 2.0 (boards, cache, cancel)
  POST /stream-compile   Streaming compile (NDJSON events)
  POST /upload           Streaming wireless upload (NDJSON events)
  POST /serial           Serial monitor connect/disconnect
  GET  /serial/stream    Serial monitor data (SSE)
  GET  /ping             Health check (no auth)`,

		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, _, err := config.Load(globalFlags.ConfigFile)
			if err != nil {
				return fmt.Errorf("config: %w", err)
			}
			if err := config.EnsureDirs(cfg); err != nil {
				return err
			}

			d, err := newDaemonServer(cfg)
			if err != nil {
				return fmt.Errorf("daemon init: %w", err)
			}

			ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
			if err != nil {
				return fmt.Errorf("daemon listen: %w", err)
			}
			actualPort := ln.Addr().(*net.TCPAddr).Port

			if pidFile != "" {
				os.WriteFile(pidFile, []byte(fmt.Sprintf("%d", os.Getpid())), 0o644)
				defer os.Remove(pidFile)
			}

			srv := &http.Server{
				Handler:      d,
				ReadTimeout:  300 * time.Second, // long for streaming compiles
				WriteTimeout: 300 * time.Second,
			}

			fmt.Printf("COMPANION_DAEMON_PORT=%d\n", actualPort)
			fmt.Printf("COMPANION_DAEMON_TOKEN=%s\n", d.token)
			os.Stdout.Sync()
			printInfo(fmt.Sprintf("Daemon listening on port %d (PID %d)", actualPort, os.Getpid()))
			printInfo(fmt.Sprintf("Auth token written to %s", d.tokenPath))

			stop := make(chan os.Signal, 1)
			signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

			// Bug 11 fix: NewTicker + done channel prevents goroutine leak
			done := make(chan struct{})
			go func() {
				ticker := time.NewTicker(24 * time.Hour)
				defer ticker.Stop()
				for {
					select {
					case <-ticker.C:
						if err := d.cache.Evict(); err != nil {
							log.Printf("cache evict: %v", err)
						}
					case <-done:
						return
					}
				}
			}()

			go func() {
				<-stop
				printInfo("Daemon shutting down…")
				close(done)
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
				defer cancel()
				srv.Shutdown(ctx)
			}()

			if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
				return err
			}
			return nil
		},
	}

	cmd.Flags().IntVar(&port, "port", 0, "Port (0 = OS-assigned)")
	cmd.Flags().StringVar(&pidFile, "pid-file", "", "Write PID to file (optional)")
	return cmd
}
