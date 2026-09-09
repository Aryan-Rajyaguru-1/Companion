// Package config manages the Companion CLI configuration file.
// Stored at ~/.companion-cli/config.yaml
// Inspired by arduino-cli's config system but written from scratch.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

const (
	ConfigFileName = "config.yaml"
	DirName        = ".companion-cli"
)

// Config is the top-level configuration structure.
// Maps to ~/.companion-cli/config.yaml
//
// P1 YAML Config: All settings are portable and shareable.
// P2 Daemon/Cache: New sections for performance features.
type Config struct {
	BoardManager BoardManagerConfig `yaml:"board_manager"`
	Directories  DirectoriesConfig  `yaml:"directories"`
	Compiler     CompilerConfig     `yaml:"compiler"`
	Upload       UploadConfig       `yaml:"upload"`
	Bridge       BridgeConfig       `yaml:"bridge"`
	Library      LibraryConfig      `yaml:"library"`
	// P2: Daemon and build cache configuration
	Daemon DaemonConfig `yaml:"daemon"`
	Cache  CacheConfig  `yaml:"cache"`
}

// DaemonConfig controls the long-lived CLI daemon (P2 Daemon Mode).
type DaemonConfig struct {
	// Enabled controls whether the IDE spawns a persistent daemon process.
	Enabled bool `yaml:"enabled"`
	// Port to bind to; 0 = OS-assigned (printed to stdout for IDE discovery).
	Port int `yaml:"port"`
	// AutoRestart restarts the daemon if it exits unexpectedly.
	AutoRestart bool `yaml:"auto_restart"`
}

// CacheConfig controls the content-addressed build cache (P2 Build Cache).
type CacheConfig struct {
	// Enabled turns object file caching on/off.
	Enabled bool `yaml:"enabled"`
	// MaxSizeMB is the soft upper bound; LRU eviction runs when exceeded.
	MaxSizeMB int `yaml:"max_size_mb"`
	// MaxAgeDays removes cache entries older than this.
	MaxAgeDays int `yaml:"max_age_days"`
}

type BoardManagerConfig struct {
	// Additional board index URLs — same as arduino-cli additional_urls
	AdditionalURLs []string `yaml:"additional_urls"`
}

type DirectoriesConfig struct {
	// Where compiled output, downloaded cores, and toolchains live
	Data      string `yaml:"data"`
	Downloads string `yaml:"downloads"`
	// User sketchbook directory
	User string `yaml:"user"`
}

type CompilerConfig struct {
	Warnings string `yaml:"warnings"` // none | default | more | all
	Verbose  bool   `yaml:"verbose"`
}

type UploadConfig struct {
	AutoVerify bool `yaml:"auto_verify"`
	Verbose    bool `yaml:"verbose"`
}

type BridgeConfig struct {
	// Default WiFi bridge host and port
	Host string `yaml:"host"`
	Port int    `yaml:"port"`
	// Default upload baud rate
	Baud int `yaml:"baud"`
	// Default target MCU family: esp32 | esp8266 | avr | stm32 | generic
	MCU string `yaml:"mcu"`
}

type LibraryConfig struct {
	EnableUnsafeInstall bool `yaml:"enable_unsafe_install"`
}

// ── Defaults ─────────────────────────────────────────────────────

// defaultConfig returns defaults. In portable mode (COMPANION_PORTABLE=1 or
// the --portable flag, which the root command translates to the env var) all
// state lives next to the executable so Companion can run off a USB stick.
func defaultConfig() *Config {
	home := homeDir()
	dataDir := filepath.Join(home, DirName, "data")
	base, sketchDir := dataDir, filepath.Join(home, "CompanionSketches")
	if portableMode() {
		base = filepath.Join(exeDir(), "data")
		sketchDir = filepath.Join(exeDir(), "sketches")
	}
	return &Config{
		BoardManager: BoardManagerConfig{
			AdditionalURLs: []string{
				"https://dl.espressif.com/dl/package_esp32_index.json",
				"https://arduino.esp8266.com/stable/package_esp8266com_index.json",
				"https://raw.githubusercontent.com/stm32duino/BoardManagerFiles/main/package_stmicroelectronics_index.json",
			},
		},
		Directories: DirectoriesConfig{
			Data:      base,
			Downloads: filepath.Join(base, "staging"),
			User:      sketchDir,
		},
		Compiler: CompilerConfig{
			Warnings: "default",
			Verbose:  false,
		},
		Upload: UploadConfig{
			AutoVerify: true,
			Verbose:    false,
		},
		Bridge: BridgeConfig{
			Host: "192.168.4.1",
			Port: 3333,
			Baud: 115200,
			MCU:  "avr",
		},
		Library: LibraryConfig{
			EnableUnsafeInstall: false,
		},
		// P2 Daemon defaults
		Daemon: DaemonConfig{
			Enabled:     true,
			Port:        0,
			AutoRestart: true,
		},
		// P2 Cache defaults
		Cache: CacheConfig{
			Enabled:    true,
			MaxSizeMB:  512,
			MaxAgeDays: 30,
		},
	}
}

// ── Load / Save ───────────────────────────────────────────────────

// Load reads the config from disk, returning defaults if the file doesn't exist.
func Load(overridePath string) (*Config, string, error) {
	path := overridePath
	if path == "" {
		path = DefaultPath()
	}

	cfg := defaultConfig()

	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return cfg, path, nil // Return defaults silently
	}
	if err != nil {
		return nil, path, fmt.Errorf("reading config: %w", err)
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, path, fmt.Errorf("parsing config: %w", err)
	}

	return cfg, path, nil
}

// Save writes the config to disk.
func Save(cfg *Config, path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("creating config dir: %w", err)
	}

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshaling config: %w", err)
	}

	header := []byte("# Companion CLI configuration file\n# Edit manually or use: companion config set <key> <value>\n\n")
	return os.WriteFile(path, append(header, data...), 0o644)
}

// Init writes a default config to disk if it doesn't exist yet.
func Init(path string) (string, bool, error) {
	if path == "" {
		path = DefaultPath()
	}

	if _, err := os.Stat(path); err == nil {
		return path, false, nil // Already exists
	}

	cfg := defaultConfig()
	if err := Save(cfg, path); err != nil {
		return path, false, err
	}
	return path, true, nil
}

// DefaultPath returns the default config file path.
func DefaultPath() string {
	if portableMode() {
		return filepath.Join(exeDir(), ConfigFileName)
	}
	return filepath.Join(homeDir(), DirName, ConfigFileName)
}

// portableMode reports whether Companion runs in portable mode: all data
// directories live next to the executable (USB-stick workflow).
func portableMode() bool {
	v := strings.TrimSpace(os.Getenv("COMPANION_PORTABLE"))
	return v == "1" || strings.EqualFold(v, "true") || strings.EqualFold(v, "yes")
}

// exeDir returns the directory containing the running binary.
func exeDir() string {
	p, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(p)
}

// EnsureDirs creates all required directories from config.
func EnsureDirs(cfg *Config) error {
	dirs := []string{
		cfg.Directories.Data,
		cfg.Directories.Downloads,
		cfg.Directories.User,
		filepath.Join(cfg.Directories.Data, "packages"),
		filepath.Join(cfg.Directories.Data, "libraries"),
		filepath.Join(cfg.Directories.Data, "indexes"),
	}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return fmt.Errorf("creating dir %s: %w", d, err)
		}
	}
	return nil
}

// ── Key/Value get/set ─────────────────────────────────────────────

// GetValue returns a config value by dot-separated key.
func GetValue(cfg *Config, key string) (string, error) {
	switch key {
	case "board_manager.additional_urls":
		result := ""
		for i, u := range cfg.BoardManager.AdditionalURLs {
			if i > 0 {
				result += "\n"
			}
			result += u
		}
		return result, nil
	case "directories.data":
		return cfg.Directories.Data, nil
	case "directories.user":
		return cfg.Directories.User, nil
	case "compiler.warnings":
		return cfg.Compiler.Warnings, nil
	case "compiler.verbose":
		return fmt.Sprintf("%v", cfg.Compiler.Verbose), nil
	case "upload.auto_verify":
		return fmt.Sprintf("%v", cfg.Upload.AutoVerify), nil
	case "bridge.host":
		return cfg.Bridge.Host, nil
	case "bridge.port":
		return fmt.Sprintf("%d", cfg.Bridge.Port), nil
	case "bridge.baud":
		return fmt.Sprintf("%d", cfg.Bridge.Baud), nil
	case "bridge.mcu":
		return cfg.Bridge.MCU, nil
	// P2 Daemon
	case "daemon.enabled":
		return fmt.Sprintf("%v", cfg.Daemon.Enabled), nil
	case "daemon.port":
		return fmt.Sprintf("%d", cfg.Daemon.Port), nil
	// P2 Cache
	case "cache.enabled":
		return fmt.Sprintf("%v", cfg.Cache.Enabled), nil
	case "cache.max_size_mb":
		return fmt.Sprintf("%d", cfg.Cache.MaxSizeMB), nil
	case "cache.max_age_days":
		return fmt.Sprintf("%d", cfg.Cache.MaxAgeDays), nil
	case "library.enable_unsafe_install":
		return fmt.Sprintf("%v", cfg.Library.EnableUnsafeInstall), nil
	default:
		return "", fmt.Errorf("unknown config key: %s", key)
	}
}

// SetValue sets a config key by dot-separated string.
func SetValue(cfg *Config, key, value string) error {
	switch key {
	case "directories.data":
		cfg.Directories.Data = value
	case "directories.user":
		cfg.Directories.User = value
	case "compiler.warnings":
		if value != "none" && value != "default" && value != "more" && value != "all" {
			return fmt.Errorf("warnings must be: none | default | more | all")
		}
		cfg.Compiler.Warnings = value
	case "compiler.verbose":
		cfg.Compiler.Verbose = value == "true"
	case "upload.auto_verify":
		cfg.Upload.AutoVerify = value == "true"
	case "bridge.host":
		cfg.Bridge.Host = value
	case "bridge.port":
		n, err := strconv.Atoi(value)
		if err != nil || n < 1 || n > 65535 {
			return fmt.Errorf("bridge.port must be an integer between 1 and 65535")
		}
		cfg.Bridge.Port = n
	case "bridge.baud":
		n, err := strconv.Atoi(value)
		if err != nil || n <= 0 {
			return fmt.Errorf("bridge.baud must be a positive integer (e.g. 115200)")
		}
		cfg.Bridge.Baud = n
	case "bridge.mcu":
		valid := map[string]bool{"esp32": true, "esp8266": true, "avr": true, "stm32": true, "generic": true}
		if !valid[value] {
			return fmt.Errorf("mcu must be: esp32 | esp8266 | avr | stm32 | generic")
		}
		cfg.Bridge.MCU = value
	case "daemon.enabled":
		cfg.Daemon.Enabled = value == "true"
	case "daemon.port":
		n, err := strconv.Atoi(value)
		if err != nil || n < 1 || n > 65535 {
			return fmt.Errorf("daemon.port must be an integer between 1 and 65535")
		}
		cfg.Daemon.Port = n
	case "cache.enabled":
		cfg.Cache.Enabled = value == "true"
	case "cache.max_size_mb":
		n, err := strconv.Atoi(value)
		if err != nil || n < 0 {
			return fmt.Errorf("cache.max_size_mb must be a non-negative integer")
		}
		cfg.Cache.MaxSizeMB = n
	case "cache.max_age_days":
		n, err := strconv.Atoi(value)
		if err != nil || n < 0 {
			return fmt.Errorf("cache.max_age_days must be a non-negative integer")
		}
		cfg.Cache.MaxAgeDays = n
	default:
		return fmt.Errorf("unknown config key: %q\n\nAvailable keys:\n"+
			"  directories.data      directories.user\n"+
			"  compiler.warnings     compiler.verbose\n"+
			"  upload.auto_verify\n"+
			"  bridge.host           bridge.port\n"+
			"  bridge.baud           bridge.mcu\n"+
			"  daemon.enabled        daemon.port\n"+
			"  cache.enabled         cache.max_size_mb   cache.max_age_days\n"+
			"  library.enable_unsafe_install",
			key,
		)
	}
	return nil
}

// ── Helpers ───────────────────────────────────────────────────────

func homeDir() string {
	if h, err := os.UserHomeDir(); err == nil {
		return h
	}
	if runtime.GOOS == "windows" {
		return os.Getenv("USERPROFILE")
	}
	return os.Getenv("HOME")
}

// PackagesDir returns the root directory where board cores are installed.
func (c *Config) PackagesDir() string {
	return filepath.Join(c.Directories.Data, "packages")
}

// IndexesDir returns where board/library JSON indexes are cached.
func (c *Config) IndexesDir() string {
	return filepath.Join(c.Directories.Data, "indexes")
}

// LibrariesDir returns the user libraries directory.
func (c *Config) LibrariesDir() string {
	return filepath.Join(c.Directories.Data, "libraries")
}

// CacheDir returns the build object cache directory (P2 Build Cache).
func (c *Config) CacheDir() string {
	return filepath.Join(c.Directories.Data, "cache", "builds")
}
