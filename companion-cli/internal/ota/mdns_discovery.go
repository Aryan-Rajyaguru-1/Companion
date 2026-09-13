// Package ota: mdns_discovery.go — dependency-free mDNS for _arduino._tcp.
//
// Hand-built DNS wire format per RFC 1035 §4.1 and RFC 6762 (mDNS). No
// third-party libraries. Two roles:
//
//   - Query side (queryMDNS): send one mDNS PTR query for _arduino._tcp.local
//     and collect PTR/SRV/A answers for the listen window (device discovery).
//   - Responder side (Serve): answer _arduino._tcp.local queries advertising
//     THIS machine's OTA TCP port (bridge-firmware OTA server mode).
package ota

import (
	"context"
	"encoding/binary"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"
)

// ── Wire constants (RFC 1035 §4.1 + RFC 6762) ────────────────────

const (
	mdnsMulticast       = "224.0.0.251:5353"
	mdnsQueryPort       = 5353
	mdnsService         = "_arduino._tcp.local"
	mdnsTypePTR         = 12
	mdnsTypeSRV         = 33
	mdnsTypeTXT         = 16
	mdnsTypeA           = 1
	mdnsClassIN         = 0x0001
	mdnsClassCacheFlush = 0x8001
)

// ── ServiceRecord — one _arduino._tcp advertisement ──────────────

// ServiceRecord is one OTA advertisement seen on the network.
type ServiceRecord struct {
	Name string // instance name (e.g. "companion bridge OTA")
	Host string // SRV target hostname (e.g. "companion-000000.local")
	IP   string // resolved A record (device IP)
	Port int    // OTA TCP port
}

// ── DNS wire-format writer ───────────────────────────────────────

type dnsWriter struct {
	buf []byte
}

func (w *dnsWriter) u16(v uint16) { w.buf = append(w.buf, byte(v>>8), byte(v)) }

func (w *dnsWriter) u32(v uint32) {
	w.buf = append(w.buf, byte(v>>24), byte(v>>16), byte(v>>8), byte(v))
}

// name writes a DNS name as length-prefixed labels.
func (w *dnsWriter) name(n string) {
	for _, label := range strings.Split(n, ".") {
		if label == "" {
			continue
		}
		w.buf = append(w.buf, byte(len(label)))
		w.buf = append(w.buf, label...)
	}
	w.buf = append(w.buf, 0)
}

func (w *dnsWriter) question(n string, qtype uint16) {
	w.name(n)
	w.u16(qtype)
	w.u16(mdnsClassIN)
}

// ptr writes a PTR answer (rdata = target domain name).
func (w *dnsWriter) ptr(name, target string, ttl uint32) {
	w.name(name)
	w.u16(mdnsTypePTR)
	w.u16(mdnsClassCacheFlush)
	w.u32(ttl)
	rdlen := len(w.buf)
	w.u16(0) // rdlen — patched below
	w.name(target)
	binary.BigEndian.PutUint16(w.buf[rdlen:], uint16(len(w.buf)-rdlen-2))
}

// srv writes a SRV answer (priority/weight 0).
func (w *dnsWriter) srv(name, target string, port uint16, ttl uint32) {
	w.name(name)
	w.u16(mdnsTypeSRV)
	w.u16(mdnsClassCacheFlush)
	w.u32(ttl)
	rdlen := len(w.buf)
	w.u16(0) // rdlen — patched below (priority/weight/port + target)
	w.u16(0)
	w.u16(0)
	w.u16(port)
	w.name(target)
	binary.BigEndian.PutUint16(w.buf[rdlen:], uint16(len(w.buf)-rdlen-2))
}

// txt writes a TXT record from key=value pairs.
func (w *dnsWriter) txt(name string, kvs map[string]string, ttl uint32) {
	w.name(name)
	w.u16(mdnsTypeTXT)
	w.u16(mdnsClassCacheFlush)
	w.u32(ttl)
	var rdata []byte
	for k, v := range kvs {
		s := k
		if v != "" {
			s = k + "=" + v
		}
		if len(s) > 255 {
			s = s[:255]
		}
		rdata = append(rdata, byte(len(s)))
		rdata = append(rdata, s...)
	}
	if len(rdata) == 0 {
		rdata = []byte{0}
	}
	w.buf = append(w.buf, byte(len(rdata)>>8), byte(len(rdata)))
	w.buf = append(w.buf, rdata...)
}

// a writes an address record (rdata = 4-byte IPv4).
func (w *dnsWriter) a(name string, ip net.IP, ttl uint32) {
	w.name(name)
	w.u16(mdnsTypeA)
	w.u16(mdnsClassCacheFlush)
	w.u32(ttl)
	ip4 := ip.To4()
	if ip4 == nil {
		ip4 = net.IPv4zero.To4()
	}
	w.buf = append(w.buf, ip4...)
}

// ── DNS wire-format reader ───────────────────────────────────────

type dnsReader struct {
	buf []byte
	off int
}

func newDNSReader(b []byte) *dnsReader { return &dnsReader{buf: b} }

func (r *dnsReader) u16() (uint16, bool) {
	if r.off+2 > len(r.buf) {
		return 0, false
	}
	v := binary.BigEndian.Uint16(r.buf[r.off:])
	r.off += 2
	return v, true
}

func (r *dnsReader) u32() (uint32, bool) {
	if r.off+4 > len(r.buf) {
		return 0, false
	}
	v := binary.BigEndian.Uint32(r.buf[r.off:])
	r.off += 4
	return v, true
}

// name reads a (possibly compressed) DNS name.
func (r *dnsReader) name() (string, bool) {
	var sb strings.Builder
	off := r.off
	jumped := false
	jumps := 0
	for {
		if off >= len(r.buf) {
			return "", false
		}
		l := int(r.buf[off])
		if l == 0 {
			if !jumped {
				r.off = off + 1
			}
			break
		}
		if l&0xC0 == 0xC0 { // compression pointer
			if off+1 >= len(r.buf) || jumps > 8 {
				return "", false
			}
			ptr := int(binary.BigEndian.Uint16(r.buf[off:]) & 0x3FFF)
			if !jumped {
				r.off = off + 2
				jumped = true
			}
			off = ptr
			jumps++
			continue
		}
		if l&0xC0 != 0 || off+1+l > len(r.buf) {
			return "", false
		}
		sb.Write(r.buf[off+1 : off+1+l])
		sb.WriteByte('.')
		off += 1 + l
		if sb.Len() > 512 {
			return "", false
		}
	}
	return strings.TrimSuffix(sb.String(), "."), true
}

// skipName advances past a name without materializing it.
func (r *dnsReader) skipName() bool {
	_, ok := r.name()
	return ok
}

// ── Response parsing ─────────────────────────────────────────────

// parseMDNSResponses extracts _arduino._tcp PTR/SRV/A records into the
// records map (keyed by instance name).
func parseMDNSResponses(pkt []byte, records map[string]*ServiceRecord) {
	r := newDNSReader(pkt)
	if _, ok := r.u16(); !ok {
		return
	}
	if _, ok := r.u16(); !ok {
		return
	}
	qd, ok1 := r.u16()
	an, ok2 := r.u16()
	ns, ok3 := r.u16()
	ar, ok4 := r.u16()
	if !ok1 || !ok2 || !ok3 || !ok4 {
		return
	}
	for i := 0; i < int(qd); i++ {
		if !r.skipName() {
			return
		}
		if _, ok := r.u16(); !ok {
			return
		}
		if _, ok := r.u16(); !ok {
			return
		}
	}
	total := int(an) + int(ns) + int(ar)
	for i := 0; i < total; i++ {
		nm, ok := r.name()
		if !ok {
			break
		}
		rtype, ok1 := r.u16()
		class, ok2 := r.u16()
		_, ok3 := r.u32() // TTL
		rdlen, ok4 := r.u16()
		if !ok1 || !ok2 || !ok3 || !ok4 {
			break
		}
		rdend := r.off + int(rdlen)
		if rdend > len(r.buf) {
			break
		}
		switch rtype {
		case mdnsTypePTR:
			if class&0x7FFF == mdnsClassIN && nm == mdnsService {
				if target, ok := r.name(); ok {
					inst := instanceFromService(target)
					if inst != "" && records[inst] == nil {
						records[inst] = &ServiceRecord{Name: inst}
					}
				}
			}
		case mdnsTypeSRV:
			if rec := records[instanceFromService(nm)]; rec != nil && r.off+6 <= rdend {
				r.off += 4 // priority + weight
				if port, ok := r.u16(); ok {
					rec.Port = int(port)
				}
				if target, ok := r.name(); ok {
					rec.Host = target
				}
			}
		case mdnsTypeA:
			if rdend-r.off >= 4 {
				ip := net.IP(r.buf[r.off : r.off+4]).String()
				host := strings.TrimSuffix(nm, ".local")
				matched := false
				for _, rec := range records {
					if rec.IP == "" && (instanceFromService(nm) == rec.Name ||
						rec.Host == nm || rec.Host == host ||
						rec.Host == nm+".local") {
						rec.IP = ip
						matched = true
					}
				}
				if !matched {
					// Orphan A record: no instance named yet in this batch.
					// Park it in the "" bucket; the sweep after the loop
					// hands it to the first IP-less record.
					if records[""] == nil {
						records[""] = &ServiceRecord{Name: ""}
					}
					if records[""].IP == "" {
						records[""].IP = ip
						records[""].Host = nm
					}
				}
			}
		}
		if r.off < rdend { // safety: never desync on unknown rdata
			r.off = rdend
		}
	}
	// Residual A records carried in packets that named no instance yet
	// (rare: answers without their own PTR in the same window) land in
	// the bucket and are handed to the first IP-less record.
	if bucket := records[""]; bucket != nil {
		for key, rec := range records {
			if key != "" && rec.IP == "" && bucket.IP != "" {
				rec.IP = bucket.IP
			}
		}
		delete(records, "")
	}
}

// ── queryMDNS — one-shot discovery (query side) ──────────────────

// queryMDNS broadcasts one mDNS PTR question for _arduino._tcp.local on
// every multicast-capable interface and collects answers for the listen
// window. Best-effort: returns whatever resolved.
//
// A laptop often has several interfaces (ethernet, WiFi to the bridge's
// own hotspot, VPN/container bridges). The OS routes multicast out a
// single default route, so a query bound without an interface never
// reaches devices on the others — e.g. an ESP32 bridge whose AP the
// laptop itself is connected to. One socket per interface fixes that.
func queryMDNS(ctx context.Context, timeout time.Duration) []ServiceRecord {
	if timeout <= 0 {
		timeout = 3 * time.Second
	}

	ifaces, err := net.Interfaces()
	if err != nil {
		return nil
	}

	var conns []*net.UDPConn   // per-interface multicast listeners
	var writers []*net.UDPConn // ephemeral sockets bound per interface
	for i := range ifaces {
		ifc := ifaces[i]
		if ifc.Flags&net.FlagUp == 0 || ifc.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := ifc.Addrs()
		if err != nil {
			continue
		}
		for _, a := range addrs {
			ipnet, ok := a.(*net.IPNet)
			if !ok {
				continue
			}
			ip4 := ipnet.IP.To4()
			if ip4 == nil || !ip4.IsPrivate() {
				continue
			}
			pc, err := net.ListenMulticastUDP("udp4", &ifc, mdnsGroup())
			if err != nil {
				continue // driver may refuse multicast here — skip
			}
			// Ephemeral query socket bound to this interface's address:
			// multicast egresses the right link, and the answers come
			// straight back here without sharing 224.0.0.251:5353.
			wc, err := net.ListenUDP("udp4", &net.UDPAddr{IP: ip4, Port: 0})
			if err != nil {
				pc.Close()
				continue
			}
			conns = append(conns, pc)
			writers = append(writers, wc)
			break // one socket pair per interface
		}
	}
	if len(conns) == 0 {
		return nil
	}
	defer func() {
		for _, pc := range conns {
			pc.Close()
		}
		for _, wc := range writers {
			wc.Close()
		}
	}()

	// One question, one send per interface, and the ephemeral socket
	// doubles as that interface's dedicated answer collector.
	var w dnsWriter
	w.u16(0) // transaction ID (0 = mDNS convention)
	w.u16(0) // flags: standard query
	w.u16(1) // QDCOUNT
	w.u16(0)
	w.u16(0)
	w.u16(0)
	w.question(mdnsService, mdnsTypePTR)

	group := &net.UDPAddr{IP: net.IPv4(224, 0, 0, 251), Port: mdnsQueryPort}
	for _, wc := range writers {
		_, _ = wc.WriteToUDP(w.buf, group)
	}

	// Collect on every socket until the overall deadline. Each socket's
	// read deadline is the shared deadline, so a silent interface costs
	// nothing extra — the wait ends when every socket has timed out.
	deadline := time.Now().Add(timeout)
	records := make(map[string]*ServiceRecord)
	var mu sync.Mutex
	var wg sync.WaitGroup
	for _, pc := range append(append([]*net.UDPConn{}, conns...), writers...) {
		wg.Add(1)
		go func(pc *net.UDPConn) {
			defer wg.Done()
			buf := make([]byte, 9000)
			for {
				pc.SetReadDeadline(deadline)
				n, _, err := pc.ReadFromUDP(buf)
				if err != nil {
					return // deadline exceeded
				}
				mu.Lock()
				parseMDNSResponses(buf[:n], records)
				mu.Unlock()
				if ctx.Err() != nil {
					return
				}
			}
		}(pc)
	}
	wg.Wait()

	out := make([]ServiceRecord, 0, len(records))
	for _, rec := range records {
		if rec.IP != "" && rec.Port > 0 { // only fully-resolved devices
			out = append(out, *rec)
		}
	}
	return out
}

// ── Responder — advertise this host's OTA server ─────────────────

// Serve answers mDNS queries for _arduino._tcp.local until ctx is cancelled,
// advertising the given OTA TCP port on this machine's local IP.
func Serve(ctx context.Context, port int) error {
	pc, err := net.ListenMulticastUDP("udp4", nil, mdnsGroup())
	if err != nil {
		return fmt.Errorf("mDNS responder: %w", err)
	}
	defer pc.Close()

	ip := localIP()
	host, _ := os.Hostname()
	if host == "" {
		host = "companion-host"
	}
	inst := strings.ReplaceAll(host, ".", "-") + " OTA"
	svcInst := inst + "." + mdnsService
	hostFQDN := strings.ReplaceAll(host, ".", "-") + ".local"

	var mu sync.Mutex
	buf := make([]byte, 9000)
	for {
		pc.SetReadDeadline(time.Now().Add(500 * time.Millisecond))
		n, from, err := pc.ReadFromUDP(buf)
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if err != nil {
			continue // deadline tick — re-check ctx
		}
		if !isArduinoQuery(buf[:n]) {
			continue
		}
		mu.Lock()
		var w dnsWriter
		w.u16(0)
		w.u16(0x8400) // QR=1, AA=1 — authoritative response
		w.u16(0)
		w.u16(3) // ANCOUNT
		w.u16(0)
		w.u16(0)
		w.ptr(mdnsService, svcInst, 120)
		w.srv(svcInst, hostFQDN, uint16(port), 120)
		w.a(hostFQDN, ip, 120)
		// Send both: multicast so every listener (including true mDNS
		// stacks) caches the answer, and unicast back to the requester
		// because our querier listens on its own ephemeral socket rather
		// than sharing 224.0.0.251:5353 — a multicast-only answer never
		// reaches it there.
		mcast := mdnsGroup()
		_, _ = pc.WriteToUDP(w.buf, mcast)
		if from != nil && (from.Port != mdnsQueryPort || !from.IP.Equal(mcast.IP)) {
			_, _ = pc.WriteToUDP(w.buf, from)
		}
		mu.Unlock()
	}
}

// isArduinoQuery reports whether the packet asks for _arduino._tcp PTR.
func isArduinoQuery(pkt []byte) bool {
	r := newDNSReader(pkt)
	if _, ok := r.u16(); !ok {
		return false
	}
	flags, ok := r.u16()
	if !ok || flags&0x8000 != 0 { // must be a query, not a response
		return false
	}
	qd, ok := r.u16()
	if !ok || qd < 1 {
		return false
	}
	nm, ok := r.name()
	return ok && nm == mdnsService
}

// mdnsGroup returns the mDNS multicast group address.
func mdnsGroup() *net.UDPAddr {
	return &net.UDPAddr{IP: net.IPv4(224, 0, 0, 251), Port: mdnsQueryPort}
}

// localIP returns the primary outbound IPv4 address (best-effort).
func localIP() net.IP {
	conn, err := net.Dial("udp4", "8.8.8.8:53")
	if err == nil {
		if addr, ok := conn.LocalAddr().(*net.UDPAddr); ok {
			conn.Close()
			return addr.IP
		}
		conn.Close()
	}
	addrs, err := net.InterfaceAddrs()
	if err == nil {
		for _, a := range addrs {
			if ipn, ok := a.(*net.IPNet); ok && ipn.IP.To4() != nil && !ipn.IP.IsLoopback() {
				return ipn.IP
			}
		}
	}
	return net.IPv4(0, 0, 0, 0)
}

// instanceFromService reduces "bridge._arduino._tcp.local" → "bridge".
func instanceFromService(nm string) string {
	nm = strings.TrimSuffix(nm, ".")
	if i := strings.Index(nm, "._arduino"); i >= 0 {
		return nm[:i]
	}
	if i := strings.Index(nm, "._tcp"); i >= 0 {
		return nm[:i]
	}
	return nm
}
