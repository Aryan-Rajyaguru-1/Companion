package version

import "testing"

func TestCompare(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"1.8.0", "1.8.0", 0},
		{"10.0.0", "9.0.0", 1},  // numeric, not lexical
		{"9.0.0", "10.0.0", -1}, // numeric, not lexical
		{"3.10.0", "3.9.0", 1},  // digit rollover within a component
		{"2.0.0", "1.99.99", 1}, // major bump beats minor/patch pileup
		{"1.8", "1.8.0", -1},    // prefix is smaller
		{"1.8.0", "1.8", 1},
		{"3.10rc", "3.9rc", 1}, // mixed alpha-numeric components
		{"4.2rc2", "4.2rc", 1}, // suffix tie-break by content
	}
	for _, c := range cases {
		got := Compare(c.a, c.b)
		if got != c.want {
			t.Errorf("Compare(%q, %q) = %d, want %d", c.a, c.b, got, c.want)
		}
	}
}
