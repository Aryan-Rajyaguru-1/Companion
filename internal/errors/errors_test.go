package errors

import (
	"errors"
	"strings"
	"testing"
)

func TestErrorFormatting(t *testing.T) {
	e := BoardNotFound("arduino:avr:uno")
	s := e.Error()
	if !strings.Contains(s, "BOARD_NOT_FOUND") {
		t.Errorf("formatted error should contain code, got: %s", s)
	}
	if !strings.Contains(s, "companion board install") {
		t.Errorf("formatted error should contain suggestion, got: %s", s)
	}
}

func TestErrorsIsMatchesByCode(t *testing.T) {
	a := MissingLibrary("WiFiNINA")
	b := New(ErrMissingLibrary, "other message")
	if !errors.Is(a, b) {
		t.Error("errors.Is should match on Code")
	}
	c := New(ErrLinkError, "different code")
	if errors.Is(a, c) {
		t.Error("different codes must not match")
	}
}

func TestAnalyzeGCCOutput(t *testing.T) {
	out := strings.Join([]string{
		"/path/sketch.ino:5:10: fatal error: WiFiNINA.h: No such file or directory",
		"sketch.ino:12:3: error: 'ledPin' was not declared in this scope",
		"/usr/lib/ld: undefined reference to `Serial_println'",
	}, "\n")

	errs := AnalyzeGCCOutput(out)
	if len(errs) != 3 {
		t.Fatalf("expected 3 classified errors, got %d", len(errs))
	}
	if errs[0].Code != ErrMissingHeader || errs[0].Context["header"] != "WiFiNINA.h" {
		t.Errorf("first error should be MISSING_HEADER for WiFiNINA.h, got %+v", errs[0])
	}
	if errs[1].Code != ErrUndeclaredIdent {
		t.Errorf("second error should be UNDECLARED_IDENTIFIER, got %s", errs[1].Code)
	}
	if errs[2].Code != ErrLinkError {
		t.Errorf("third error should be LINK_ERROR, got %s", errs[2].Code)
	}
}

func TestWrapPreservesCause(t *testing.T) {
	cause := errors.New("disk full")
	e := Wrap(ErrInternal, cause, "install failed")
	if !errors.Is(e, cause) {
		t.Error("Wrapped cause should be unwrappable via errors.Is")
	}
}
