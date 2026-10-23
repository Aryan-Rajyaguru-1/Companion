package cmd

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// The relay token must travel in the Authorization header, never in the
// /health URL: URLs reach proxy access logs, terminal error messages and bug
// reports. This also proves doctor sends the header exactly once.
func TestDoctorCheckHubUsesAuthorizationHeader(t *testing.T) {
	const token = "deadbeefcafe"
	var sawAuth string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sawAuth = r.Header.Get("Authorization")
		if r.URL.RawQuery != "" {
			t.Errorf("doctor put a query string on /health: %q", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"devices":[]}`))
	}))
	defer srv.Close()

	t.Setenv("COMPANION_RELAY_AGENTS_TOKEN", token)
	if err := doctorCheckHub(srv.URL); err != nil {
		t.Fatalf("doctorCheckHub: %v", err)
	}
	if want := "Bearer " + token; sawAuth != want {
		t.Fatalf("Authorization header = %q, want %q", sawAuth, want)
	}
}

// A rejected token gets the same liveness-only body as an unauthenticated
// probe. Doctor must report that as a failed auth check, not "no devices
// online", or an operator will debug the board instead of the token.
func TestDoctorHubRejectsTokenThatGetsLivenessOnly(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got, want := r.Header.Get("Authorization"), "Bearer bad-token"; got != want {
			t.Errorf("Authorization = %q, want %q", got, want)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	t.Setenv("COMPANION_RELAY_AGENTS_TOKEN", "bad-token")
	if err := doctorCheckHub(srv.URL); err == nil {
		t.Fatal("doctor accepted a liveness-only response after sending a token")
	}
}

// A URL with no scheme is rejected locally, before any network call — the
// check earns its keep by not hanging on a typo.
func TestDoctorHubRejectsSchemelessURL(t *testing.T) {
	if err := doctorCheckHub("ota.example.com"); err == nil {
		t.Fatal("expected an error for a URL with no ws:// or wss:// scheme")
	}
}
