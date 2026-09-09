package cmd

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/companion-ide/companion-cli/internal/config"
)

func testDaemon(t *testing.T) *daemonServer {
	t.Helper()
	cfg := &config.Config{}
	cfg.Directories.Data = t.TempDir() // isolated cache/index dirs
	d, err := newDaemonServer(cfg)
	if err != nil {
		t.Fatalf("newDaemonServer: %v", err)
	}
	return d
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
