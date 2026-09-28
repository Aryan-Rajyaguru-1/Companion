package fleet

import (
	"strings"
	"testing"
)

// A rollout must be able to exclude devices that are already on the target
// version — that is what makes it re-runnable, and at 50 devices it is the
// difference between a staged rollout and a coin flip.
func TestBuildPlanSkipsAlreadyCurrent(t *testing.T) {
	r := sampleRegistry(t)
	// Mark two devices as already running the version we are deploying.
	devs := r.All()
	for i := range devs {
		if i < 2 {
			devs[i].Version = "1.2.0"
			r.Upsert(devs[i])
		}
	}
	plan := BuildPlan(r, PlanOptions{SkipIfVersion: "1.2.0", Workers: 4})
	if len(plan.Skipped) != 2 {
		t.Fatalf("expected 2 skips, got %d (%+v)", len(plan.Skipped), plan.Skipped)
	}
	for _, s := range plan.Skipped {
		if !strings.Contains(s.Reason, "already on") {
			t.Errorf("skip reason should say why: %q", s.Reason)
		}
	}
	if len(plan.Targets) != len(r.All())-2 {
		t.Fatalf("targets = %d, want %d", len(plan.Targets), len(r.All())-2)
	}
}

// An UNKNOWN version must never be treated as current. The LAN ArduinoOTA
// path reports no version at all, so a naive "skip if version matches empty"
// would silently exclude every LAN board from every update.
func TestBuildPlanNeverSkipsUnknownVersion(t *testing.T) {
	r := sampleRegistry(t)
	for _, d := range r.All() {
		if d.Version == "" {
			// Simulate a LAN device: no version reported.
		}
	}
	plan := BuildPlan(r, PlanOptions{SkipIfVersion: "", Workers: 2})
	if len(plan.Targets) != len(r.All()) {
		t.Fatalf("no filter must keep every device: %d of %d", len(plan.Targets), len(r.All()))
	}
	// And a filter must not skip a device whose version is merely empty.
	plan2 := BuildPlan(r, PlanOptions{SkipIfVersion: "1.2.0", Workers: 2})
	for _, s := range plan2.Skipped {
		if s.Device.Version == "" {
			t.Errorf("device with unknown version was skipped: %+v", s.Device)
		}
	}
}

// A canary must take the FIRST N in deterministic order and hold the rest
// back explicitly, so a rerun picks the same boards.
func TestBuildPlanCanaryHoldsBackTheRest(t *testing.T) {
	r := sampleRegistry(t)
	all := r.All()
	if len(all) < 3 {
		t.Skip("sample registry too small")
	}
	plan := BuildPlan(r, PlanOptions{Canary: 1, Workers: 4})
	if len(plan.Targets) != 1 {
		t.Fatalf("canary targets = %d, want 1", len(plan.Targets))
	}
	rem := plan.Remaining()
	if len(rem) != len(all)-1 {
		t.Fatalf("remaining = %d, want %d", len(rem), len(all)-1)
	}
	for _, d := range rem {
		if d.Key() == plan.Targets[0].Key() {
			t.Fatal("canary device also held back")
		}
	}
	// Deterministic: the same input picks the same canary.
	plan2 := BuildPlan(r, PlanOptions{Canary: 1, Workers: 4})
	if plan2.Targets[0].Key() != plan.Targets[0].Key() {
		t.Fatalf("canary is not deterministic: %q then %q", plan.Targets[0].Key(), plan2.Targets[0].Key())
	}
}

// Waves and the estimate must reflect concurrency, so the operator can judge a
// 50-device run before committing to it.
func TestBuildPlanWavesAndEstimate(t *testing.T) {
	r := sampleRegistry(t)
	n := len(r.All())
	plan := BuildPlan(r, PlanOptions{Workers: 2, EstPushSeconds: 100})
	wantWaves := (n + 1) / 2
	if plan.Waves != wantWaves {
		t.Fatalf("waves = %d, want ceil(%d/2)=%d", plan.Waves, n, wantWaves)
	}
	if plan.EstSeconds != plan.Waves*100 {
		t.Fatalf("estimate = %ds, want %ds", plan.EstSeconds, plan.Waves*100)
	}
	if !strings.Contains(plan.Report(), "Will flash") {
		t.Error("report should state the flash count")
	}
	if !strings.Contains(plan.Report(), "est ") {
		t.Error("report should state an estimate")
	}
}

// "+" ORed selectors, alongside the existing AND behaviour.
func TestSelectOrSemantics(t *testing.T) {
	r := sampleRegistry(t)
	and := r.Select([]string{"@uno", "lab"})
	or := r.Select([]string{"+@uno", "+@lab"})
	if len(or) < len(and) {
		t.Fatalf("OR (%d) should select at least as many as AND (%d)", len(or), len(and))
	}
	for _, d := range or {
		if !d.Match("@uno") && !d.Match("@lab") {
			t.Errorf("device %s matches neither optional selector", d.Key())
		}
	}
}
