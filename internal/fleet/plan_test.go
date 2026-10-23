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

// Finish mode replays the phase-1 canary positionally: it must target exactly
// the held-back remainder — same size, same members — so --dry-run on phase 2
// shows the complement of phase 1's report.
func TestBuildPlanFinishTargetsTheRemainder(t *testing.T) {
	r := sampleRegistry(t)
	all := r.All()
	phase1 := BuildPlan(r, PlanOptions{Canary: 1, Workers: 4})
	phase2 := BuildPlan(r, PlanOptions{Canary: 1, FinishWith: true, Workers: 4})
	if len(phase2.Targets) != len(all)-1 {
		t.Fatalf("finish targets = %d, want remainder %d", len(phase2.Targets), len(all)-1)
	}
	held := map[string]bool{}
	for _, d := range phase1.Remaining() {
		held[d.Key()] = true
	}
	for _, d := range phase2.Targets {
		if !held[d.Key()] {
			t.Errorf("finish targets %s, which was not held back in phase 1", d.Key())
		}
		if d.Key() == phase1.Targets[0].Key() {
			t.Errorf("finish re-targets the phase-1 canary device %s", d.Key())
		}
	}
	for _, s := range phase2.Skipped {
		if !strings.Contains(s.Reason, "finished") {
			t.Errorf("finish skip reason should explain the canary was done: %q", s.Reason)
		}
	}
}

// A canary is only deterministic while the registry is unchanged: registering
// a board between phase 1 and phase 2 reorders the remainder, and the plan
// must still target exactly "everything except the first N" rather than
// replaying stale membership.
func TestBuildPlanFinishAfterRegistryDrift(t *testing.T) {
	r := sampleRegistry(t)
	phase1 := BuildPlan(r, PlanOptions{Canary: 1, Workers: 4})
	phase1Canary := phase1.Targets[0].Key()
	// A board registered before every existing ID sorts FIRST — inside the
	// replayed canary window — so the remainder shifts: phase-1's canary
	// device is now IN the remainder, and only the new board is held back.
	if err := r.Upsert(Device{ID: "companion-000000", Name: "early-board", Host: "10.0.0.1", Port: 3232, MCU: "avr"}); err != nil {
		t.Fatal(err)
	}
	phase2 := BuildPlan(r, PlanOptions{Canary: 1, FinishWith: true, Workers: 4})
	if len(phase2.Targets) != len(r.All())-1 {
		t.Fatalf("finish after drift targets = %d, want %d", len(phase2.Targets), len(r.All())-1)
	}
	if len(phase2.Skipped) != 1 || phase2.Skipped[0].Device.Key() != "companion-000000" {
		t.Fatalf("drift must hold back only the new board, got %+v", phase2.Skipped)
	}
	found := false
	for _, d := range phase2.Targets {
		if d.Key() == phase1Canary {
			found = true
		}
	}
	if !found {
		t.Errorf("phase-1 canary %s should be in the shifted remainder", phase1Canary)
	}
}

// Boards PROVEN current by --skip-if-version are excluded in finish mode too,
// even when they sat inside the original canary window — the version record
// always beats the positional replay.
func TestBuildPlanFinishExcludesConfirmedDevices(t *testing.T) {
	r := sampleRegistry(t)
	devs := r.All()
	devs[0].Version = "1.2.0"
	if err := r.Upsert(devs[0]); err != nil {
		t.Fatal(err)
	}
	phase2 := BuildPlan(r, PlanOptions{Canary: 1, FinishWith: true, SkipIfVersion: "1.2.0", Workers: 4})
	for _, d := range phase2.Targets {
		if d.Key() == devs[0].Key() {
			t.Errorf("confirmed-current device %s must not be re-flashed in finish mode", d.Key())
		}
	}
	found := false
	for _, s := range phase2.Skipped {
		if s.Device.Key() == devs[0].Key() && strings.Contains(s.Reason, "finished") {
			found = true
		}
	}
	if !found {
		t.Error("confirmed-current device should be skipped with a (finished) reason")
	}
}

// --finish-with with no --canary is meaningless: there is no canary to replay,
// and silently flashing everything again is exactly what the operator feared.
func TestValidatePlanOptionsRejectsFinishWithoutCanary(t *testing.T) {
	if err := ValidatePlanOptions(PlanOptions{FinishWith: true}); err == nil {
		t.Fatal("expected an error for --finish-with without --canary")
	}
	if err := ValidatePlanOptions(PlanOptions{FinishWith: false, Canary: 2}); err != nil {
		t.Fatalf("ordinary canary must stay valid: %v", err)
	}
	if err := ValidatePlanOptions(PlanOptions{FinishWith: true, Canary: 2}); err != nil {
		t.Fatalf("finish replay must be valid: %v", err)
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
