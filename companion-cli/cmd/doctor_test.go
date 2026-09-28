package cmd

import (
	"strings"
	"testing"
)

// The relay token travels in the /health query string, and net errors quote
// the URL they failed on. That text reaches terminals and bug reports, so
// doctor must never echo the secret — this guards the redaction.
func TestRedactURLTokenRemovesSecret(t *testing.T) {
	full := "https://ota.example.com/health?token=deadbeefcafe&x=1"
	query := "token=deadbeefcafe&x=1"
	text := `Get "https://ota.example.com/health?token=deadbeefcafe&x=1": dial tcp: no such host`

	got := redactURLToken(text, full, query)
	if strings.Contains(got, "deadbeefcafe") {
		t.Fatalf("token survived redaction: %q", got)
	}
	if !strings.Contains(got, "no such host") {
		t.Fatalf("redaction ate the actual error: %q", got)
	}
	if !strings.Contains(got, "token=…") {
		t.Fatalf("expected a placeholder in place of the token: %q", got)
	}
}

// No query (unauthenticated /health, or no token in the environment) means
// nothing to redact and no reason to rewrite the message.
func TestRedactURLTokenNoQueryIsPassthrough(t *testing.T) {
	text := `Get "https://ota.example.com/health": no such host`
	if got := redactURLToken(text, "https://ota.example.com/health", ""); got != text {
		t.Fatalf("expected passthrough, got %q", got)
	}
}

// A URL with no scheme is rejected locally, before any network call — the
// check earns its keep by not hanging on a typo.
func TestDoctorHubRejectsSchemelessURL(t *testing.T) {
	if err := doctorCheckHub("ota.example.com"); err == nil {
		t.Fatal("expected an error for a URL with no ws:// or wss:// scheme")
	}
}
