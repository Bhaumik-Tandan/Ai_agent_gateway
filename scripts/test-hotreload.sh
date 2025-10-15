#!/bin/bash

# Hot Reload Demo Script
# Demonstrates policy hot-reload without server restart

set -e

BASE_URL="http://localhost:8080"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Policy Hot-Reload Demo${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

# Test initial policy - should be blocked
echo -e "${YELLOW}Step 1: Testing with initial policy (should be blocked)${NC}"
echo -e "Attempting to create payment for \$7,000 (above \$5,000 limit)"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: finance-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/payments/create" \
  -d '{"amount":7000,"currency":"USD","vendor_id":"V123"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "403" ]; then
    echo -e "${GREEN}✓ Blocked as expected${NC}"
else
    echo -e "Got status: $http_status"
fi
echo ""

# Backup original policy
cp policies/main.yaml policies/main.yaml.backup

# Modify policy to increase limit
echo -e "${YELLOW}Step 2: Updating policy to increase limit to \$10,000${NC}"
cat > policies/main.yaml <<EOF
version: 1
agents:
  - id: finance-agent
    allow:
      - tool: payments
        actions: [create, refund]
        conditions:
          max_amount: 10000
          currencies: [USD, EUR]
  
  - id: hr-agent
    allow:
      - tool: files
        actions: [read]
        conditions:
          folder_prefix: "/hr-docs/"
EOF

echo "Policy file updated. Waiting 2 seconds for hot-reload..."
sleep 2
echo ""

# Test with new policy - should be allowed
echo -e "${YELLOW}Step 3: Testing with updated policy (should be allowed)${NC}"
echo -e "Attempting same \$7,000 payment (now within \$10,000 limit)"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: finance-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/payments/create" \
  -d '{"amount":7000,"currency":"USD","vendor_id":"V123"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "200" ]; then
    echo -e "${GREEN}✓ Allowed as expected (hot-reload worked!)${NC}"
    echo -e "Response: $body"
else
    echo -e "Got status: $http_status"
    echo -e "Response: $body"
fi
echo ""

# Restore original policy
echo -e "${YELLOW}Step 4: Restoring original policy${NC}"
mv policies/main.yaml.backup policies/main.yaml
sleep 2
echo -e "${GREEN}✓ Policy restored${NC}"
echo ""

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Hot-Reload Demo Complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "The policy was modified and reloaded WITHOUT restarting the server!"
echo ""

