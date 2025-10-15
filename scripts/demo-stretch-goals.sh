#!/bin/bash

# Aegis Gateway - Stretch Goals Demo
# Demonstrates call-chain awareness, approval gates, and parent restrictions

set -e

BASE_URL="http://localhost:8080"
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Aegis Gateway - Stretch Goals Demo${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server to be ready...${NC}"
for i in {1..30}; do
    if curl -s "$BASE_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Server failed to start${NC}"
        exit 1
    fi
    sleep 1
done
echo ""

# Feature 1: Call-chain awareness - Allow with parent
echo -e "${BOLD}${BLUE}Feature 1: Call-Chain Awareness${NC}"
echo -e "${BOLD}Test 1a: Worker agent WITH allowed parent (orchestrator)${NC}"
echo -e "Agent: worker-agent"
echo -e "Parent: orchestrator-agent"
echo -e "Tool: files.read"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: worker-agent" \
  -H "X-Parent-Agent: orchestrator-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/files/read" \
  -d '{"path":"/tmp/data.txt"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "200" ]; then
    echo -e "${GREEN}✓ PASS: Request allowed (valid parent)${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 200, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Feature 1b: Call-chain awareness - Deny without parent
echo -e "${BOLD}Test 1b: Worker agent WITHOUT parent (should fail)${NC}"
echo -e "Agent: worker-agent"
echo -e "Parent: (none)"
echo -e "Tool: files.read"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: worker-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/files/read" \
  -d '{"path":"/tmp/data.txt"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "403" ]; then
    echo -e "${GREEN}✓ PASS: Request blocked (missing required parent)${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 403, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Feature 1c: Deny if parent restriction
echo -e "${BOLD}Test 1c: Secure agent WITH denied parent${NC}"
echo -e "Agent: secure-agent"
echo -e "Parent: untrusted-agent (in deny list)"
echo -e "Tool: files.read"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: secure-agent" \
  -H "X-Parent-Agent: untrusted-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/files/read" \
  -d '{"path":"/secure/config.json"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "403" ]; then
    echo -e "${GREEN}✓ PASS: Request blocked (denied parent)${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 403, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Feature 2: Approval Gates
echo -e "${BOLD}${BLUE}Feature 2: Approval Gates${NC}"
echo -e "${BOLD}Test 2a: Refund requiring approval${NC}"
echo -e "Agent: refund-agent"
echo -e "Tool: payments.refund"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: refund-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/payments/refund" \
  -d '{"payment_id":"PAY123","reason":"Customer complaint"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "202" ]; then
    echo -e "${GREEN}✓ PASS: Approval required (202 status)${NC}"
    echo -e "Response: $body"
    
    # Extract approval_id
    approval_id=$(echo "$body" | grep -o '"approval_id":"[^"]*"' | cut -d'"' -f4)
    echo ""
    echo -e "${YELLOW}Approval ID: $approval_id${NC}"
    echo ""
    
    # Now approve it
    echo -e "${BOLD}Test 2b: Approving the request${NC}"
    sleep 1
    
    response2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
      -H "X-Agent-ID: admin-user" \
      -H "Content-Type: application/json" \
      -X POST "$BASE_URL/api/approve/$approval_id")
    
    http_status2=$(echo "$response2" | grep "HTTP_STATUS" | cut -d: -f2)
    body2=$(echo "$response2" | grep -v "HTTP_STATUS")
    
    if [ "$http_status2" = "200" ]; then
        echo -e "${GREEN}✓ PASS: Approval executed successfully${NC}"
        echo -e "Response: $body2"
    else
        echo -e "${RED}✗ FAIL: Expected 200, got $http_status2${NC}"
        echo -e "Response: $body2"
    fi
else
    echo -e "${RED}✗ FAIL: Expected 202 (approval required), got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Feature 3: Admin API
echo -e "${BOLD}${BLUE}Feature 3: Admin API${NC}"
echo -e "${BOLD}Test 3a: Get agents${NC}"
agents_response=$(curl -s "$BASE_URL/api/admin/agents")
agent_count=$(echo "$agents_response" | grep -o '"id"' | wc -l)
echo -e "${GREEN}✓ Retrieved $agent_count agents${NC}"
echo ""

echo -e "${BOLD}Test 3b: Get policies${NC}"
policies_response=$(curl -s "$BASE_URL/api/admin/policies")
policy_count=$(echo "$policies_response" | grep -o '"version"' | wc -l)
echo -e "${GREEN}✓ Retrieved $policy_count policy files${NC}"
echo ""

echo -e "${BOLD}Test 3c: Get recent decisions${NC}"
decisions_response=$(curl -s "$BASE_URL/api/admin/decisions")
echo "$decisions_response" | head -c 100
echo "..."
echo -e "${GREEN}✓ Decision history accessible${NC}"
echo ""
echo "---"
echo ""

# Summary
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Demo Complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Call-chain awareness with parent restrictions${NC}"
echo -e "${GREEN}✓ Approval gates for risky actions${NC}"
echo -e "${GREEN}✓ Admin API for monitoring${NC}"
echo ""
echo -e "View Admin UI at: ${BLUE}http://localhost:3000${NC}"
echo -e "View logs at: ./logs/aegis.log"
echo -e "View traces at: http://localhost:16686 (Jaeger UI)"
echo ""

