package boards

// ExtractArchive is exported so the libraries package can reuse it.
// It strips the top-level directory (library archives).
func ExtractArchive(archivePath, destDir string) error {
	return extractArchive(archivePath, destDir)
}

// ExtractArchiveKeepRoot preserves the archive's internal directory
// structure (tool/platform archives where the top-level dir is meaningful).
func ExtractArchiveKeepRoot(archivePath, destDir string) error {
	return extractArchiveKeepRoot(archivePath, destDir)
}
