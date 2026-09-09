package boards

import (
	"archive/tar"
	"archive/zip"
	"compress/bzip2"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// sanitizeRelPath validates an archive entry name and returns the safe
// destination path under destDir.
//
// Security: archives from third-party indexes are untrusted input. Entry
// names like "../../../etc/passwd" (Zip Slip) must never escape destDir.
func sanitizeRelPath(destDir, name string) (string, error) {
	// Reject absolute paths and Windows drive letters outright.
	if filepath.IsAbs(name) || strings.Contains(name, `:\`) || strings.HasPrefix(name, `\`) {
		return "", fmt.Errorf("archive entry %q: absolute paths are not allowed", name)
	}
	cleaned := filepath.Clean(filepath.FromSlash(name))
	if cleaned == "." || cleaned == ".." || strings.HasPrefix(cleaned, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("archive entry %q: path traversal is not allowed", name)
	}
	destPath := filepath.Join(destDir, cleaned)
	if !strings.HasPrefix(destPath, filepath.Clean(destDir)+string(filepath.Separator)) {
		return "", fmt.Errorf("archive entry %q: escapes destination directory", name)
	}
	return destPath, nil
}

// extractZip extracts a .zip archive to destDir.
// The top-level directory in the archive is stripped (library layout).
func extractZip(archivePath, destDir string) error {
	return extractZipOpts(archivePath, destDir, true)
}

func extractZipOpts(archivePath, destDir string, stripTop bool) error {
	r, err := zip.OpenReader(archivePath)
	if err != nil {
		return fmt.Errorf("opening zip: %w", err)
	}
	defer r.Close()

	// Find the top-level directory to strip
	topDir := ""
	if stripTop && len(r.File) > 0 {
		first := r.File[0].Name
		parts := strings.SplitN(first, "/", 2)
		if len(parts) > 0 && parts[0] != "" {
			topDir = parts[0] + "/"
		}
	}

	for _, f := range r.File {
		relPath := strings.TrimPrefix(f.Name, topDir)
		if relPath == "" {
			continue
		}

		destPath, err := sanitizeRelPath(destDir, relPath)
		if err != nil {
			return err
		}

		if f.FileInfo().IsDir() {
			os.MkdirAll(destPath, f.FileInfo().Mode())
			continue
		}

		if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
			return err
		}

		rc, err := f.Open()
		if err != nil {
			return err
		}

		out, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, f.FileInfo().Mode())
		if err != nil {
			rc.Close()
			return err
		}

		_, err = io.Copy(out, rc)
		out.Close()
		rc.Close()
		if err != nil {
			return err
		}
	}

	return nil
}

// extractTar extracts .tar.gz / .tar.bz2 / .tar.xz archives.
//
// Security: every entry goes through sanitizeRelPath() before being written.
// The previous version delegated to the system `tar` binary first; that path
// bypassed sanitization entirely, so it has been removed in favour of the
// fully validated Go implementation below (xz is handled by piping through
// the xz executable).
func extractTar(archivePath, destDir string) error {
	return extractTarOpts(archivePath, destDir, true)
}

func extractTarOpts(archivePath, destDir string, stripTop bool) error {
	f, err := os.Open(archivePath)
	if err != nil {
		return err
	}
	defer f.Close()

	var reader io.Reader = f

	switch {
	case strings.HasSuffix(archivePath, ".tar.gz"):
		gr, err := gzip.NewReader(f)
		if err != nil {
			return err
		}
		defer gr.Close()
		reader = gr

	case strings.HasSuffix(archivePath, ".tar.bz2"):
		reader = bzip2.NewReader(f)

	case strings.HasSuffix(archivePath, ".tar.xz"):
		xz, lookErr := exec.LookPath("xz")
		if lookErr != nil {
			return fmt.Errorf("xz decompression requires the xz utility — install xz-utils and retry")
		}
		cmd := exec.Command(xz, "-dc")
		cmd.Stdin = f
		pipe, err := cmd.StdoutPipe()
		if err != nil {
			return err
		}
		if err := cmd.Start(); err != nil {
			return err
		}
		defer func() {
			io.Copy(io.Discard, pipe) // drain so xz can exit cleanly
			cmd.Wait()
		}()
		reader = pipe
	}

	tr := tar.NewReader(reader)
	topDir := ""
	first := stripTop // only detect/stripping the top-level dir when asked

	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}

		if first {
			parts := strings.SplitN(hdr.Name, "/", 2)
			if len(parts) > 0 {
				topDir = parts[0] + "/"
			}
			first = false
		}

		relPath := strings.TrimPrefix(hdr.Name, topDir)
		if relPath == "" {
			continue
		}

		destPath, err := sanitizeRelPath(destDir, relPath)
		if err != nil {
			return err
		}

		switch hdr.Typeflag {
		case tar.TypeDir:
			os.MkdirAll(destPath, os.FileMode(hdr.Mode))

		case tar.TypeReg, tar.TypeRegA:
			os.MkdirAll(filepath.Dir(destPath), 0o755)
			out, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, os.FileMode(hdr.Mode))
			if err != nil {
				return err
			}
			_, err = io.Copy(out, tr)
			out.Close()
			if err != nil {
				return err
			}

		case tar.TypeLink:
			// Hardlink to a previously extracted entry (GCC toolchains use
			// these heavily: bin/avr-gcc ↔ bin/avr-gcc-<version>).
			linkSrc := strings.TrimPrefix(hdr.Linkname, topDir)
			linkPath, lerr := sanitizeRelPath(destDir, linkSrc)
			if lerr != nil {
				return lerr
			}
			os.MkdirAll(filepath.Dir(destPath), 0o755)
			os.Remove(destPath)
			if lerr := os.Link(linkPath, destPath); lerr != nil {
				// Fallback (e.g. filesystems without hardlink support):
				// duplicate the target's content.
				if cerr := copyTree(linkPath, destPath); cerr != nil {
					return fmt.Errorf("hardlink %q -> %q: %w", linkSrc, relPath, lerr)
				}
			}

		case tar.TypeSymlink:
			// Only allow symlinks whose target stays within destDir.
			target := hdr.Linkname
			resolved := target
			if !filepath.IsAbs(target) {
				resolved = filepath.Join(filepath.Dir(destPath), target)
			}
			if !strings.HasPrefix(filepath.Clean(resolved), filepath.Clean(destDir)+string(filepath.Separator)) {
				return fmt.Errorf("archive symlink %q -> %q: escapes destination directory", hdr.Name, hdr.Linkname)
			}
			os.MkdirAll(filepath.Dir(destPath), 0o755)
			os.Remove(destPath) // replace stale symlinks/files
			if err := os.Symlink(target, destPath); err != nil && !os.IsExist(err) {
				return err
			}
		}
	}

	return nil
}
