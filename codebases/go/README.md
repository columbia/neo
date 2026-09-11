<artifact identifier="readme-md" type="application/vnd.ant.code" language="markdown" title="README.md">
# Microservices Test Go

A Go project demonstrating inter-service communication patterns across HTTP/REST, gRPC, Kafka, RabbitMQ, and Redis.

## Prerequisites

- Go 1.23+
- Make

Optional (tests skip if unavailable):
- Kafka (localhost:9092)
- RabbitMQ (localhost:5672)
- Redis (localhost:6379)

## Quick Start

```bash
# Install dependencies
make deps

# Build
make build

# Run
make run
```

## Project Structure

```
├── main.go           # Test runner
├── makefile          # Build automation
└── tests/            # Service implementations
    ├── test_grpc.go
    ├── test_http_rest.go
    ├── test_kafka.go
    ├── test_rabbitmq.go
    └── test_redis.go
```


## Communication Patterns

- **HTTP/REST**: Sequential and concurrent API calls, retry logic
- **gRPC**: Unary, streaming (server/client/bidirectional)
- **Kafka**: Event publishing, consumer groups, message batching
- **RabbitMQ**: Topic exchanges, pub/sub, RPC pattern
- **Redis**: Pub/Sub, caching, distributed locking

## CodeQL Database

```bash
# Using go build (compiles all packages)
codeql database create ../databases/go \
  --language=go \
  --source-root=. \
  --command="go build ./..." \
  --overwrite

# Or using Makefile
codeql database create ../databases/go \
  --language=go \
  --source-root=. \
  --command="make build" \
  --overwrite
```


## Module Info

- Module: `microservices-test-go`
- Import: `microservices-test-go/tests`
</artifact>
