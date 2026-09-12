package fleet

import (
	"fmt"
	"strings"
)

// Discovered is one OTA device seen via mDNS (host/name/port).
// The advertised Name for Companion bridges is "companion-XXXXXX" derived from
// the last 3 MAC bytes, giving each board a stable, verifiable identity.
type Discovered struct {
	Host string
	Name string
	Port int
}

// PreflightState classifies an identity-check outcome.
type PreflightState int

const (
	PreflightOK PreflightState = iota
	PreflightWarn
	PreflightFail
)

func (s PreflightState) String() string {
	switch s {
	case PreflightWarn:
		return "warn"
	case PreflightFail:
		return "fail"
	}
	return "ok"
}

// Preflight is one target's identity-verification result.
type Preflight struct {
	Device Device
	State  PreflightState
	Detail string
}

// macSuffix extracts the 6-hex companion-XXXXXX MAC suffix from an mDNS name,
// or returns "" when the name is not one of ours. Example:
//
//	"companion-A1B2C3" → "a1b2c3"
func macSuffix(name string) string {
	n := strings.ToLower(strings.TrimSpace(name))
	const prefix = "companion-"
	if !strings.HasPrefix(n, prefix) {
		return ""
	}
	suf := n[len(prefix):]
	if len(suf) != 6 {
		return ""
	}
	for _, c := range suf {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			return ""
		}
	}
	return suf
}

func hostnamesMatch(a, b string) bool {
	return strings.EqualFold(strings.TrimSpace(a), strings.TrimSpace(b))
}

// VerifyTargets checks each target's registered identity against live mDNS
// advertisements (host → advertised name). reg holds all registered devices so
// address-reuse (a different board now answering at a registered IP, or two
// entries claiming the same host/name) is caught before anything is flashed.
func VerifyTargets(reg *Registry, targets []Device, advertisements map[string]string) []Preflight {
	res := make([]Preflight, 0, len(targets))
	for _, t := range targets {
		p := Preflight{Device: t, State: PreflightOK, Detail: "identity verified"}
		adv, seen := advertisements[t.Host]
		if !seen {
			p.State = PreflightWarn
			p.Detail = fmt.Sprintf("no mDNS advertisement observed for %s — identity not independently verified", t.Host)
			res = append(res, p)
			continue
		}

		// Wrong-board guard: both sides carry MAC-derived suffixes and they differ.
		mt := macSuffix(t.Name)
		ma := macSuffix(adv)
		if mt != "" && ma != "" && mt != ma {
			p.State = PreflightFail
			p.Detail = fmt.Sprintf("host %s advertises %q (MAC %s) but registry expects %q (MAC %s) — wrong board?",
				t.Host, adv, strings.ToUpper(ma), t.Name, strings.ToUpper(mt))
			res = append(res, p)
			continue
		}

		// Same-name check: a non-MAC registered name should match the advertisement.
		if t.Name != "" && !hostnamesMatch(t.Name, adv) {
			p.State = PreflightWarn
			p.Detail = fmt.Sprintf("host %s advertises %q (registry name: %q)", t.Host, adv, t.Name)
			res = append(res, p)
			continue
		}

		// Address ownership: no other registered device may share this host or name.
		if reg != nil {
			for _, other := range reg.All() {
				if other.Key() == t.Key() {
					continue
				}
				if hostnamesMatch(other.Host, t.Host) {
					p.State = PreflightFail
					p.Detail = fmt.Sprintf("host %s is also registered to %q (registry) — address reuse or swapped boards?", t.Host, other.Key())
					break
				}
				if hostnamesMatch(other.Name, adv) || hostnamesMatch(other.Name, t.Name) {
					p.State = PreflightWarn
					p.Detail = fmt.Sprintf("advertised/registered name %q already belongs to registry device %q", adv, other.Key())
					break
				}
			}
		}
		res = append(res, p)
	}
	return res
}
