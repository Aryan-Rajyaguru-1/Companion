package fleet

import (
	"context"
	"fmt"
	"sort"
	"sync"
)

// PushFunc pushes the image to one device and returns an error on failure.
type PushFunc func(ctx context.Context, d Device) error

// BatchOptions configures a fleet push.
type BatchOptions struct {
	Devices     []Device // resolved target list (exactly what will be flashed)
	ImagePath   string   // pre-compiled binary path
	Push        PushFunc // per-device push implementation (default ota.Push wrapper)
	Concurrency int      // bounded worker count; 0 → 4
	Retries     int      // automatic retries per failing device; 0 → 1
}

// Retry generous defaults so a fresh call is safe.
func (b *BatchOptions) norm() {
	if b.Concurrency <= 0 {
		b.Concurrency = 4
	}
	if b.Retries < 0 {
		b.Retries = 0
	}
}

// DeviceResult is the outcome for a single target.
type DeviceResult struct {
	Device   Device
	OK       bool
	Error    string
	Attempts int
}

// BatchResults holds the outcome table plus rollup counters.
type BatchResults struct {
	Results []DeviceResult
	OK      int
	Failed  int
	Total   int
	// Summary renders a compact table (name / host / ok / error).
	Summary []string
}

// RunBatch pushes the image to every selected device with bounded concurrency
// and one automatic retry pass for failures. ctx cancellation aborts in-flight
// and pending work promptly.
func RunBatch(ctx context.Context, opts BatchOptions) BatchResults {
	opts.norm()

	// Worker pool — bounded, not naive full parallel.
	sem := make(chan struct{}, opts.Concurrency)
	out := make(chan DeviceResult, len(opts.Devices))

	var wg sync.WaitGroup
	for _, d := range opts.Devices {
		wg.Add(1)
		go func(d Device) {
			defer wg.Done()
			select {
			case sem <- struct{}{}:
				defer func() { <-sem }()
			case <-ctx.Done():
				out <- DeviceResult{Device: d, Error: "aborted: " + ctx.Err().Error()}
				return
			}
			res := pushWithRetry(ctx, d, opts)
			out <- res
		}(d)
	}
	wg.Wait()
	close(out)

	res := BatchResults{}
	for r := range out {
		res.Results = append(res.Results, r)
		if r.OK {
			res.OK++
		} else {
			res.Failed++
		}
	}
	res.Total = len(res.Results)
	sort.Slice(res.Results, func(i, j int) bool { return res.Results[i].Device.Key() < res.Results[j].Device.Key() })
	for _, r := range res.Results {
		row := fmt.Sprintf("%-20s %-16s %s", r.Device.Key(), r.Device.Host, statusText(r))
		res.Summary = append(res.Summary, row)
	}
	return res
}

func pushWithRetry(ctx context.Context, d Device, opts BatchOptions) DeviceResult {
	attempts := 0
	var lastErr error
	for attempt := 0; attempt <= opts.Retries; attempt++ {
		if ctx.Err() != nil {
			return DeviceResult{Device: d, Attempts: attempts, Error: "aborted: " + ctx.Err().Error()}
		}
		attempts++
		if err := opts.Push(ctx, d); err != nil {
			lastErr = err
			continue
		}
		return DeviceResult{Device: d, OK: true, Attempts: attempts}
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("push failed")
	}
	return DeviceResult{Device: d, Attempts: attempts, Error: lastErr.Error()}
}

func statusText(r DeviceResult) string {
	if r.OK {
		return fmt.Sprintf("ok (%d attempt)", r.Attempts)
	}
	return fmt.Sprintf("FAILED — %s", r.Error)
}
