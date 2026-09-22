package ota

// stream.go — the transport-independent ArduinoOTA data phase.
//
// Both transports (LAN dial-back TCP and the relay hub's paired websocket
// pipe) speak the same wire protocol to the device, so the chunk/ACK state
// machine lives here exactly once:
//
//	"<size> <md5>\n" header (optional — LAN carries size+md5 in the UDP
//	                          invite, the relay path embeds it in-stream)
//	→ 1 KiB chunks, strict stop-and-wait: one bare decimal ACK per chunk
//	→ unframed replies, possibly coalesced ("1024OK") or split
//	→ bare "OK" only after Update.end() verifies the full-image MD5
//
// LAN Push() and remote relay.PushDevice() are thin wrappers over PushStream.

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"strconv"
	"strings"
	"time"
)

// StreamOptions configures one PushStream transfer.
type StreamOptions struct {
	// SendHeader prepends the ASCII "<size> <md5>\n" header in-stream.
	// Required for transports without a control channel (the relay pipe,
	// where push_start carried size+md5 out-of-band but the device still
	// parses the header from the byte stream). LAN leaves this false —
	// the UDP invite already delivered size+md5.
	SendHeader bool

	// ChunkBytes is the stop-and-wait frame size: the agent sends this many
	// firmware bytes per ACK round-trip. The protocol still requires one
	// bare decimal ACK per frame (coalesced ACKs are NOT consumed ahead),
	// so raising ChunkBytes purely amortizes per-round-trip latency — it is
	// the chunk ÷ RTT lever on tunnel paths. ≤0 → legacy 1024-byte frames.
	// Large frames are bounded by the transport MTU and whatever the device
	// accepts in one frame, so large frames belong to opt-in tuning, not
	// defaults: pass ChunkBytes (e.g. 8192) on long-RTT paths where fewer
	// round-trips per image directly shorten the push.
	ChunkBytes int

	// ChunkWait is the per-chunk ACK timeout. LAN links are sub-second;
	// stop-and-wait over an internet tunnel is ~0.6s per KiB, so the
	// remote path widens this.
	ChunkWait time.Duration

	// FinalWait bounds the wait for the bare "OK" that the device emits
	// after Update.end() (flash write + full-image MD5 verify).
	FinalWait time.Duration

	// WriteWait bounds each write of one chunk to the transport.
	WriteWait time.Duration

	OnProgress func(sent, total int64)
	OnMessage  func(string)
}

func (o *StreamOptions) log(msg string) {
	if o.OnMessage != nil {
		o.OnMessage(msg)
	}
}

func (o *StreamOptions) progress(sent, total int64) {
	if o.OnProgress != nil {
		o.OnProgress(sent, total)
	}
}

// DefaultStreamOptions fills zero-valued fields with LAN-tuned defaults.
func DefaultStreamOptions(opts *StreamOptions) *StreamOptions {
	if opts == nil {
		opts = &StreamOptions{}
	}
	if opts.ChunkWait <= 0 {
		opts.ChunkWait = 60 * time.Second
	}
	if opts.FinalWait <= 0 {
		opts.FinalWait = 120 * time.Second
	}
	if opts.WriteWait <= 0 {
		opts.WriteWait = 60 * time.Second
	}
	return opts
}

// PushStream streams size bytes from img to the device over conn using the
// shared ArduinoOTA data-phase protocol. img must be seekable (it is hashed,
// then rewound); conn must be a real net.Conn (per-op deadlines required).
func PushStream(ctx context.Context, conn net.Conn, img io.ReadSeeker, size int64, so *StreamOptions) error {
	so = DefaultStreamOptions(so)

	h := md5.New()
	if _, err := io.Copy(h, img); err != nil {
		return fmt.Errorf("hash image: %w", err)
	}
	md5sum := hex.EncodeToString(h.Sum(nil))
	if _, err := img.Seek(0, io.SeekStart); err != nil {
		return fmt.Errorf("rewind image: %w", err)
	}

	// Abort a blocked ACK read promptly on cancellation: closing conn
	// unblocks the in-flight Read. (Double Close with the caller's deferred
	// Close is harmless.)
	done := make(chan struct{})
	defer close(done)
	go func() {
		select {
		case <-ctx.Done():
			conn.Close()
		case <-done:
		}
	}()

	if so.SendHeader {
		if err := writeWithDeadline(conn, []byte(fmt.Sprintf("%d %s\n", size, md5sum)), so.WriteWait); err != nil {
			return fmt.Errorf("send image header: %w", err)
		}
	}

	reader := &replyReader{conn: conn}
	// Frame size: ChunkBytes amortizes the per-ACK round trip on long-RTT
	// paths (relay tunnels); ≤0 keeps the legacy 1024-byte ArduinoOTA frame.
	chunk := chunkSize
	if so.ChunkBytes > 0 {
		chunk = so.ChunkBytes
	}
	buf := make([]byte, chunk)
	var sent int64
	finalOK := false

	for sent < size && !finalOK {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		n, rerr := img.Read(buf)
		if n > 0 {
			if err := writeWithDeadline(conn, buf[:n], so.WriteWait); err != nil {
				return fmt.Errorf("write to device: %w", err)
			}
			raw, aerr := reader.next(so.ChunkWait)
			if aerr != nil {
				return fmt.Errorf("device stopped ACKing at %d/%d bytes: %w", sent, size, aerr)
			}
			_, okSeen, errText := classifyReply(raw)
			if errText != "" {
				return fmt.Errorf("device rejected data at offset %d: %q", sent, errText)
			}
			if okSeen {
				// Device finished the whole update early (size mismatch on
				// its side). espota.py treats any OK as immediate success.
				finalOK = true
			}
			sent += int64(n)
			so.progress(sent, size)
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return fmt.Errorf("read image: %w", rerr)
		}
	}

	// Final verdict: "OK" on success, error text otherwise. The device sends
	// it only after Update.end() (flash write + MD5 verify of the whole
	// image) completes, which takes seconds on large images — espota.py
	// allows up to 300s, so wait generously and drain duplicate ACKs.
	if !finalOK {
		hard := time.Now().Add(so.FinalWait)
		for {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			remain := time.Until(hard)
			if remain <= 0 {
				return errors.New("no final device response (timeout waiting for OK)")
			}
			raw, err := reader.next(remain)
			if err != nil {
				return fmt.Errorf("no final device response: %w", err)
			}
			_, okSeen, errText := classifyReply(raw)
			if okSeen {
				finalOK = true
				break
			}
			if errText != "" {
				return fmt.Errorf("device reported failure: %s", errText)
			}
			// bare numeric → duplicate/late ACK; keep waiting for OK
		}
	}

	so.progress(size, size)
	so.log(fmt.Sprintf("✓ OTA transfer complete — %d bytes written, device rebooting", size))
	return nil
}

// writeWithDeadline writes p to conn with a fresh per-op deadline, so a
// wedged transport can never hang the push loop.
func writeWithDeadline(conn net.Conn, p []byte, wait time.Duration) error {
	if err := conn.SetWriteDeadline(time.Now().Add(wait)); err != nil {
		return err
	}
	_, err := conn.Write(p)
	return err
}

// replyReader assembles unframed device replies. ArduinoOTA sends bare
// decimal ACKs and a bare "OK" — no terminators — so replies arrive without
// framing and may be coalesced ("1024OK") or split across TCP segments. The
// reader accumulates bytes until the sender goes quiet briefly, which is the
// practical end-of-reply signal for an unframed protocol (the same
// tolerance espota.py gets by parsing whatever recv() returns).
type replyReader struct {
	conn net.Conn
	tmp  [512]byte
}

func (rr *replyReader) next(timeout time.Duration) (string, error) {
	hard := time.Now().Add(timeout)
	var acc []byte
	for {
		remain := time.Until(hard)
		if remain <= 0 {
			if len(acc) > 0 {
				return string(acc), nil
			}
			return "", errors.New("timeout waiting for device reply")
		}
		d := remain
		if len(acc) > 0 {
			d = 30 * time.Millisecond // quiet period after first byte
		}
		if err := rr.conn.SetReadDeadline(time.Now().Add(d)); err != nil {
			if len(acc) > 0 {
				return string(acc), nil
			}
			return "", err
		}
		n, err := rr.conn.Read(rr.tmp[:])
		if n > 0 {
			acc = append(acc, rr.tmp[:n]...)
		}
		if err != nil {
			if ne, ok := err.(net.Error); ok && ne.Timeout() {
				if len(acc) > 0 {
					return string(acc), nil // quiet → reply complete
				}
				return "", errors.New("timeout waiting for device reply")
			}
			// EOF / reset: return any bytes read before the close so the
			// caller can classify a coalesced final "OK" that raced the
			// device's client.stop().
			if len(acc) > 0 {
				return string(acc), nil
			}
			return "", err
		}
	}
}

// classifyReply interprets one raw device reply: a bare decimal ACK, the
// bare final "OK", both coalesced ("273OK"), or device error text. The
// numeric count is advisory — the device may ACK partial writes — so it is
// reported but never validated (espota.py ignores it too).
func classifyReply(raw string) (acked int64, okSeen bool, errText string) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return 0, false, ""
	}
	okSeen = strings.Contains(s, "OK")
	if d := leadingDigits(s); d != "" {
		if n, err := strconv.ParseInt(d, 10, 64); err == nil {
			acked = n
		}
	}
	if okSeen || acked > 0 {
		return acked, okSeen, ""
	}
	return 0, false, s
}

// leadingDigits returns the maximal digit prefix after leading whitespace.
func leadingDigits(s string) string {
	s = strings.TrimLeft(s, " \t\r\n")
	end := 0
	for end < len(s) && s[end] >= '0' && s[end] <= '9' {
		end++
	}
	return s[:end]
}
