# Stretch Goals

## 1. Call-Chain Awareness

Parent agent tracking via `X-Parent-Agent` header with ancestry rules.

```yaml
agents:
  - id: worker-agent
    allow_only_parents: [orchestrator-agent]
    allow:
      - tool: files
        actions: [read, write]
  
  - id: secure-agent
    deny_if_parent: [untrusted-agent]
    allow:
      - tool: files
        actions: [read]
```

Test:
```bash
curl -H "X-Agent-ID: worker-agent" \
     -H "X-Parent-Agent: orchestrator-agent" \
     -X POST http://localhost:8080/tools/files/read \
     -d '{"path":"/tmp/data.txt"}'
```

## 2. Admin UI

React dashboard at http://localhost:3000

Views:
- Recent decisions (last 50)
- Configured agents
- Policy files
- Pending approvals

```bash
cd admin-ui
npm install
npm start
```

## 3. Approval Gates

Actions requiring manual approval return 202 with `approval_id`.

```yaml
agents:
  - id: refund-agent
    allow:
      - tool: payments
        actions: [refund]
        require_approval: true
```

Flow:
```bash
# Request refund
curl -H "X-Agent-ID: refund-agent" \
     -X POST http://localhost:8080/tools/payments/refund \
     -d '{"payment_id":"PAY123"}'
# Returns: {"approval_id":"abc-123"}

# Approve and execute
curl -H "X-Agent-ID: admin" \
     -X POST http://localhost:8080/api/approve/abc-123
```

## Demo

```bash
./scripts/demo-stretch-goals.sh
```
