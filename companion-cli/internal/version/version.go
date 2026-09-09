// Package version provides semantic-version aware comparison.
//
// Board platforms, tools, and library releases must be ordered numerically:
// plain lexicographic comparison picks "9.0.0" over "10.0.0" and
// "3.10.0" over "3.9.0", which selects stale releases.
package version

import (
	"strconv"
	"strings"
)

// Compare returns -1 if a < b, 0 if a == b, and 1 if a > b.
//
// Comparison rules (a pragmatic superset of semver):
//   - Versions are split into dot-separated components.
//   - Each component is split into its leading numeric part and trailing
//     suffix ("10rc" → 10 + "rc"); the numeric parts compare numerically,
//     then the suffixes lexically.
//   - A shorter version that is a prefix of the longer one is smaller
//     ("1.8" < "1.8.0").
func Compare(a, b string) int {
	as := strings.Split(strings.TrimSpace(a), ".")
	bs := strings.Split(strings.TrimSpace(b), ".")

	for i := 0; i < len(as) || i < len(bs); i++ {
		var ac, bc string
		if i < len(as) {
			ac = as[i]
		}
		if i < len(bs) {
			bc = bs[i]
		}

		an, asuf := splitComponent(ac)
		bn, bsuf := splitComponent(bc)

		if an != bn {
			if an < bn {
				return -1
			}
			return 1
		}
		if asuf != bsuf {
			if asuf < bsuf {
				return -1
			}
			return 1
		}
	}
	return 0
}

// splitComponent splits "12ab" into (12, "ab") and "3" into (3, "").
// Non-numeric-leading components become (-1, component) so they sort
// below any numeric one deterministically.
func splitComponent(c string) (int, string) {
	i := 0
	for i < len(c) && c[i] >= '0' && c[i] <= '9' {
		i++
	}
	if i == 0 {
		return -1, c
	}
	n, err := strconv.Atoi(c[:i])
	if err != nil {
		return -1, c
	}
	return n, c[i:]
}
