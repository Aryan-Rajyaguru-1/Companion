package fleet

import (
	"fmt"
	"sort"
	"strings"
)

// Skip records a device that matched the selectors but will NOT be flashed,
// and why. Skips are shown to the operator rather than silently dropped: a
// rollout that quietly excludes 40 of 50 boards looks identical to one that
// flashed all 50 until something fails to boot.
type Skip struct {
	Device Device
	Reason string
}

// Plan is a fully-resolved push, computed before anything is written to a
// board. It is what --dry-run prints and what --canary slices.
type Plan struct {
	Targets     []Device
	Skipped     []Skip
	Workers     int
	Waves       int
	EstSeconds  int    // rough wall-clock estimate
	ImageBytes  int64  // 0 when unknown
	DeployVer   string // the version being deployed (--mark-version)
	VersionFrom string // how DeployVer was established
}

// PlanOptions describes the intent; BuildPlan turns it into a Plan.
type PlanOptions struct {
	Selectors []string
	// SkipIfVersion skips devices already reporting this firmware, which is
	// what makes a rollout re-runnable: the second run has nothing to do.
	SkipIfVersion string
	// Canary limits the first wave to N devices. 0 = flash everything.
	Canary int
	// FinishWith replays a canary of size Canary and targets only the
	// remainder: the first Canary matches are held back positionally.
	// The registry can prove a board is already flashed only on paths that
	// report a version; for the version-unknown boards left over, canary
	// ORDER is the only identity phase 1 and phase 2 share.
	FinishWith        bool
	Workers           int
	ImageBytes        int64
	EstPushSeconds    int
	DeployVer         string
	DeployVerDeclared bool
}

const maxVersionLen = 64 // guard against garbage clogging the plan report

// ValidatePlanOptions rejects flag combinations that cannot mean anything,
// before any plan is built or device contacted. --finish-with without
// --canary has no canary to replay, so it would silently flash everything
// again — exactly the outcome the operator is trying to avoid.
func ValidatePlanOptions(opts PlanOptions) error {
	if opts.FinishWith && opts.Canary <= 0 {
		return fmt.Errorf("--finish-with needs --canary N: the finish phase replays the phase-1 canary to find the remainder")
	}
	if opts.Canary < 0 {
		return fmt.Errorf("--canary must be >= 0")
	}
	if len(opts.SkipIfVersion) > maxVersionLen {
		return fmt.Errorf("--skip-if-version is too long (%d chars)", len(opts.SkipIfVersion))
	}
	return nil
}

// BuildPlan resolves selectors, applies the version filter, and computes the
// wave plan. It performs no I/O against devices — only the local registry —
// so it is safe to call for a preview.
func BuildPlan(reg *Registry, opts PlanOptions) Plan {
	selected := reg.Select(opts.Selectors)

	workers := opts.Workers
	if workers <= 0 {
		workers = 4
	}
	est := opts.EstPushSeconds
	if est <= 0 {
		est = 165 // measured: a 1.2 MB relay push takes ~2m45s
	}

	plan := Plan{
		Workers:     workers,
		ImageBytes:  opts.ImageBytes,
		DeployVer:   opts.DeployVer,
		VersionFrom: "hub reports at pairing",
	}
	if opts.DeployVerDeclared {
		plan.VersionFrom = "--mark-version (declared, not verified)"
	}

	finish := opts.FinishWith
	want := strings.TrimSpace(opts.SkipIfVersion)
	for _, d := range selected {
		// Only skip a device we actually KNOW is current. An unknown
		// version (LAN path, legacy firmware) must still be flashed — the
		// LAN ArduinoOTA protocol exposes no version at all, so treating
		// "" as current would silently exclude every LAN board.
		// In finish mode a proven-current board is labelled "(finished)":
		// it is not part of the remainder, even if it sat inside the
		// original canary.
		if want != "" && d.Version != "" && d.Version == want {
			reason := fmt.Sprintf("already on %s", d.Version)
			if finish {
				reason = fmt.Sprintf("already on %s (finished)", d.Version)
			}
			plan.Skipped = append(plan.Skipped, Skip{Device: d, Reason: reason})
			continue
		}
		plan.Targets = append(plan.Targets, d)
	}

	// Deterministic canary order (registry order is already id-sorted) so a
	// rerun picks the same boards — a canary you cannot repeat is a coin flip.
	// Finish mode replays that same order positionally: the first Canary
	// matches of phase 1's canary are assumed already flashed, because
	// recordResults only learns versions on the relay path — a LAN wave-1
	// push, or one run without --mark-version, leaves the registry with
	// nothing to skip on. Versioned devices are excluded above; what remains
	// here are the version-unknown boards, for which registry ORDER is the
	// only stable identity phase 1 and phase 2 share.
	if opts.Canary > 0 && len(plan.Targets) > opts.Canary {
		if finish {
			// Phase 2: hold back the first N (phase 1's canary), flash the rest.
			for _, d := range plan.Targets[:opts.Canary] {
				plan.Skipped = append(plan.Skipped, Skip{Device: d,
					Reason: fmt.Sprintf("flashed in canary wave (--canary %d finished)", opts.Canary)})
			}
			plan.Targets = plan.Targets[opts.Canary:]
		} else {
			// Phase 1: flash the first N, hold the rest back explicitly.
			for _, d := range plan.Targets[opts.Canary:] {
				plan.Skipped = append(plan.Skipped, Skip{Device: d,
					Reason: "held back by --canary"})
			}
			plan.Targets = plan.Targets[:opts.Canary]
		}
	}
	sort.Slice(plan.Skipped, func(i, j int) bool {
		return plan.Skipped[i].Device.Key() < plan.Skipped[j].Device.Key()
	})

	plan.Waves = (len(plan.Targets) + workers - 1) / workers
	plan.EstSeconds = plan.Waves * est
	return plan
}

// Report renders the plan for a human: what will be flashed, what will not and
// why, and how long it should take. Used by both the confirmation prompt and
// --dry-run, so the operator sees the same thing either way.
func (p Plan) Report() string {
	var b strings.Builder
	if p.DeployVer != "" {
		fmt.Fprintf(&b, "Deploying version: %s  (%s)\n", p.DeployVer, p.VersionFrom)
	}
	fmt.Fprintf(&b, "Will flash %d device(s)", len(p.Targets))
	if p.ImageBytes > 0 {
		fmt.Fprintf(&b, "  (%.1f MB each, %d MB total)",
			float64(p.ImageBytes)/(1<<20), len(p.Targets)*int(p.ImageBytes)/(1<<20))
	}
	fmt.Fprintf(&b, "  workers=%d  waves=%d  est %s\n",
		p.Workers, p.Waves, humanDuration(p.EstSeconds))
	for _, d := range p.Targets {
		cur := d.Version
		if cur == "" {
			cur = "unknown"
		}
		fmt.Fprintf(&b, "  → %-24s %-16s current: %s\n", d.Key(), hostOrDash(d.Host), cur)
	}
	if len(p.Skipped) > 0 {
		fmt.Fprintf(&b, "Skipping %d:\n", len(p.Skipped))
		for _, s := range p.Skipped {
			fmt.Fprintf(&b, "  – %-24s %s\n", s.Device.Key(), s.Reason)
		}
	}
	return b.String()
}

// Remaining returns the devices held back by a canary, so the second phase of
// a staged rollout can be run explicitly.
func (p Plan) Remaining() []Device {
	var out []Device
	for _, s := range p.Skipped {
		if s.Reason == "held back by --canary" {
			out = append(out, s.Device)
		}
	}
	return out
}

func hostOrDash(h string) string {
	if strings.TrimSpace(h) == "" {
		return "-"
	}
	return h
}

func humanDuration(sec int) string {
	if sec <= 0 {
		return "unknown"
	}
	if sec < 60 {
		return fmt.Sprintf("%ds", sec)
	}
	m := sec / 60
	s := sec % 60
	if s == 0 {
		return fmt.Sprintf("%dm", m)
	}
	return fmt.Sprintf("%dm%02ds", m, s)
}
