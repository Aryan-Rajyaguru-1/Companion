package selfupdate

import (
	"encoding/hex"
	"fmt"
	"path"
	"strings"
)

// ChecksumFor extracts the SHA-256 digest for name from a SHA256SUMS file.
//
// The format produced by the release workflow is:
//
//	<64 hex digits>  <filename>
//
// The binary marker ("*") used by sha256sum -b is accepted too. Filenames are
// matched exactly, with a basename fallback so mirrors that add a directory
// prefix still work.
func ChecksumFor(data []byte, name string) (string, error) {
	name = strings.TrimSpace(name)
	if name == "" {
		return "", fmt.Errorf("checksum lookup has an empty asset name")
	}
	var found string
	for lineNo, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		digest := strings.ToLower(fields[0])
		if len(digest) != 64 || !isHex(digest) {
			return "", fmt.Errorf("malformed checksum on line %d", lineNo+1)
		}
		filename := strings.TrimPrefix(strings.TrimSpace(strings.TrimPrefix(line, fields[0])), "*")
		if filename != name && path.Base(filename) != name {
			continue
		}
		if found != "" && !strings.EqualFold(found, digest) {
			return "", fmt.Errorf("conflicting checksums for %s", name)
		}
		found = digest
	}
	if found == "" {
		return "", fmt.Errorf("%s does not list %s", ChecksumsAssetName, name)
	}
	return found, nil
}

func isHex(s string) bool {
	if len(s)%2 != 0 {
		return false
	}
	_, err := hex.DecodeString(s)
	return err == nil
}
