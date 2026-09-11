# Makefile for microservices-test-go

.PHONY: all build clean test deps fmt vet lint help

# Variables
BINARY_NAME=microservices-test
MAIN_PACKAGE=./
GO=go
GOFLAGS=-v
LDFLAGS=-ldflags "-w -s"

# Default target
all: deps fmt vet build

# Install dependencies
deps:
	@echo "Installing dependencies..."
	$(GO) mod download
	$(GO) mod tidy

# Format code
fmt:
	@echo "Formatting code..."
	$(GO) fmt ./...

# Vet code
vet:
	@echo "Vetting code..."
	$(GO) vet ./...

# Build the binary
build: deps
	@echo "Building binary..."
	$(GO) build $(GOFLAGS) $(LDFLAGS) -o bin/$(BINARY_NAME) $(MAIN_PACKAGE)
	@echo "Build complete: bin/$(BINARY_NAME)"

# Run test-runner
run: build
	@echo "Running $(BINARY_NAME)..."
	./bin/$(BINARY_NAME)

# Clean build artifacts
clean:
	@echo "Cleaning..."
	rm -rf bin/
	$(GO) clean

# Run tests
test:
	@echo "Running tests..."
	$(GO) test -v ./tests/...

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	$(GO) test -v -coverprofile=coverage.out ./tests/...
	$(GO) tool cover -html=coverage.out -o coverage.html

# Check for compilation errors without building
check:
	@echo "Checking for compilation errors..."
	$(GO) build -o /dev/null $(MAIN_PACKAGE)

# Install linter (golangci-lint)
install-lint:
	@echo "Installing golangci-lint..."
	@which golangci-lint > /dev/null || curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $$(go env GOPATH)/bin

# Run linter
lint: install-lint
	@echo "Running linter..."
	golangci-lint run ./...