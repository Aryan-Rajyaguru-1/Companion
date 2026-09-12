package fleet

import (
	"testing"
)

// memStore is an in-memory Store for tests.
type memStore struct {
	mu   chan struct{}
	data []Device
}

func newMemStore() *memStore {
	return &memStore{mu: make(chan struct{}, 1)}
}

func (m *memStore) Load() ([]Device, error) {
	m.mu <- struct{}{}
	defer func() { <-m.mu }()
	return m.data, nil
}

func (m *memStore) Save(devs []Device) error {
	m.mu <- struct{}{}
	defer func() { <-m.mu }()
	m.data = devs
	return nil
}

func sampleRegistry(t *testing.T) *Registry {
	t.Helper()
	r := New(newMemStore())
	devs := []Device{
		{ID: "companion-A1B2C3", Name: "kitchen-uno", Host: "10.0.0.11", Port: 3232, MCU: "avr", Tags: []string{"kitchen", "uno"}},
		{ID: "companion-D4E5F6", Name: "office-esp32", Host: "10.0.0.12", Port: 3232, MCU: "esp32", Tags: []string{"office"}},
		{ID: "companion-7A8B9C", Name: "lab-nano", Host: "10.0.0.13", Port: 3232, MCU: "avr", Tags: []string{"lab", "uno"}},
	}
	for _, d := range devs {
		if err := r.Upsert(d); err != nil {
			t.Fatal(err)
		}
	}
	if err := r.Load(); err != nil {
		t.Fatal(err)
	}
	return r
}

func TestUpsertAndPersist(t *testing.T) {
	s := newMemStore()
	r := New(s)
	if err := r.Upsert(Device{ID: "a", Name: "alpha", Host: "1.2.3.4", Port: 3232}); err != nil {
		t.Fatal(err)
	}
	if len(s.data) != 1 {
		t.Fatalf("store has %d devices after one Upsert", len(s.data))
	}
	r2 := New(s)
	if err := r2.Load(); err != nil {
		t.Fatal(err)
	}
	d, ok := r2.Get("a")
	if !ok || d.Host != "1.2.3.4" {
		t.Fatalf("reloaded device missing or wrong: %+v ok=%v", d, ok)
	}
}

func TestSelectByTagAndNames(t *testing.T) {
	r := sampleRegistry(t)
	if got := r.Select([]string{"@uno"}); len(got) != 2 {
		t.Fatalf("@uno matched %d, want 2", len(got))
	}
	if got := r.Select([]string{"kitchen"}); len(got) != 1 || got[0].Key() != "companion-A1B2C3" {
		t.Fatalf("name select got %+v", got)
	}
	if got := r.Select([]string{"esp32"}); len(got) != 1 || got[0].Key() != "companion-D4E5F6" {
		t.Fatalf("mcu select got %+v", got)
	}
	if got := r.Select([]string{"@uno", "lab"}); len(got) != 1 || got[0].Key() != "companion-7A8B9C" {
		t.Fatalf("AND select got %+v", got)
	}
	if got := r.Select(nil); len(got) != 3 {
		t.Fatalf("empty selector matched %d, want 3 (all)", len(got))
	}
}

func TestRemove(t *testing.T) {
	r := sampleRegistry(t)
	if err := r.Remove("companion-A1B2C3"); err != nil {
		t.Fatal(err)
	}
	if _, ok := r.Get("companion-A1B2C3"); ok {
		t.Fatal("device still present after Remove")
	}
}

func TestFileStoreRoundTrip(t *testing.T) {
	dir := t.TempDir()
	s := FileStore{Path: dir + "/devices.yaml"}
	r := New(s)
	if err := r.Upsert(Device{ID: "companion-ABC123", Name: "sensor-1", Host: "192.168.1.5", Port: 3232, MCU: "esp32", Tags: []string{"sensors"}}); err != nil {
		t.Fatal(err)
	}
	r2 := New(s)
	if err := r2.Load(); err != nil {
		t.Fatal(err)
	}
	d, ok := r2.Get("companion-ABC123")
	if !ok || d.Name != "sensor-1" || d.MCU != "esp32" {
		t.Fatalf("file round-trip mismatch: %+v", d)
	}
}
