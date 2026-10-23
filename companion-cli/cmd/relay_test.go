package cmd

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// The hub deliberately answers an unauthenticated /health with liveness only
// ({"ok":true}) so it cannot leak the device inventory. A bad token must not
// therefore look like an idle hub: `relay devices` has to distinguish the
// missing "devices" field from an authenticated empty list.
func TestRelayDevicesRejectsLivenessOnlyResponse(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("path = %q, want /health", r.URL.Path)
		}
		if got, want := r.Header.Get("Authorization"), "Bearer wrong"; got != want {
			t.Errorf("Authorization = %q, want %q", got, want)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	cmd := newRelayCmd()
	cmd.SetArgs([]string{"devices", "--hub", srv.URL, "--token", "wrong"})
	if err := cmd.Execute(); err == nil {
		t.Fatal("relay devices accepted a liveness-only response as an empty device list")
	}
}

func TestRelayDevicesAcceptsAuthenticatedEmptyList(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got, want := r.Header.Get("Authorization"), "Bearer agent-token"; got != want {
			t.Errorf("Authorization = %q, want %q", got, want)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"devices":[]}`))
	}))
	defer srv.Close()

	cmd := newRelayCmd()
	cmd.SetArgs([]string{"devices", "--hub", srv.URL, "--token", "agent-token"})
	if err := cmd.Execute(); err != nil {
		t.Fatalf("relay devices rejected an authenticated empty list: %v", err)
	}
}
