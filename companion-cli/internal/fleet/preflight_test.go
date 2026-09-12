package fleet

import (
	"strings"
	"testing"
)

func TestMacSuffix(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"companion-A1B2C3", "a1b2c3"},
		{"companion-aabbcc", "aabbcc"},
		{"kitchen-uno", ""},
		{"companion-", ""},
		{"companion-XYZ", ""},
		{"companion-A1B2C", ""},
		{"compaNION-D4E5F6", "d4e5f6"},
	}
	for _, c := range cases {
		if got := macSuffix(c.in); got != c.want {
			t.Errorf("macSuffix(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func preflightReg(t *testing.T) *Registry {
	t.Helper()
	r := New(newMemStore())
	for _, d := range []Device{
		{ID: "companion-A1B2C3", Name: "companion-A1B2C3", Host: "10.0.0.11", Port: 3232, MCU: "esp32"},
		{ID: "kitchen-uno", Name: "kitchen-uno", Host: "10.0.0.12", Port: 3232, MCU: "avr"},
		{ID: "companion-D4E5F6", Name: "companion-D4E5F6", Host: "10.0.0.13", Port: 3232, MCU: "esp32"},
	} {
		if err := r.Upsert(d); err != nil {
			t.Fatal(err)
		}
	}
	return r
}

func TestVerifyTargetsOK(t *testing.T) {
	r := preflightReg(t)
	targets := r.All()
	ads := map[string]string{
		"10.0.0.11": "companion-A1B2C3",
		"10.0.0.12": "kitchen-uno",
		"10.0.0.13": "companion-D4E5F6",
	}
	got := VerifyTargets(r, targets, ads)
	if len(got) != 3 {
		t.Fatalf("got %d preflights, want 3", len(got))
	}
	for _, p := range got {
		if p.State != PreflightOK {
			t.Errorf("device %s state=%s (%s), want ok", p.Device.Key(), p.State, p.Detail)
		}
	}
}

func TestVerifyTargetsWrongBoardMAC(t *testing.T) {
	r := preflightReg(t)
	targets := r.Select([]string{"companion-A1B2C3"})
	// The host we expect to be A1B2C3 now advertises a different MAC suffix.
	ads := map[string]string{"10.0.0.11": "companion-FF00AA"}
	got := VerifyTargets(r, targets, ads)
	if len(got) != 1 || got[0].State != PreflightFail {
		t.Fatalf("expected fail for MAC mismatch, got %+v", got)
	}
	if !strings.Contains(got[0].Detail, "wrong board") {
		t.Fatalf("detail should call out wrong board, got: %s", got[0].Detail)
	}
}

func TestVerifyTargetsUnadvertisedWarns(t *testing.T) {
	r := preflightReg(t)
	targets := r.Select([]string{"companion-A1B2C3"})
	got := VerifyTargets(r, targets, map[string]string{})
	if len(got) != 1 || got[0].State != PreflightWarn {
		t.Fatalf("expected warn for unadvertised host, got %+v", got)
	}
}

func TestVerifyTargetsAddressReuseFail(t *testing.T) {
	r := preflightReg(t)
	// Two registry entries claiming the same host.
	if err := r.Upsert(Device{ID: "another", Name: "another", Host: "10.0.0.12", Port: 3232}); err != nil {
		t.Fatal(err)
	}
	targets := r.Select([]string{"kitchen-uno"})
	ads := map[string]string{"10.0.0.12": "kitchen-uno"}
	got := VerifyTargets(r, targets, ads)
	if len(got) != 1 || got[0].State != PreflightFail {
		t.Fatalf("expected fail for address reuse, got %+v", got)
	}
}

func TestVerifyTargetsNameDriftWarns(t *testing.T) {
	r := preflightReg(t)
	targets := r.Select([]string{"kitchen-uno"})
	// Host answers, but with a non-MAC name that isn't the registered one.
	ads := map[string]string{"10.0.0.12": "office-uno"}
	got := VerifyTargets(r, targets, ads)
	if len(got) != 1 || got[0].State != PreflightWarn {
		t.Fatalf("expected warn for name drift, got %+v", got)
	}
}
