# Aegis Gateway

Production-grade reverse proxy gateway that enforces least-privilege policies on agent → tool calls with audit-grade telemetry.

## Features

- **Policy-as-Code**: YAML-based policies with hot-reload
- **Zero-Trust Enforcement**: Every call evaluated before forwarding
- **Full Observability**: OpenTelemetry traces + structured JSON audit logs
- **Mock Tools**: Payments and Files adapters for testing
- **Production Ready**: Clean architecture, graceful shutdown, health checks

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the gateway
python main.py

# Or with Docker
docker-compose up -d

# Run demo
chmod +x scripts/demo.sh
./scripts/demo.sh
```

The gateway will start on `http://localhost:8080`

## Architecture

```
┌─────────────┐
│   Agents    │
└─────┬───────┘
      │ POST /tools/:tool/:action
      │ Headers: X-Agent-ID, X-Parent-Agent
      ▼
┌─────────────────────────────────┐
│      Aegis Gateway              │
│  ┌──────────────────────────┐   │
│  │  Policy Engine           │   │
│  │  - YAML parsing          │   │
│  │  - Hot reload            │   │
│  │  - Condition checks      │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │  Telemetry               │   │
│  │  - OTel spans            │   │
│  │  - JSON audit logs       │   │
│  │  - Param hashing         │   │
│  └──────────────────────────┘   │
└───────────┬─────────────────────┘
            │
            ▼
    ┌───────────────┐
    │  Tool Adapters│
    │  - Payments   │
    │  - Files      │
    └───────────────┘
```

## API Reference

### Gateway Endpoint

```bash
POST /tools/:tool/:action
```

**Headers:**
- `X-Agent-ID` (required): Agent identity
- `X-Parent-Agent` (optional): Parent agent in call chain

**Request Body:** JSON (tool-specific)

**Responses:**
- `200 OK` - Request allowed and forwarded
- `403 Forbidden` - Policy violation
- `400 Bad Request` - Invalid request
- `502 Bad Gateway` - Tool error

### Mock Tools

**Payments:**
```bash
# Create payment
POST /tools/payments/create
{"amount": 1000, "currency": "USD", "vendor_id": "V123"}

# Refund payment
POST /tools/payments/refund
{"payment_id": "xxx", "reason": "Customer request"}
```

**Files:**
```bash
# Read file
POST /tools/files/read
{"path": "/hr-docs/handbook.txt"}

# Write file
POST /tools/files/write
{"path": "/tmp/data.txt", "content": "..."}
```

## Policy Configuration

Policies are defined in YAML files in the `./policies` directory:

```yaml
version: 1
agents:
  - id: finance-agent
    allow:
      - tool: payments
        actions: [create, refund]
        conditions:
          max_amount: 5000
          currencies: [USD, EUR]
```

**Supported Conditions:**
- `max_amount`: Maximum payment amount
- `currencies`: Allowed currency list
- `folder_prefix`: Required path prefix for files

Policies hot-reload automatically when files change.

## Demo Scripts

### Main Demo (4 test cases)
```bash
./scripts/demo.sh
```

Tests:
1. ✗ High-value payment blocked ($50k > $5k limit)
2. ✓ Normal payment allowed ($2k < $5k limit)
3. ✓ HR file read in allowed folder
4. ✗ HR file read outside allowed folder

### Hot-Reload Demo
```bash
./scripts/test-hotreload.sh
```

Modifies policy live and shows changes take effect without restart.

## Observability

**Logs:**
- Console: JSON structured logs to stdout
- File: `./logs/aegis.log`

**Traces:**
- OpenTelemetry spans exported to Jaeger
- View at: http://localhost:16686

**Attributes tracked:**
- `agent.id`, `tool.name`, `tool.action`
- `decision.allow`, `policy.version`
- `params.hash` (SHA-256, no PII)
- `latency.ms`, `trace.id`

## Environment Variables

- `PORT` - Server port (default: 8080)
- `POLICY_DIR` - Policy directory (default: ./policies)
- `OTEL_ENDPOINT` - OpenTelemetry endpoint (optional)

## Development

```bash
# Run locally
python main.py

# With custom config
POLICY_DIR=./custom-policies PORT=9000 python main.py
```

## Design Decisions

**Stateless Gateway**: No session state, scales horizontally

**Hot-Reload**: watchdog monitors policy directory, debounced reloads prevent thrashing

**In-Process Adapters**: Mock tools run in-process for demo. In production, these would be HTTP/gRPC clients to real services.

**Param Hashing**: SHA-256 hash logged instead of raw params to avoid PII leakage

**Fail-Safe**: Invalid policy files log errors but don't crash if other valid policies exist

## Security

- All requests require `X-Agent-ID` header
- Policy violations return sanitized error messages
- Request params hashed before logging
- Input validation on all tool calls
- No secrets in logs or traces

## Future Extensions

- Policy priority/merging for overlapping rules
- Call-chain tracking via `X-Parent-Agent`
- Rate limiting per agent
- Approval gates for high-risk actions
- Admin UI for policy visualization
- Policy simulation/dry-run mode

## License

MIT
