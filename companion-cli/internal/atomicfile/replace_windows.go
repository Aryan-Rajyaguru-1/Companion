//go:build windows

package atomicfile

import (
	"syscall"
	"unsafe"
)

const (
	moveFileReplaceExisting = 0x1
	moveFileWriteThrough    = 0x8
)

var moveFileExW = syscall.NewLazyDLL("kernel32.dll").NewProc("MoveFileExW")

// Replace moves src over dest with MoveFileExW. Unlike os.Rename on Windows,
// it replaces an existing destination (the token and relay secrets files are
// rewritten on every start/registration) and flushes the move through.
func Replace(src, dest string) error {
	srcPtr, err := syscall.UTF16PtrFromString(src)
	if err != nil {
		return err
	}
	destPtr, err := syscall.UTF16PtrFromString(dest)
	if err != nil {
		return err
	}
	ok, _, callErr := moveFileExW.Call(
		uintptr(unsafe.Pointer(srcPtr)),
		uintptr(unsafe.Pointer(destPtr)),
		moveFileReplaceExisting|moveFileWriteThrough,
	)
	if ok != 0 {
		return nil
	}
	if callErr != syscall.Errno(0) {
		return callErr
	}
	return syscall.EINVAL
}
