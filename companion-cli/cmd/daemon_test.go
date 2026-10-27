package cmd

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/companion-ide/companion-cli/internal/config"
)

func testDaemon(t *testing.T) *daemonServer {
	t.Helper()
	cfg := &config.Config{}
	cfg.Directories.Data = t.TempDir() // isolated cache/index dirs
	d, err := newDaemonServer(cfg, filepath.Join(t.TempDir(), "auth-token"))
	if err != nil {
		t.Fatalf("newDaemonServer: %v", err)
	}
	return d
}

// The daemon token is a credential. It must land in a 0600 file that the IDE
// can read, and it must match the token the server actually accepts.
func TestDaemonTokenFileIsPrivateAndMatches(t *testing.T) {
	path := filepath.Join(t.TempDir(), "private", "auth-token")
	cfg := &config.Config{}
	cfg.Directories.Data = t.TempDir()
	d, err := newDaemonServer(cfg, path)
	if err != nil {
		t.Fatalf("newDaemonServer: %v", err)
	}
	if d.tokenPath != path {
		t.Fatalf("tokenPath = %q, want %q", d.tokenPath, path)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat token file: %v", err)
	}
	if got := fi.Mode().Perm(); got != 0o600 {
		t.Fatalf("token file mode = %04o, want 0600", got)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read token file: %v", err)
	}
	if string(raw) != d.token {
		t.Fatalf("token file content does not match the accepted token")
	}
}

// A pre-existing symlink must be replaced, not followed: a link planted at the
// token path would otherwise overwrite its target with the new credential.
func TestDaemonTokenReplacesSymlinkWithoutFollowing(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink creation requires elevated privileges on Windows")
	}
	target := filepath.Join(t.TempDir(), "target")
	if err := os.WriteFile(target, []byte("keep me"), 0o600); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "auth-token")
	if err := os.Symlink(target, path); err != nil {
		t.Fatal(err)
	}
	cfg := &config.Config{}
	cfg.Directories.Data = t.TempDir()
	if _, err := newDaemonServer(cfg, path); err != nil {
		t.Fatalf("newDaemonServer: %v", err)
	}
	got, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "keep me" {
		t.Fatalf("symlink target was overwritten with %q", got)
	}
	fi, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode()&os.ModeSymlink != 0 {
		t.Fatal("token path is still a symlink")
	}
}

// A world-writable token directory lets another account replace the token
// file. Refuse it instead of writing a credential into that directory.
func TestDaemonRejectsWorldWritableTokenDir(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("POSIX mode bits are not enforced on Windows")
	}
	dir := t.TempDir()
	if err := os.Chmod(dir, 0o777); err != nil {
		t.Fatal(err)
	}
	cfg := &config.Config{}
	cfg.Directories.Data = t.TempDir()
	if _, err := newDaemonServer(cfg, filepath.Join(dir, "auth-token")); err == nil {
		t.Fatal("newDaemonServer accepted a world-writable token directory")
	}
}

// compile.cancel releases the slot before the old handler returns. A compile
// that starts in that window owns a new job; the old handler's cleanup must
// not clear it.
func TestCompileJobCleanupDoesNotClearNewerJob(t *testing.T) {
	d := &daemonServer{}
	var oldCancelled, newCancelled int
	oldJob := d.acquireCompileJob(func() { oldCancelled++ })
	if oldJob == nil {
		t.Fatal("first acquire unexpectedly failed")
	}
	if second := d.acquireCompileJob(func() { t.Error("rejected job must not run") }); second != nil {
		t.Fatal("second acquire succeeded while the first job was active")
	}
	if !d.cancelCompile() {
		t.Fatal("cancelCompile reported no active job")
	}
	newJob := d.acquireCompileJob(func() { newCancelled++ })
	if newJob == nil {
		t.Fatal("new acquire failed after cancel released the slot")
	}

	d.releaseCompileJob(oldJob)
	d.cancelMu.Lock()
	active := d.cancelJob
	d.cancelMu.Unlock()
	if active != newJob {
		t.Fatal("old job cleanup cleared the newer job's slot")
	}

	d.releaseCompileJob(newJob)
	if oldCancelled != 2 {
		t.Fatalf("old job cancel count = %d, want 2 (cancel RPC + cleanup)", oldCancelled)
	}
	if newCancelled != 1 {
		t.Fatalf("new job cancel count = %d, want 1", newCancelled)
	}
	d.cancelMu.Lock()
	active = d.cancelJob
	d.cancelMu.Unlock()
	if active != nil {
		t.Fatal("slot was not cleared after the final job finished")
	}
}

func doReq(t *testing.T, d *daemonServer, method, path, token string, body []byte) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if body != nil {
		req = httptest.NewRequest(method, path, bytes.NewReader(body))
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	d.ServeHTTP(rec, req)
	return rec
}

func TestDaemonPingRequiresNoAuth(t *testing.T) {
	d := testDaemon(t)
	rec := doReq(t, d, http.MethodGet, "/ping", "", nil)
	if rec.Code != 200 {
		t.Fatalf("/ping status = %d, want 200", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"ok"`) {
		t.Errorf("ping body should contain ok, got %q", rec.Body.String())
	}
}

func TestDaemonRejectsMissingToken(t *testing.T) {
	d := testDaemon(t)
	body, _ := json.Marshal(rpcRequest{ID: 1, Method: "version"})
	rec := doReq(t, d, http.MethodPost, "/api/v1/rpc", "", body)
	if rec.Code != 200 { // JSON-RPC errors ride on HTTP 200
		t.Fatalf("status = %d", rec.Code)
	}
	var resp rpcResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.Error == nil || resp.Error.Code != rpcUnauthorized {
		t.Errorf("expected unauthorized JSON-RPC error, got %+v", resp.Error)
	}
}

func TestDaemonRejectsWrongToken(t *testing.T) {
	d := testDaemon(t)
	body, _ := json.Marshal(rpcRequest{ID: 1, Method: "version"})
	rec := doReq(t, d, http.MethodPost, "/rpc", "wrong-token", body)
	var resp rpcResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)
	if resp.Error == nil || resp.Error.Code != rpcUnauthorized {
		t.Errorf("expected unauthorized for wrong token, got %+v", resp.Error)
	}
}

func TestDaemonRPCVersionWithToken(t *testing.T) {
	d := testDaemon(t)
	body, _ := json.Marshal(rpcRequest{ID: 7, Method: "version"})
	for _, path := range []string{"/rpc", "/api/v1/rpc"} {
		rec := doReq(t, d, http.MethodPost, path, d.token, body)
		var resp rpcResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
			t.Fatalf("%s: bad response: %v", path, err)
		}
		if resp.Error != nil {
			t.Errorf("%s: unexpected error %+v", path, resp.Error)
		}
		result, _ := resp.Result.(map[string]interface{})
		if result["version"] == "" {
			t.Errorf("%s: version result missing", path)
		}
	}
}

func TestDaemonUnknownMethodIsStructuredError(t *testing.T) {
	d := testDaemon(t)
	body, _ := json.Marshal(rpcRequest{ID: 2, Method: "no.such.method"})
	rec := doReq(t, d, http.MethodPost, "/rpc", d.token, body)
	var resp rpcResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)
	if resp.Error == nil || resp.Error.Code != rpcServerError {
		t.Errorf("expected server error for unknown method, got %+v", resp.Error)
	}
}

func TestGenerateTokenShape(t *testing.T) {
	a, err := generateToken()
	if err != nil {
		t.Fatal(err)
	}
	b, _ := generateToken()
	if a == b {
		t.Error("tokens must be unique")
	}
	if len(a) < 32 {
		t.Errorf("token too short: %d chars", len(a))
	}
}

// startAuthDaemonBridge accepts one daemon serial connection, requires the
// same challenge-response as the firmware, records the SET_BAUD frame, and
// then holds the connection open. It intentionally does not echo bytes: the
// daemon owns the reader goroutine, so the test only needs the handshake and
// control frame.
func startAuthDaemonBridge(t *testing.T, key string) (string, int, <-chan uint32) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(func() { _ = ln.Close() })
	bauds := make(chan uint32, 1)

	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		_ = conn.SetDeadline(time.Now().Add(5 * time.Second))

		hdr := make([]byte, 3)
		if _, err := io.ReadFull(conn, hdr); err != nil {
			t.Errorf("read AUTH_BEGIN: %v", err)
			return
		}
		if !bytes.Equal(hdr, []byte{0xEF, 0xBE, 0x30}) {
			t.Errorf("first frame = % x, want AUTH_BEGIN", hdr)
			return
		}

		nonce := bytes.Repeat([]byte{0x5a}, 32)
		if _, err := conn.Write(append([]byte{0xEF, 0xBE, 0x32}, nonce...)); err != nil {
			t.Errorf("write challenge: %v", err)
			return
		}
		response := make([]byte, 3+32)
		if _, err := io.ReadFull(conn, response); err != nil {
			t.Errorf("read AUTH_RESPONSE: %v", err)
			return
		}
		mac := hmac.New(sha256.New, []byte(key))
		mac.Write(nonce)
		if !bytes.Equal(response[:3], []byte{0xEF, 0xBE, 0x31}) ||
			!hmac.Equal(response[3:], mac.Sum(nil)) {
			t.Errorf("bad authentication response")
			_, _ = conn.Write([]byte{0xEF, 0xBE, 0x34})
			return
		}
		if _, err := conn.Write([]byte{0xEF, 0xBE, 0x33}); err != nil {
			t.Errorf("write AUTH_OK: %v", err)
			return
		}

		frame := make([]byte, 7)
		if _, err := io.ReadFull(conn, frame); err != nil {
			t.Errorf("read SET_BAUD: %v", err)
			return
		}
		if !bytes.Equal(frame[:3], []byte{0xEF, 0xBE, 0x10}) {
			t.Errorf("control frame = % x, want SET_BAUD", frame)
			return
		}
		bauds <- binary.BigEndian.Uint32(frame[3:])
		// Keep the socket open until the daemon disconnects.
		_, _ = io.Copy(io.Discard, conn)
	}()

	addr := ln.Addr().(*net.TCPAddr)
	return "127.0.0.1", addr.Port, bauds
}

// startLegacyDaemonBridge expects the raw SET_BAUD frame with no preceding
// authentication probe. It stands in for a relay-local socket whose transport
// is already protected by the relay hub.
func startLegacyDaemonBridge(t *testing.T) (string, int, <-chan uint32) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(func() { _ = ln.Close() })
	bauds := make(chan uint32, 1)

	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		_ = conn.SetDeadline(time.Now().Add(5 * time.Second))

		frame := make([]byte, 7)
		if _, err := io.ReadFull(conn, frame); err != nil {
			t.Errorf("read SET_BAUD: %v", err)
			return
		}
		if !bytes.Equal(frame[:3], []byte{0xEF, 0xBE, 0x10}) {
			t.Errorf("control frame = % x, want SET_BAUD", frame)
			return
		}
		bauds <- binary.BigEndian.Uint32(frame[3:])
		_, _ = io.Copy(io.Discard, conn)
	}()

	addr := ln.Addr().(*net.TCPAddr)
	return "127.0.0.1", addr.Port, bauds
}

func TestDaemonSerialAuthenticatesLANBridge(t *testing.T) {
	const key = "daemon-test-bridge-key"
	t.Setenv("COMPANION_BRIDGE_KEY", key)
	host, port, bauds := startAuthDaemonBridge(t, key)
	d := testDaemon(t)
	t.Cleanup(d.serialDisconnect)

	body, _ := json.Marshal(map[string]any{
		"action": "connect", "host": host, "port": port, "baud": 115200,
		"bridgeMode": "local",
	})
	rec := doReq(t, d, http.MethodPost, "/serial", d.token, body)
	if rec.Code != http.StatusOK {
		t.Fatalf("/serial status = %d, body = %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"ok":true`) {
		t.Fatalf("/serial body = %s", rec.Body.String())
	}

	select {
	case got := <-bauds:
		if got != 115200 {
			t.Fatalf("SET_BAUD = %d, want 115200", got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("bridge never received an authenticated SET_BAUD")
	}
}

func TestDaemonSerialRemoteModeSkipsBridgeAuthProbe(t *testing.T) {
	t.Setenv("COMPANION_BRIDGE_KEY", "configured-lan-key")
	host, port, bauds := startLegacyDaemonBridge(t)
	d := testDaemon(t)
	t.Cleanup(d.serialDisconnect)

	body, _ := json.Marshal(map[string]any{
		"action": "connect", "host": host, "port": port, "baud": 9600,
		"bridgeMode": "remote",
	})
	rec := doReq(t, d, http.MethodPost, "/serial", d.token, body)
	if rec.Code != http.StatusOK {
		t.Fatalf("/serial status = %d, body = %s", rec.Code, rec.Body.String())
	}

	select {
	case got := <-bauds:
		if got != 9600 {
			t.Fatalf("SET_BAUD = %d, want 9600", got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("relay-local bridge never received SET_BAUD")
	}
}

func TestDaemonSerialDialFailureKeepsBridgeTimeoutCode(t *testing.T) {
	// Reserve and release a loopback port so the dial is refused.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	_ = ln.Close()

	d := testDaemon(t)
	body, _ := json.Marshal(map[string]any{
		"action": "connect", "host": "127.0.0.1", "port": port,
		"bridgeMode": "local",
	})
	rec := doReq(t, d, http.MethodPost, "/serial", d.token, body)

	var resp rpcResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.Error == nil || resp.Error.ErrCode != "BRIDGE_TIMEOUT" {
		t.Fatalf("error = %+v, want BRIDGE_TIMEOUT", resp.Error)
	}
}

func TestDaemonSerialRejectsUnknownBridgeMode(t *testing.T) {
	d := testDaemon(t)
	body, _ := json.Marshal(map[string]any{
		"action": "connect", "host": "127.0.0.1", "port": 1, "bridgeMode": "bogus",
	})
	rec := doReq(t, d, http.MethodPost, "/serial", d.token, body)
	var resp rpcResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.Error == nil || resp.Error.Code != rpcInvalidParams {
		t.Fatalf("error = %+v, want invalid params", resp.Error)
	}
}

func TestBridgeAuthForMode(t *testing.T) {
	t.Setenv("COMPANION_BRIDGE_KEY", "env-key")
	d := testDaemon(t)

	for _, mode := range []string{"", "local"} {
		key, noAuth, err := d.bridgeAuthForMode(mode)
		if err != nil || key != "env-key" || noAuth {
			t.Fatalf("bridgeAuthForMode(%q) = %q, noAuth=%v, %v; want env-key and auth",
				mode, key, noAuth, err)
		}
	}
	key, noAuth, err := d.bridgeAuthForMode("remote")
	if err != nil || key != "" || !noAuth {
		t.Fatalf("bridgeAuthForMode(remote) = %q, noAuth=%v, %v; want empty and no-auth",
			key, noAuth, err)
	}
	if _, _, err := d.bridgeAuthForMode("bogus"); err == nil {
		t.Fatal("bridgeAuthForMode accepted an unknown mode")
	}
}
