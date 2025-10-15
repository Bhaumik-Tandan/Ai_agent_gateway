#!/bin/bash

# Aegis Gateway Demo Script
# This script demonstrates all four test cases

set -e

BASE_URL="http://localhost:8080"
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Aegis Gateway Demo${NC}"
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

# Test Case 1: Blocked high-value payment
echo -e "${BOLD}Test 1: Blocked high-value payment (exceeds limit)${NC}"
echo -e "Agent: finance-agent"
echo -e "Tool: payments.create"
echo -e "Amount: \$50,000 (limit is \$5,000)"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: finance-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/payments/create" \
  -d '{"amount":50000,"currency":"USD","vendor_id":"V99"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "403" ]; then
    echo -e "${GREEN}✓ PASS: Request blocked with 403${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 403, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Test Case 2: Allowed payment within limits
echo -e "${BOLD}Test 2: Allowed payment (within limit)${NC}"
echo -e "Agent: finance-agent"
echo -e "Tool: payments.create"
echo -e "Amount: \$2,000 (within \$5,000 limit)"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: finance-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/payments/create" \
  -d '{"amount":2000,"currency":"USD","vendor_id":"V42","memo":"Office supplies"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "200" ]; then
    echo -e "${GREEN}✓ PASS: Request allowed with 200${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 200, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Test Case 3: Allowed HR file read inside /hr-docs/
echo -e "${BOLD}Test 3: Allowed HR file read (within allowed folder)${NC}"
echo -e "Agent: hr-agent"
echo -e "Tool: files.read"
echo -e "Path: /hr-docs/employee-handbook.txt"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: hr-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/files/read" \
  -d '{"path":"/hr-docs/employee-handbook.txt"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "200" ]; then
    echo -e "${GREEN}✓ PASS: Request allowed with 200${NC}"
    echo -e "Response (truncated): $(echo "$body" | jq -r '.path')"
else
    echo -e "${RED}✗ FAIL: Expected 200, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Test Case 4: Blocked HR file read outside /hr-docs/
echo -e "${BOLD}Test 4: Blocked HR file read (outside allowed folder)${NC}"
echo -e "Agent: hr-agent"
echo -e "Tool: files.read"
echo -e "Path: /legal/contract.docx"
echo ""
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "X-Agent-ID: hr-agent" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/tools/files/read" \
  -d '{"path":"/legal/contract.docx"}')

http_status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

if [ "$http_status" = "403" ]; then
    echo -e "${GREEN}✓ PASS: Request blocked with 403${NC}"
    echo -e "Response: $body"
else
    echo -e "${RED}✗ FAIL: Expected 403, got $http_status${NC}"
    echo -e "Response: $body"
fi
echo ""
echo "---"
echo ""

# Summary
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   Demo Complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo -e "View logs at: ./logs/aegis.log"
echo -e "View traces at: http://localhost:16686 (Jaeger UI)"
echo ""

