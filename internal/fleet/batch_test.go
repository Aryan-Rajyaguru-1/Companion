package fleet

import (
	"context"
	"fmt"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestRunBatchAllSucceed(t *testing.T) {
	var calls int64
	push := func(ctx context.Context, d Device) error {
		atomic.AddInt64(&calls, 1)
		return nil
	}
	res := RunBatch(context.Background(), BatchOptions{
		Devices: sampleRegistry(t).All(),
		Push:    push,
	})
	if res.OK != 3 || res.Failed != 0 {
		t.Fatalf("expected 3 ok / 0 failed, got %d/%d", res.OK, res.Failed)
	}
	if calls != 3 {
		t.Fatalf("push called %d times, want 3", calls)
	}
	if len(res.Summary) != 3 {
		t.Fatalf("summary rows = %d, want 3", len(res.Summary))
	}
}

func TestRunBatchRetriesFailures(t *testing.T) {
	var attempts int64
	flaky := map[string]bool{}
	push := func(ctx context.Context, d Device) error {
		atomic.AddInt64(&attempts, 1)
		if d.Key() == "companion-D4E5F6" && !flaky[d.Key()] {
			flaky[d.Key()] = true
			return fmt.Errorf("transient wifi drop")
		}
		return nil
	}
	res := RunBatch(context.Background(), BatchOptions{
		Devices: sampleRegistry(t).All(),
		Push:    push,
		Retries: 1,
	})
	if res.OK != 3 || res.Failed != 0 {
		t.Fatalf("expected 3 ok after retry, got %d/%d (attempts=%d)", res.OK, res.Failed, attempts)
	}
	if attempts != 4 {
		t.Fatalf("attempts = %d, want 4 (2 for flaky, 1 each for others)", attempts)
	}
}

func TestRunBatchPermanentFailure(t *testing.T) {
	push := func(ctx context.Context, d Device) error {
		if d.Key() == "companion-7A8B9C" {
			return fmt.Errorf("auth failed")
		}
		return nil
	}
	res := RunBatch(context.Background(), BatchOptions{
		Devices: sampleRegistry(t).All(),
		Push:    push,
		Retries: 1,
	})
	if res.OK != 2 || res.Failed != 1 {
		t.Fatalf("expected 2 ok / 1 failed, got %d/%d", res.OK, res.Failed)
	}
	found := false
	for _, row := range res.Summary {
		if strings.Contains(row, "auth failed") {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("failure detail missing from summary: %v", res.Summary)
	}
}

func TestRunBatchRespectsConcurrency(t *testing.T) {
	var active, maxActive int64
	push := func(ctx context.Context, d Device) error {
		cur := atomic.AddInt64(&active, 1)
		for {
			prev := atomic.LoadInt64(&maxActive)
			if cur <= prev || atomic.CompareAndSwapInt64(&maxActive, prev, cur) {
				break
			}
		}
		time.Sleep(30 * time.Millisecond)
		atomic.AddInt64(&active, -1)
		return nil
	}
	devs := make([]Device, 12)
	for i := range devs {
		devs[i] = Device{ID: fmt.Sprintf("d%02d", i), Host: fmt.Sprintf("10.0.0.%d", i+1), Port: 3232}
	}
	res := RunBatch(context.Background(), BatchOptions{Devices: devs, Push: push, Concurrency: 3, Retries: 0})
	if res.Total != 12 {
		t.Fatalf("total = %d, want 12", res.Total)
	}
	if maxActive > 3 {
		t.Fatalf("max concurrency observed = %d, want <= 3", maxActive)
	}
}

func TestRunBatchContextCancelAborts(t *testing.T) {
	start := make(chan struct{})
	release := make(chan struct{})
	push := func(ctx context.Context, d Device) error {
		select {
		case <-start:
		default:
			close(start)
		}
		select {
		case <-release:
		case <-ctx.Done():
		}
		return ctx.Err()
	}
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		<-start
		cancel()
	}()
	devs := make([]Device, 4)
	for i := range devs {
		devs[i] = Device{ID: fmt.Sprintf("d%02d", i), Host: "10.0.0.1", Port: 3232}
	}
	res := RunBatch(ctx, BatchOptions{Devices: devs, Push: push, Concurrency: 2})
	if res.Total != 4 {
		t.Fatalf("total = %d, want 4", res.Total)
	}
	if res.Failed == 0 {
		t.Fatal("expected failed results after cancellation")
	}
	close(release)
}
