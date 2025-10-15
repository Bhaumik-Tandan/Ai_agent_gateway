# Aegis Gateway

Production-grade reverse proxy gateway that enforces least-privilege policies on agent → tool calls with audit-grade telemetry.

## Features

### Core
- **Policy-as-Code**: YAML-based policies with hot-reload
- **Zero-Trust Enforcement**: Every call evaluated before forwarding
- **Full Observability**: OpenTelemetry traces + structured JSON audit logs
- **Mock Tools**: Payments and Files adapters for testing
- **Production Ready**: Clean architecture, graceful shutdown, health checks

### Stretch Goals (Implemented)
- **Call-Chain Awareness**: Parent-agent tracking with ancestry-based deny rules
- **Admin UI**: React dashboard for agents, policies, and last 50 decisions
- **Approval Gates**: Soft-deny mechanism requiring manual approval for risky actions

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the gateway
python main.py

# Or with Docker
docker-compose up -d

# Run basic demo
chmod +x scripts/demo.sh
./scripts/demo.sh

# Run stretch goals demo
chmod +x scripts/demo-stretch-goals.sh
./scripts/demo-stretch-goals.sh
```

The gateway will start on `http://localhost:8080`  
Admin UI will be at `http://localhost:3000`

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
- `X-Parent-Agent` (optional): Parent agent in call chain (for ancestry checks)
- `X-Approval-ID` (optional): Approval ID for executing pre-approved requests

**Request Body:** JSON (tool-specific)

**Responses:**
- `200 OK` - Request allowed and forwarded
- `202 Accepted` - Approval required (includes `approval_id`)
- `403 Forbidden` - Policy violation
- `400 Bad Request` - Invalid request
- `404 Not Found` - Approval ID not found
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
        require_approval: false  # Set to true for approval gates
    
  # Advanced: Call-chain restrictions
  - id: worker-agent
    allow_only_parents: [orchestrator-agent]  # Only callable by these parents
    allow:
      - tool: files
        actions: [read]
  
  - id: secure-agent
    deny_if_parent: [untrusted-agent]  # Deny if called by these parents
    allow:
      - tool: files
        actions: [read]
```

**Agent-Level Options:**
- `allow_only_parents`: List of parent agents that can call this agent
- `deny_if_parent`: List of parent agents that cannot call this agent

**Permission-Level Options:**
- `require_approval`: Boolean, if true triggers approval gate (soft-deny)
- `conditions`: Condition checks for parameters

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

### Stretch Goals Demo
```bash
./scripts/demo-stretch-goals.sh
```

Tests:
1. **Call-Chain Awareness**
   - ✓ Worker agent with valid parent (allowed)
   - ✗ Worker agent without parent (denied)
   - ✗ Secure agent with denied parent (blocked)
2. **Approval Gates**
   - Refund request requiring approval (202 response)
   - Approval and execution flow
3. **Admin API**
   - Get agents, policies, decisions

**Note:** Policies hot-reload automatically when changed - just edit a `.yaml` file and save to see changes take effect immediately.

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
- `parent.agent` (when provided)

**Admin UI:**
- React dashboard at http://localhost:3000
- Real-time view of last 50 decisions
- Agent and policy browser
- Approval queue management
- Auto-refresh every 5 seconds

To start Admin UI:
```bash
cd admin-ui
npm install
npm start
```

## Environment Variables

**Gateway:**
- `PORT` - Server port (default: 8080)
- `POLICY_DIR` - Policy directory (default: ./policies)
- `OTEL_ENDPOINT` - OpenTelemetry endpoint (optional)

**Admin UI:**
- `REACT_APP_API_BASE` - Gateway API URL (default: http://localhost:8080)

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

**Decision History**: In-memory deque (last 50) for lightweight tracking. For production, use persistent store.

**Approval Gates**: In-memory pending approvals. For production HA, use Redis or database.

**Parent-Agent Tracking**: Enables call-chain authorization for agent-to-agent scenarios

## Security

- All requests require `X-Agent-ID` header
- Policy violations return sanitized error messages
- Request params hashed before logging
- Input validation on all tool calls
- No secrets in logs or traces
- Parent-agent validation prevents unauthorized call chains
- Approval gates add human-in-the-loop for high-risk actions
- CORS enabled on admin API (configure for production)

## API Endpoints

### Core
- `POST /tools/:tool/:action` - Execute tool action (with policy enforcement)
- `GET /health` - Health check

### Admin API
- `GET /api/admin/agents` - List all configured agents
- `GET /api/admin/policies` - List loaded policy files
- `GET /api/admin/decisions?limit=50` - Get recent decisions
- `GET /api/admin/approvals/pending` - List pending approvals

### Approvals
- `POST /api/approve/:approval_id` - Approve and execute a pending request

## Future Extensions

- Policy priority/merging for overlapping rules
- Rate limiting per agent
- Policy simulation/dry-run mode
- Persistent decision history
- Multi-level approval workflows
- Audit log export to external systems

## License

MIT
