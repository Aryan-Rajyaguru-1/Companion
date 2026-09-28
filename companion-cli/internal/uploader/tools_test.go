package uploader

import "testing"

// Tools must report every tool an upload can shell out to, with a reason it
// might be needed — the doctor output is only useful if a MISSING tool still
// explains which targets want it. Whether a tool is present is environmental,
// so only the shape is asserted here.
func TestToolsReportsEveryExternalTool(t *testing.T) {
	got := Tools(nil)
	if len(got) != 3 {
		t.Fatalf("expected esptool, avrdude and python: got %d entries", len(got))
	}
	want := map[string]bool{"esptool": false, "avrdude": false}
	for _, st := range got {
		if st.Name == "" {
			t.Error("tool status without a name")
		}
		if st.Needed == "" {
			t.Errorf("%s: missing the reason it is needed", st.Name)
		}
		if _, ok := want[st.Name]; ok {
			want[st.Name] = true
		}
		// A missing tool must come with a fix, and a found one with how it
		// resolved — otherwise the line is noise.
		if st.Found && st.Detail == "" {
			t.Errorf("%s: found but no resolution detail", st.Name)
		}
		if !st.Found && st.Hint == "" {
			t.Errorf("%s: not found and no install hint", st.Name)
		}
	}
	for name, seen := range want {
		if !seen {
			t.Errorf("%s not reported", name)
		}
	}
}
