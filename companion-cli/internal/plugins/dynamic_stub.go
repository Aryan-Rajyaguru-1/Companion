//go:build !linux || !cgo

package plugins

// loadDynamic is a no-op on platforms where Go's plugin package is
// unavailable (the Linux+cgo path in dynamic_linux.go handles real .so load).
func loadDynamic(dir string) ([]Plugin, []error) {
	return nil, nil
}
