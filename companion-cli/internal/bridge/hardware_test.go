//go:build hwtest

// Hardware-in-the-loop test for the bridge control plane, run against a REAL
// ESP32 bridge on the local network:
//
//	go test -tags hwtest ./internal/bridge/ -run TestHWWireless -v
//
// Requires: a bridge at the address below, reachable, running esp32_bridge.
package bridge

import (
	"testing"
	"time"
)

const hwHost = "192.168.4.1"
const hwPort = 3333

func TestHWWirelessControlPlane(t *testing.T) {
	c := New(hwHost, hwPort)
	if err := c.Connect(); err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer c.Close()

	// 1. Query — protocol + firmware version round-trip.
	st, err := c.Query()
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if got := len(st); got == 0 {
		t.Fatal("Query returned empty status")
	}
	t.Logf("query: %q", st)

	// 2. Passthrough sanity: with no target attached, writing to the bridge's
	// UART must succeed as a transport operation (no echo expected back).
	c.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
	buf := make([]byte, 64)
	n, _ := c.Read(buf)
	t.Logf("passthrough pre-read: %d bytes (0 expected — target idle/absent)", n)

	// 3. Full command sequence uploadESP() performs before handing off to
	// esptool (profile → baud → enter-boot), then release.
	if err := c.SetProfile("esp32"); err != nil {
		t.Fatalf("SetProfile(esp32): %v", err)
	}
	if err := c.SetBaud(115200); err != nil {
		t.Fatalf("SetBaud: %v", err)
	}
	if err := c.EnterBootloader(); err != nil {
		t.Fatalf("EnterBootloader: %v", err)
	}
	time.Sleep(400 * time.Millisecond) // bootloader settle window as in uploader
	if err := c.Release(); err != nil {
		t.Fatalf("Release: %v", err)
	}

	// 4. Reset (pinsReset pulse) + Release.
	if err := c.Reset(); err != nil {
		t.Fatalf("Reset: %v", err)
	}
	time.Sleep(200 * time.Millisecond)
	if err := c.Release(); err != nil {
		t.Fatalf("Release #2: %v", err)
	}

	// 5. Query again — bridge must still be alive and healthy after all
	// pin actions (proves the control commands did not wedge it).
	st2, err := c.Query()
	if err != nil {
		t.Fatalf("Query #2: %v", err)
	}
	t.Logf("query after pin actions: %q", st2)

	// 6. Generic raw-stream write path (uploadGeneric's data stage).
	payload := []byte("COMAPPANIC-BRIDGE-TEST-0123456789")
	if _, err := c.Write(payload); err != nil {
		t.Fatalf("Write passthrough: %v", err)
	}
	t.Logf("wrote %d bytes through UART passthrough", len(payload))
}
