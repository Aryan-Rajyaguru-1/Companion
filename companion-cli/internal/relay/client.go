package relay

import (
	"bufio"
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

// Device-side protocol constants — deliberately identical in spirit to the
// ArduinoOTA LAN protocol (internal/ota): the device ACKs each chunk with a
// BARE decimal count (no framing) and finishes with a bare "OK". Reusing
// the same semantics means the ESP32 firmware shares one Update state
// machine for both LAN and remote pushes.
const (
	dataChunkSize = 1024
	ackTimeout    = 60 * time.Second
	finalOKWindow = 120 * time.Second
)

// PushDevice pushes a firmware image to a remote device over the paired
// data pipe (hub-relayed). data must be a real net.Conn (deadlines are
// required for the unframed ACK protocol); img must be seekable (it is
// hashed, then rewound).
func PushDevice(ctx context.Context, data net.Conn, img io.ReadSeeker, size int64) error {
	h := md5.New()
	if _, err := io.Copy(h, img); err != nil {
		return fmt.Errorf("hash image: %w", err)
	}
	md5sum := hex.EncodeToString(h.Sum(nil))
	if _, err := img.Seek(0, io.SeekStart); err != nil {
		return fmt.Errorf("rewind image: %w", err)
	}

	// Header: "<size> <md5>\n" — the device begins ACKing chunks after it.
	if _, err := fmt.Fprintf(data, "%d %s\n", size, md5sum); err != nil {
		return fmt.Errorf("send image header: %w", err)
	}

	rd := bufio.NewReaderSize(data, 4096)
	rr := &relayReplyReader{rd: rd, conn: data}
	buf := make([]byte, dataChunkSize)
	var sent int64
	finalOK := false

	for sent < size && !finalOK {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		n, rerr := img.Read(buf)
		if n > 0 {
			_ = data.SetWriteDeadline(time.Now().Add(60 * time.Second))
			if _, werr := data.Write(buf[:n]); werr != nil {
				return fmt.Errorf("write to device: %w", werr)
			}
			raw, aerr := rr.next(ackTimeout)
			if aerr != nil {
				return fmt.Errorf("device stopped ACKing at %d/%d bytes: %w", sent, size, aerr)
			}
			_, okSeen, errText := classifyReply(raw)
			if errText != "" {
				return fmt.Errorf("device rejected data at offset %d: %q", sent, errText)
			}
			if okSeen {
				finalOK = true // device finished the whole update early
			}
			sent += int64(n)
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return fmt.Errorf("read image: %w", rerr)
		}
	}

	// Final verdict: device verifies MD5 over the whole image in flash
	// (Update.end()), which takes seconds on large images — wait generously
	// and drain duplicate/late ACKs while looking for the bare "OK".
	if !finalOK {
		hard := time.Now().Add(finalOKWindow)
		for {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			remain := time.Until(hard)
			if remain <= 0 {
				return errors.New("no final device response (timeout waiting for OK)")
			}
			raw, err := rr.next(remain)
			if err != nil {
				return fmt.Errorf("no final device response: %w", err)
			}
			_, okSeen, errText := classifyReply(raw)
			if okSeen {
				break
			}
			if errText != "" {
				return fmt.Errorf("device reported failure: %s", errText)
			}
			// bare numeric → duplicate/late ACK; keep waiting
		}
	}
	return nil
}

// relayReplyReader assembles unframed device replies over the relayed data
// pipe — identical strategy to internal/ota's replyReader: accumulate bytes
// until the sender goes quiet for a beat.
type relayReplyReader struct {
	rd   *bufio.Reader
	conn net.Conn
}

func (rr *relayReplyReader) next(timeout time.Duration) (string, error) {
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
		var tmp [512]byte
		n, err := rr.rd.Read(tmp[:])
		if n > 0 {
			acc = append(acc, tmp[:n]...)
		}
		if err != nil {
			if ne, ok := err.(net.Error); ok && ne.Timeout() {
				if len(acc) > 0 {
					return string(acc), nil
				}
				return "", errors.New("timeout waiting for device reply")
			}
			if len(acc) > 0 {
				return string(acc), nil // EOF carrying a coalesced final OK
			}
			return "", err
		}
	}
}

// classifyReply mirrors internal/ota.classifyReply: bare decimal ACK, bare
// "OK", both coalesced ("273OK"), or device error text.
func classifyReply(raw string) (acked int64, okSeen bool, errText string) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return 0, false, ""
	}
	okSeen = strings.Contains(s, "OK")
	end := 0
	for end < len(s) && s[end] >= '0' && s[end] <= '9' {
		end++
	}
	if end > 0 {
		if n, err := strconv.ParseInt(s[:end], 10, 64); err == nil {
			acked = n
		}
	}
	if okSeen || acked > 0 {
		return acked, okSeen, ""
	}
	return 0, false, s
}

