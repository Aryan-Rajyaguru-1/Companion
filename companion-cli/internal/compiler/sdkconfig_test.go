package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestGenerateSDKConfigSkipsNotSet verifies the sdkconfig generator faithfully
// reproduces IDF semantics for Kconfig-disabled options: "# CONFIG_X is not
// set" must NOT become "#define X 0" — a defined-as-0 macro still satisfies
// #ifdef and selects the *enabled* code branch. That exact failure broke lwip's
// netdb.h: CONFIG_LWIP_USE_ESP_GETADDRINFO=0 forced the esp_getaddrinfo path
// even though that implementation is never compiled in.
func TestGenerateSDKConfigSkipsNotSet(t *testing.T) {
	// Fake sdk root with a Kconfig-format sdkconfig file.
	sdkRoot := t.TempDir()
	if err := os.WriteFile(filepath.Join(sdkRoot, "sdkconfig"), []byte(`# Test sdkconfig
CONFIG_FREERTOS_NUMBER_OF_CORES=1
CONFIG_LWIP_ENABLE=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_COMPILER_OPTIMIZATION_DEFAULT=n
# CONFIG_LWIP_USE_ESP_GETADDRINFO is not set
# CONFIG_DISABLED_NO_COMMENT_END`), 0o644); err != nil {
		t.Fatal(err)
	}

	buildDir := t.TempDir()
	c := &Compiler{}
	if err := c.generateSDKConfig(sdkRoot, buildDir, "esp32"); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(buildDir, "sdkconfig.h"))
	if err != nil {
		t.Fatal(err)
	}
	hdr := string(data)

	// Enabled options must be defined with real values.
	for _, want := range []string{
		"#define CONFIG_FREERTOS_NUMBER_OF_CORES 1",
		"#define CONFIG_LWIP_ENABLE 1",
		"#define CONFIG_LOG_DEFAULT_LEVEL 3",
	} {
		if !strings.Contains(hdr, want) {
			t.Errorf("missing definition %q in:\n%s", want, hdr)
		}
	}

	// Disabled options must NEVER be "#define X 0" (still satisfies #ifdef).
	if strings.Contains(hdr, "#define CONFIG_LWIP_USE_ESP_GETADDRINFO 0") {
		t.Error("disabled option emitted as #define with 0 — breaks #ifdef semantics")
	}
	// Correct output is the IDF-style unset comment.
	if !strings.Contains(hdr, "/* #undef CONFIG_LWIP_USE_ESP_GETADDRINFO */") {
		t.Error("disabled option did not become the IDF-style #undef comment")
	}
	// `n` values must not land in the header.
	if strings.Contains(hdr, "CONFIG_COMPILER_OPTIMIZATION_DEFAULT n") ||
		strings.Contains(hdr, "#define CONFIG_COMPILER_OPTIMIZATION_DEFAULT n") {
		t.Error("Kconfig 'n' value leaked into the header")
	}
}