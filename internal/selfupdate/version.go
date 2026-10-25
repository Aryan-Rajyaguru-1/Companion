package selfupdate

import (
	"strconv"
	"strings"

	internalversion "github.com/companion-ide/companion-cli/internal/version"
)

// CompareVersions orders release tags using semantic-version rules: numeric
// core components compare numerically, a final release sorts after its
// prereleases, and prerelease identifiers use semver's numeric/lexical order.
// A leading "v" and build metadata are ignored.
//
// Board/platform versions still use internal/version.Compare; this helper is
// specific to release tags so the updater does not offer v1.0.0-rc1 over
// v1.0.0.
func CompareVersions(a, b string) int {
	ac, apre, aok := parseReleaseVersion(a)
	bc, bpre, bok := parseReleaseVersion(b)
	if aok && bok {
		for i := 0; i < len(ac) || i < len(bc); i++ {
			var av, bv uint64
			if i < len(ac) {
				av = ac[i]
			}
			if i < len(bc) {
				bv = bc[i]
			}
			if av < bv {
				return -1
			}
			if av > bv {
				return 1
			}
		}
		return comparePrerelease(apre, bpre)
	}

	// Fall back to the project's pragmatic comparator for non-semver tags.
	// This keeps comparisons deterministic for unusual local builds.
	return internalversion.Compare(strings.TrimPrefix(strings.TrimSpace(a), "v"), strings.TrimPrefix(strings.TrimSpace(b), "v"))
}

// IsNewer reports whether latest is a meaningful upgrade over current.
// Development and unparseable local versions are treated as upgradeable; a
// normal semver current version must be strictly older.
func IsNewer(latest, current string) bool {
	current = normalizeVersion(current)
	if current == "" || strings.EqualFold(current, "dev") || strings.HasPrefix(strings.ToLower(current), "dev-") {
		return true
	}
	if _, _, ok := parseReleaseVersion(current); !ok {
		return true
	}
	return CompareVersions(latest, current) > 0
}

func normalizeVersion(v string) string {
	v = strings.TrimSpace(v)
	v = strings.TrimPrefix(v, "v")
	v = strings.TrimPrefix(v, "V")
	return v
}

func parseReleaseVersion(v string) ([]uint64, string, bool) {
	v = normalizeVersion(v)
	if v == "" {
		return nil, "", false
	}
	if i := strings.IndexByte(v, '+'); i >= 0 {
		v = v[:i]
	}
	pre := ""
	if i := strings.IndexByte(v, '-'); i >= 0 {
		pre = v[i+1:]
		v = v[:i]
		if pre == "" {
			return nil, "", false
		}
	}
	parts := strings.Split(v, ".")
	core := make([]uint64, 0, len(parts))
	for _, part := range parts {
		if part == "" {
			return nil, "", false
		}
		// semver forbids leading zeroes, but release tooling occasionally
		// emits them. Parsing them numerically is safer than treating the tag
		// as unorderable.
		n, err := strconv.ParseUint(part, 10, 64)
		if err != nil {
			return nil, "", false
		}
		core = append(core, n)
	}
	return core, pre, true
}

func comparePrerelease(a, b string) int {
	if a == b {
		return 0
	}
	if a == "" {
		return 1 // final release > prerelease
	}
	if b == "" {
		return -1
	}
	as := strings.Split(a, ".")
	bs := strings.Split(b, ".")
	for i := 0; i < len(as) || i < len(bs); i++ {
		if i >= len(as) {
			return -1 // shorter prerelease list is lower when prefixes match
		}
		if i >= len(bs) {
			return 1
		}
		an, aNum := numericIdentifier(as[i])
		bn, bNum := numericIdentifier(bs[i])
		switch {
		case aNum && bNum:
			if an < bn {
				return -1
			}
			if an > bn {
				return 1
			}
		case aNum && !bNum:
			return -1 // numeric identifiers sort before alphanumeric
		case !aNum && bNum:
			return 1
		default:
			if as[i] < bs[i] {
				return -1
			}
			if as[i] > bs[i] {
				return 1
			}
		}
	}
	return 0
}

func numericIdentifier(s string) (uint64, bool) {
	if s == "" {
		return 0, false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseUint(s, 10, 64)
	return n, err == nil
}
