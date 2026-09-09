# companion-cli Makefile

BINARY := companion
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
LDFLAGS := -s -w -X github.com/companion-ide/companion-cli/cmd.CLIVersion=$(VERSION)

.PHONY: build build-all test test-verbose lint clean ci

## Build the companion binary for the current platform
build:
	go build -buildvcs=false -ldflags '$(LDFLAGS)' -o $(BINARY) .

## Build static release binaries for all supported platforms into dist/
build-all:
	mkdir -p dist
	GOOS=linux   GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags '$(LDFLAGS)' -o dist/companion-linux-amd64 . 
	GOOS=linux   GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags '$(LDFLAGS)' -o dist/companion-linux-arm64 .
	GOOS=darwin  GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags '$(LDFLAGS)' -o dist/companion-darwin-amd64 .
	GOOS=darwin  GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags '$(LDFLAGS)' -o dist/companion-darwin-arm64 .
	GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=false -ldflags '$(LDFLAGS)' -o dist/companion-windows-amd64.exe .

## Run all Go tests
test:
	go test ./... -count=1

## Run tests with verbose output
test-verbose:
	go test ./... -v -count=1

## Run tests with coverage report
test-coverage:
	go test ./... -coverprofile=coverage.out -count=1
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

## Run specific package tests
test-fqbn:
	go test ./internal/fqbn/... -v

test-boards:
	go test ./internal/boards/... -v

test-compiler:
	go test ./internal/compiler/... -v

test-config:
	go test ./internal/config/... -v

## Lint (requires golangci-lint)
lint:
	golangci-lint run ./...

## Clean build artifacts
clean:
	rm -f $(BINARY)
	rm -rf dist/
	rm -f coverage.out coverage.html

## Install to PATH
install: build
	cp $(BINARY) $(shell go env GOPATH)/bin/$(BINARY)
	@echo "Installed to $(shell go env GOPATH)/bin/$(BINARY)"

## Create a publishable source/artifact bundle EXCLUDING the Arduino for refs
## tree (AGPL/GPL sources, legal hygiene). Run from the workspace root.
publish:
	@echo "=== Building release CLI binaries ==="
	$(MAKE) -C companion-cli build-all
	@echo "=== Building IDE ==="
	cd companion-ide && npx vite build
	@echo "=== Creating publish bundle (refs excluded) ==="
	rm -rf dist-publish
	mkdir -p dist-publish/companion/bins
	cp companion-cli/dist/* dist-publish/companion/bins/
	cp -r companion-ide/dist dist-publish/companion/ide-dist
	cp README.md ROADMAP.md LICENSE* dist-publish/companion/ 2>/dev/null || true
	@echo
	@echo "Publish bundle ready: dist-publish/companion"
	@echo "  * Purging 'Arduino for refs/' + analysis .md files from git history"
	@echo "    before any tag:  git rm -r --cached 'Arduino for refs/' && git commit"
	@echo "  * Only from-scratch code ships. License stays MIT."

## Mirror the IDE's compiled CLI into it (dev loop shortcut)
sync-ide:
	cp companion-cli/companion companion-ide/bin/companion
	@echo "IDE binary synced."
