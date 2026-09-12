// Package registry implements the Companion device registry — a durable
// catalog of OTA-capable boards keyed by stable identity (name or MAC-derived
// hostname), with select-by-filter and bounded-concurrency fleet push.
package fleet

import (
	"sort"
	"strings"
	"sync"
	"time"
)

// Device is one OTA-capable board known to the registry.
type Device struct {
	ID     string    `yaml:"id"`            // stable ID: registry name or MAC-derived hostname
	Name   string    `yaml:"name"`          // friendly name (may equal ID)
	MAC    string    `yaml:"mac,omitempty"` // last-seen MAC, "" when unknown
	Host   string    `yaml:"host"`          // device IP
	Port   int       `yaml:"port"`          // OTA port (3232 default)
	MCU    string    `yaml:"mcu,omitempty"` // esp32 | esp8266 | avr | stm32 | generic
	Tags   []string  `yaml:"tags,omitempty"`
	SeenAt time.Time `yaml:"seen_at"`
}

// ID returns the stable key for a device.
func (d Device) Key() string {
	if d.ID != "" {
		return d.ID
	}
	return d.Name
}

// Match reports whether the device matches a selector.
// @<tag> matches a tag; otherwise the term matches ID, Name, MAC, Host, MCU
// (case-insensitive substring).
func (d Device) Match(sel string) bool {
	sel = strings.TrimSpace(sel)
	if sel == "" {
		return true
	}
	if strings.HasPrefix(sel, "@") {
		t := strings.TrimPrefix(sel, "@")
		for _, tag := range d.Tags {
			if strings.EqualFold(tag, t) {
				return true
			}
		}
		return false
	}
	selL := strings.ToLower(sel)
	fields := []string{d.Key(), d.Name, d.MAC, d.Host, d.MCU}
	for _, f := range fields {
		if strings.Contains(strings.ToLower(f), selL) {
			return true
		}
	}
	return false
}

// Registry is an in-memory device catalog backed by a Store.
type Registry struct {
	mu      sync.RWMutex
	store   Store
	devices map[string]*Device // key: stable ID
}

// Store persists the device catalog.
type Store interface {
	Load() ([]Device, error)
	Save([]Device) error
}

// New builds a Registry from a Store (which may be a file-backed store).
func New(s Store) *Registry {
	return &Registry{store: s, devices: map[string]*Device{}}
}

// Load reads all devices from the store into memory.
func (r *Registry) Load() error {
	all, err := r.store.Load()
	if err != nil {
		return err
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.devices = map[string]*Device{}
	for i := range all {
		d := all[i]
		if d.ID == "" {
			d.ID = d.Name
		}
		r.devices[d.ID] = &d
	}
	return nil
}

// Upsert adds or updates a device, keyed by its stable ID.
func (r *Registry) Upsert(d Device) error {
	r.mu.Lock()
	if d.ID == "" {
		d.ID = d.Name
	}
	d.SeenAt = time.Now().UTC()
	r.devices[d.ID] = &d
	all := r.snapshotLocked()
	r.mu.Unlock()
	return r.store.Save(all)
}

// Get returns a device by stable ID.
func (r *Registry) Get(id string) (*Device, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	d, ok := r.devices[id]
	if !ok {
		return nil, false
	}
	cp := *d
	return &cp, true
}

// All returns a sorted snapshot of all devices.
func (r *Registry) All() []Device {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.snapshotLocked()
}

func (r *Registry) snapshotLocked() []Device {
	out := make([]Device, 0, len(r.devices))
	for _, d := range r.devices {
		out = append(out, *d)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Key() < out[j].Key() })
	return out
}

// Select returns the devices matching all selectors (AND) in ID order.
// An empty selector list matches every device.
func (r *Registry) Select(selectors []string) []Device {
	all := r.All()
	var out []Device
	for _, d := range all {
		ok := true
		for _, sel := range selectors {
			if sel == "" {
				continue
			}
			if !d.Match(sel) {
				ok = false
				break
			}
		}
		if ok {
			out = append(out, d)
		}
	}
	return out
}

// Remove deletes a device by stable ID and persists the change.
func (r *Registry) Remove(id string) error {
	r.mu.Lock()
	delete(r.devices, id)
	all := r.snapshotLocked()
	r.mu.Unlock()
	return r.store.Save(all)
}
