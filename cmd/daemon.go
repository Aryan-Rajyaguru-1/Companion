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
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/companion-ide/companion-cli/internal/atomicfile"
	"github.com/companion-ide/companion-cli/internal/boards"
	"github.com/companion-ide/companion-cli/internal/bridge"
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

	// Bug A: cancelCompile support. The job pointer is the ownership token:
	// an older compile must not clear a newer compile's cancellation slot.
	cancelMu  sync.Mutex
	cancelJob *compileJob

	// Serial monitor hub: one bridge connection, many SSE subscribers.
	serialMu      sync.Mutex
	serialConn    *bridge.Client
	serialClosed  bool
	serialReaders map[chan serialFrame]struct{}
}

// serialFrame is one chunk received from the target MCU.
type serialFrame struct {
	Data   []byte // raw bytes (may be non-UTF-8)
	Closed bool   // connection dropped
}

// compileJob identifies the single streaming compile allowed at a time.
// Comparing pointers lets the finishing handler clear only its own slot, even
// if compile.cancel released it and a second compile started in the meantime.
type compileJob struct {
	cancel context.CancelFunc
}

func (d *daemonServer) acquireCompileJob(cancel context.CancelFunc) *compileJob {
	d.cancelMu.Lock()
	defer d.cancelMu.Unlock()
	if d.cancelJob != nil {
		return nil
	}
	job := &compileJob{cancel: cancel}
	d.cancelJob = job
	return job
}

func (d *daemonServer) releaseCompileJob(job *compileJob) {
	job.cancel()
	d.cancelMu.Lock()
	if d.cancelJob == job {
		d.cancelJob = nil
	}
	d.cancelMu.Unlock()
}

func (d *daemonServer) cancelCompile() bool {
	d.cancelMu.Lock()
	defer d.cancelMu.Unlock()
	if d.cancelJob == nil {
		return false
	}
	d.cancelJob.cancel()
	d.cancelJob = nil
	return true
}

func newDaemonServer(cfg *config.Config, tokenPath string) (*daemonServer, error) {
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

	if tokenPath == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, fmt.Errorf("locate home directory for auth token: %w", err)
		}
		tokenPath = filepath.Join(home, config.DirName, "daemon", "auth-token")
	}
	tokenPath, err = filepath.Abs(tokenPath)
	if err != nil {
		return nil, fmt.Errorf("resolve auth token path: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(tokenPath), 0o700); err != nil {
		return nil, fmt.Errorf("daemon state dir: %w", err)
	}
	if err := checkTokenDir(filepath.Dir(tokenPath)); err != nil {
		return nil, err
	}
	// 0600: only the owning user may read the token. The IDE points this at a
	// private temp directory so it never has to print the credential to stdout
	// (which is copied into the console pane and logs). Atomic replacement also
	// means a pre-existing symlink at tokenPath is replaced, not followed.
	if err := atomicfile.WriteFile(tokenPath, []byte(token), 0o600); err != nil {
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

// checkTokenDir refuses a world-writable token directory. The token file
// itself is 0600, but in a world-writable directory another account could
// replace it (or the whole path) and point clients at a token they control.
// Existing 0755 application directories are fine: they are not writable by
// anyone but their owner.
func checkTokenDir(dir string) error {
	fi, err := os.Stat(dir)
	if err != nil {
		return fmt.Errorf("inspect auth token directory: %w", err)
	}
	if !fi.IsDir() {
		return fmt.Errorf("auth token parent %s is not a directory", dir)
	}
	// Windows synthesizes modes instead of reporting Unix permission bits, so
	// a normal file commonly appears as 0666/0777. The mode check is a Unix
	// ownership control; Windows access is governed by ACLs.
	if runtime.GOOS != "windows" {
		if perm := fi.Mode().Perm(); perm&0o002 != 0 {
			return fmt.Errorf("auth token directory %s is mode %04o; world-write access would let another user replace the token", dir, perm)
		}
	}
	return nil
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
	// One streaming compile at a time. The job pointer is an ownership token:
	// after compile.cancel releases the slot and a second compile starts, the
	// first compile's deferred cleanup must not clear the second's slot.
	job := d.acquireCompileJob(cancel)
	if job == nil {
		cancel()
		http.Error(w, "a compile is already running — cancel it before starting another", http.StatusConflict)
		return
	}
	defer d.releaseCompileJob(job)

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
		MainIno:      p.MainIno,
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
		d.cancelCompile()
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
	// BridgeMode selects LAN authentication. "local" (or omitted) uses the
	// configured bridge.key; "remote" targets a `companion relay bridge`
	// loopback socket, whose transport is protected by the relay hub and must
	// not receive an HMAC probe.
	BridgeMode string `json:"bridgeMode"`
}

// bridgeAuthForMode selects the bridge transport policy. Keeping the decision
// explicit avoids silently downgrading a keyed LAN bridge when a caller is
// actually talking to a relay loopback socket, and avoids making relay callers
// wait out the legacy-firmware authentication timeout.
func (d *daemonServer) bridgeAuthForMode(mode string) (key string, noAuth bool, err error) {
	switch mode {
	case "", "local":
		return config.BridgeKey(d.cfg), false, nil
	case "remote":
		return "", true, nil
	default:
		return "", false, fmt.Errorf("bridgeMode must be \"local\" or \"remote\"")
	}
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
	bridgeKey, bridgeNoAuth, err := d.bridgeAuthForMode(p.BridgeMode)
	if err != nil {
		writeStreamErr(w, err.Error())
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
		BinaryPath:   p.BinaryPath,
		MCU:          p.MCU,
		Host:         p.Host,
		Port:         p.Port,
		Baud:         p.Baud,
		FQBN:         p.FQBN,
		BridgeKey:    bridgeKey,
		BridgeNoAuth: bridgeNoAuth,
		Verbose:      p.Verbose,
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
	MainIno   string `json:"mainIno"`
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
		Action     string `json:"action"` // connect | disconnect
		Host       string `json:"host"`
		Port       int    `json:"port"`
		Baud       uint32 `json:"baud"`
		BridgeMode string `json:"bridgeMode"`
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
		bridgeKey, bridgeNoAuth, err := d.bridgeAuthForMode(p.BridgeMode)
		if err != nil {
			writeRPCError(w, nil, rpcInvalidParams, err.Error())
			return
		}
		if err := d.serialConnect(p.Host, p.Port, p.Baud, bridgeKey, bridgeNoAuth); err != nil {
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

func (d *daemonServer) serialConnect(host string, port int, baud uint32, bridgeKey string, bridgeNoAuth bool) error {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()

	// Replace any existing session. The reader for the old connection compares
	// against d.serialConn before publishing, so its late error cannot mark the
	// replacement session closed.
	if d.serialConn != nil {
		d.serialConn.Close()
		d.serialConn = nil
		d.serialClosed = true
		d.notifySerialLocked(serialFrame{Closed: true})
	}

	var conn *bridge.Client
	if bridgeNoAuth {
		conn = bridge.NewNoAuth(host, port)
	} else {
		conn = bridge.New(host, port, bridgeKey)
	}
	if err := conn.Connect(); err != nil {
		d.serialClosed = true
		d.notifySerialLocked(serialFrame{Closed: true})
		// Preserve the daemon's existing BRIDGE_TIMEOUT classification for
		// dial/network failures now that Connect wraps them in context.
		// Authentication failures are returned as-is so the UI can explain
		// the key mismatch instead of claiming the bridge is offline.
		var opErr *net.OpError
		if errors.As(err, &opErr) {
			return cerrors.BridgeTimeout(host, port)
		}
		return err
	}
	if baud > 0 {
		if err := conn.SetBaud(baud); err != nil {
			conn.Close()
			d.serialClosed = true
			d.notifySerialLocked(serialFrame{Closed: true})
			return err
		}
	}
	d.serialConn = conn
	d.serialClosed = false

	// Reader goroutine: broadcast chunks to all SSE subscribers.
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := conn.Read(buf)
			if n > 0 {
				frame := make([]byte, n)
				copy(frame, buf[:n])
				d.broadcastSerialFrom(conn, serialFrame{Data: frame})
			}
			if err != nil {
				d.broadcastSerialFrom(conn, serialFrame{Closed: true})
				return
			}
		}
	}()
	return nil
}

func (d *daemonServer) notifySerialLocked(f serialFrame) {
	for ch := range d.serialReaders {
		select {
		case ch <- f:
		default: // slow subscriber: drop rather than block the reader
		}
	}
}

// broadcastSerialFrom publishes only while conn is still the active session.
// Without the identity check, a reconnect's old reader could deliver stale
// bytes or a spurious "closed" event to the new session's subscribers.
func (d *daemonServer) broadcastSerialFrom(conn *bridge.Client, f serialFrame) {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()
	if d.serialConn != conn {
		return
	}
	if f.Closed {
		d.serialClosed = true
	}
	d.notifySerialLocked(f)
}

func (d *daemonServer) serialDisconnect() {
	d.serialMu.Lock()
	defer d.serialMu.Unlock()
	if d.serialConn != nil {
		d.serialConn.Close()
		d.serialConn = nil
		d.serialClosed = true
		d.notifySerialLocked(serialFrame{Closed: true})
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
		port      int
		pidFile   string
		tokenFile = os.Getenv("COMPANION_DAEMON_TOKEN_FILE")
	)

	cmd := &cobra.Command{
		Use:   "daemon",
		Short: "Start Companion Core Service — the API layer for desktop, web & mobile",
		Long: `Starts the persistent Companion Core Service that all clients talk to.
Compile output and wireless uploads stream in real time; the serial monitor
is multiplexed over Server-Sent Events.

  companion daemon --port 44444

Authentication: a bearer token is generated at startup and written to
~/.companion-cli/daemon/auth-token (mode 0600), or to --token-file when set.
Every endpoint except GET /ping requires "Authorization: Bearer <token>".
Set COMPANION_DAEMON_TOKEN_FILE to choose the path without putting it in argv.

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

			d, err := newDaemonServer(cfg, tokenFile)
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
				Handler:     d,
				ReadTimeout: 300 * time.Second,
				// No write deadline: compile and upload responses STREAM, and a
				// cold ESP32 build on slow hardware (or a big firmware push
				// over a tunnel) legitimately runs past five minutes — the
				// old 300s WriteTimeout killed the serial monitor and any long
				// build mid-response. ReadHeaderTimeout still bounds the
				// slowloris case, which is the one that matters.
				ReadHeaderTimeout: 20 * time.Second,
				IdleTimeout:       120 * time.Second,
			}

			fmt.Printf("COMPANION_DAEMON_PORT=%d\n", actualPort)
			// The token is never printed: stdout is piped into the IDE's console
			// pane (and often a log file), which turns a bearer credential into
			// something readable in a screenshot. It is written to a 0600 file
			// and read from there by clients.
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
	cmd.Flags().StringVar(&tokenFile, "token-file", tokenFile,
		"Write the bearer token to this file (default ~/.companion-cli/daemon/auth-token; env COMPANION_DAEMON_TOKEN_FILE)")
	return cmd
}
