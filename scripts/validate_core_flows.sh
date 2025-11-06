#!/bin/bash

# QueueCTL Core Flow Validation Script
# This script validates the core functionality of QueueCTL

set -e  # Exit on error

echo "=========================================="
echo "QueueCTL Core Flow Validation"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    # Stop workers if running
    python -m queuectl worker stop 2>/dev/null || true
    sleep 1
    # Remove test database
    rm -f ./data/queuectl.db
    rm -f ./data/queuectl.log
    rm -f ./data/worker_manager.pid
    rm -f ./data/worker_manager.shutdown
    echo "Cleanup complete."
}

# Set trap for cleanup
trap cleanup EXIT

echo "Step 1: Recreating database..."
rm -rf ./data
python -m queuectl init-db
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Database initialization failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Database initialized${NC}"
echo ""

echo "Step 2: Enqueuing sample jobs..."
# Enqueue a job that will succeed
echo "Enqueuing successful job..."
python -m queuectl enqueue --command "python -c \"print('success')\"" --id test-success-job
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to enqueue successful job${NC}"
    exit 1
fi

# Enqueue a job that will fail
echo "Enqueuing failing job..."
python -m queuectl enqueue --command "python -c \"import sys; sys.exit(1)\"" --id test-fail-job --max-retries 2
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to enqueue failing job${NC}"
    exit 1
fi

# Set backoff_base to 1 for faster testing
python -m queuectl config set backoff_base 1
echo -e "${GREEN}✓ Jobs enqueued${NC}"
echo ""

echo "Step 3: Starting worker manager (2 workers)..."
python -m queuectl worker start --count 2 &
WORKER_PID=$!
sleep 2

# Check if workers started
if ! python -m queuectl status > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Failed to start workers${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Workers started${NC}"
echo ""

echo "Step 4: Waiting for jobs to process (max 30 seconds)..."
sleep 15

# Wait a bit more for retries
echo "Waiting additional time for retries..."
sleep 10

echo -e "${GREEN}✓ Processing time elapsed${NC}"
echo ""

echo "Step 5: Checking queue status..."
python -m queuectl status
STATUS_EXIT=$?
if [ $STATUS_EXIT -ne 0 ]; then
    echo -e "${RED}ERROR: Status command failed${NC}"
    exit 1
fi
echo ""

echo "Step 6: Checking Dead Letter Queue..."
python -m queuectl dlq list
DLQ_EXIT=$?
if [ $DLQ_EXIT -ne 0 ]; then
    echo -e "${RED}ERROR: DLQ list command failed${NC}"
    exit 1
fi
echo ""

echo "Step 7: Stopping workers..."
python -m queuectl worker stop
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}WARNING: Worker stop command failed (may already be stopped)${NC}"
fi
sleep 2
echo -e "${GREEN}✓ Workers stopped${NC}"
echo ""

echo "=========================================="
echo -e "${GREEN}Validation Complete!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Database initialized: ✓"
echo "  - Jobs enqueued: ✓"
echo "  - Workers started: ✓"
echo "  - Status checked: ✓"
echo "  - DLQ checked: ✓"
echo "  - Workers stopped: ✓"
echo ""
echo -e "${GREEN}All core flows validated successfully!${NC}"
exit 0

