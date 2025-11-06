# QueueCTL - Comprehensive Manual Testing Guide

This guide provides step-by-step instructions to manually test all QueueCTL features and requirements with 0% error margin.

## Prerequisites

1. **Environment Setup:**
   ```bash
   # Create conda environment (Rule #11)
   conda create -n queuectl-env python=3.11
   conda activate queuectl-env
   
   # Or use venv
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies:**
   ```bash
   cd queuectl-deploy
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Initialize Database:**
   ```bash
   python3 -m queuectl init-db
   ```
   **Expected Output:** `Database initialized successfully at ./data/queuectl.db`

---

## Test 1: Database Initialization

**Purpose:** Verify database schema creation

**Steps:**
```bash
rm -rf data
python3 -m queuectl init-db
ls -la data/
```

**Expected Results:**
- [PASS] Database file created at `./data/queuectl.db`
- [PASS] No errors in output
- [PASS] Database directory exists

---

## Test 2: Basic Job Enqueue (JSON Format)

**Purpose:** Verify job enqueue using JSON string

**Steps:**
```bash
python3 -m queuectl enqueue '{"id":"test-email-001","command":"python3 -c \"import time; time.sleep(0.5); print(\\\"Email notification sent\\\")\""}'
python3 -m queuectl status
python3 -m queuectl list --state pending
```

**Expected Results:**
- [PASS] Job enqueued successfully with ID "test-email-001"
- [PASS] Status shows 1 pending job
- [PASS] List shows job with state="pending", attempts=0

---

## Test 3: Basic Job Enqueue (CLI Flags)

**Purpose:** Verify job enqueue using command-line flags

**Steps:**
```bash
python3 -m queuectl enqueue --command "python3 -c \"import time; time.sleep(0.5); print('Data processing task completed')\"" --id test-data-process-001 --max-retries 5
python3 -m queuectl list --state pending
```

**Expected Results:**
- [PASS] Job enqueued with ID "test-data-process-001"
- [PASS] Max retries set to 5
- [PASS] Job appears in pending list

---

## Test 4: Auto-Generated Job ID

**Purpose:** Verify UUID generation when ID not provided

**Steps:**
```bash
python3 -m queuectl enqueue --command "python3 -c \"print('auto-id')\""
python3 -m queuectl list --state pending
```

**Expected Results:**
- [PASS] Job enqueued with auto-generated UUID
- [PASS] UUID format is valid (36 characters with hyphens)

---

## Test 5: Job Execution and Completion

**Purpose:** Verify workers process jobs successfully

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue a job
python3 -m queuectl enqueue --command "python3 -c \"print('success')\"" --id success-job

# Start worker
python3 -m queuectl worker start --count 1

# Wait 3 seconds
sleep 3

# Check status
python3 -m queuectl status

# Check completed jobs
python3 -m queuectl list --state completed

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Worker starts successfully
- [PASS] Status shows 1 completed job
- [PASS] Job state is "completed"
- [PASS] Result code is 0
- [PASS] Attempts = 1 (only one attempt needed)

---

## Test 6: Multiple Workers Processing

**Purpose:** Verify multiple workers process jobs in parallel without overlap

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue 5 jobs
for i in {1..5}; do
  python3 -m queuectl enqueue --command "python3 -c \"print('job$i')\"" --id job-$i
done

# Start 3 workers
python3 -m queuectl worker start --count 3

# Wait 5 seconds
sleep 5

# Check status
python3 -m queuectl status

# Check completed jobs
python3 -m queuectl list --state completed

# Stop workers
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] All 5 jobs completed
- [PASS] Each job has attempts = 1 (no duplicate processing)
- [PASS] Status shows 5 completed jobs
- [PASS] No jobs in pending or processing state

---

## Test 7: Retry Logic with Exponential Backoff

**Purpose:** Verify failed jobs retry with exponential backoff

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Set backoff_base to 1 for faster testing
python3 -m queuectl config set backoff_base 1

# Enqueue a failing job with max_retries=2
python3 -m queuectl enqueue --command "python3 -c \"import sys; sys.exit(1)\"" --id fail-job --max-retries 2

# Start worker
python3 -m queuectl worker start --count 1

# Wait 10 seconds (for retries)
sleep 10

# Check DLQ
python3 -m queuectl dlq list

# Check status
python3 -m queuectl status

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Job retried 2 times (attempts = 2)
- [PASS] Job moved to DLQ after max_retries
- [PASS] DLQ list shows job with state="dead"
- [PASS] Status shows 1 dead job
- [PASS] Backoff delay = 1^1 = 1s, 1^2 = 1s (with backoff_base=1)

---

## Test 8: Dead Letter Queue (DLQ) Retry

**Purpose:** Verify jobs can be retried from DLQ

**Steps:**
```bash
# Continue from Test 7 (job should be in DLQ)

# Retry job from DLQ
python3 -m queuectl dlq retry fail-job

# Check pending jobs
python3 -m queuectl list --state pending

# Start worker
python3 -m queuectl worker start --count 1

# Wait 5 seconds
sleep 5

# Check DLQ again
python3 -m queuectl dlq list

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Job moved from DLQ to pending
- [PASS] Attempts reset to 0
- [PASS] Job will retry again

---

## Test 9: Configuration Management

**Purpose:** Verify configuration get/set functionality

**Steps:**
```bash
# Set configuration values
python3 -m queuectl config set max_retries 5
python3 -m queuectl config set backoff_base 3
python3 -m queuectl config set worker_poll_interval 2

# Get configuration values
python3 -m queuectl config get max_retries
python3 -m queuectl config get backoff_base
python3 -m queuectl config get worker_poll_interval
python3 -m queuectl config get db_path

# Get non-existent key
python3 -m queuectl config get non-existent-key
```

**Expected Results:**
- [PASS] Config values set successfully
- [PASS] Config values retrieved correctly
- [PASS] Non-existent key returns default message

---

## Test 10: Job Listing and Filtering

**Purpose:** Verify job listing with state filtering and pagination

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue jobs in different states
python3 -m queuectl enqueue --command "python3 -c \"print('pending1')\"" --id p1
python3 -m queuectl enqueue --command "python3 -c \"print('pending2')\"" --id p2

# Start worker, wait, stop
python3 -m queuectl worker start --count 1
sleep 3
python3 -m queuectl worker stop

# List by state
python3 -m queuectl list --state pending
python3 -m queuectl list --state completed
python3 -m queuectl list --state dead

# List with pagination
python3 -m queuectl list --state completed --limit 1 --offset 0
python3 -m queuectl list --state completed --limit 1 --offset 1
```

**Expected Results:**
- [PASS] Jobs filtered by state correctly
- [PASS] Pagination works (limit and offset)
- [PASS] Empty states handled gracefully

---

## Test 11: Edge Cases - Error Handling

**Purpose:** Verify error handling for invalid inputs

**Steps:**
```bash
# Test 11.1: Invalid JSON
python3 -m queuectl enqueue 'invalid json'
# Expected: Error message about JSON parsing

# Test 11.2: Missing command
python3 -m queuectl enqueue --id test-no-command
# Expected: Error message about missing command

# Test 11.3: DLQ retry non-existent job
python3 -m queuectl dlq retry non-existent-job
# Expected: Error message about job not found

# Test 11.4: Worker stop when not running
python3 -m queuectl worker stop
# Expected: Error message about manager not running

# Test 11.5: Worker start when already running
python3 -m queuectl worker start --count 1
python3 -m queuectl worker start --count 1
# Expected: Error message about manager already running
```

**Expected Results:**
- [PASS] All error cases handled gracefully
- [PASS] Clear error messages displayed
- [PASS] No crashes or exceptions

---

## Test 12: Persistence Across Restart

**Purpose:** Verify jobs persist when workers restart

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue a job
python3 -m queuectl enqueue --command "python3 -c \"import time; time.sleep(1); print('persisted')\"" --id persist-job

# Verify job is pending
python3 -m queuectl list --state pending

# Start worker
python3 -m queuectl worker start --count 1

# Immediately stop worker (before job completes)
sleep 1
python3 -m queuectl worker stop

# Verify job still exists (may be pending or processing)
python3 -m queuectl list

# Start worker again
python3 -m queuectl worker start --count 1

# Wait for completion
sleep 3

# Verify job completed
python3 -m queuectl list --state completed

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Job persists after worker restart
- [PASS] Job is processed after restart
- [PASS] Job completes successfully

---

## Test 13: Scheduled Jobs (run-at)

**Purpose:** Verify scheduled jobs with future run time

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue job scheduled for future (5 seconds from now)
FUTURE_TIME=$(python3 -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat())")
python3 -m queuectl enqueue --command "python3 -c \"print('scheduled')\"" --id scheduled-job --run-at "$FUTURE_TIME"

# Start worker
python3 -m queuectl worker start --count 1

# Wait 2 seconds (job should not run yet)
sleep 2
python3 -m queuectl status

# Wait 5 more seconds (job should run now)
sleep 5
python3 -m queuectl status
python3 -m queuectl list --state completed

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Job not claimed before scheduled time
- [PASS] Job processed after scheduled time
- [PASS] Job completes successfully

---

## Test 14: Atomic Job Claiming (No Duplicate Processing)

**Purpose:** Verify multiple workers don't process the same job

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue 10 jobs
for i in {1..10}; do
  python3 -m queuectl enqueue --command "python3 -c \"print('job$i')\"" --id job-$i
done

# Start 5 workers
python3 -m queuectl worker start --count 5

# Wait 5 seconds
sleep 5

# Check all completed jobs
python3 -m queuectl list --state completed

# Verify no job has attempts > 1
python3 -m queuectl list --state completed | grep -c "attempts.*[2-9]"
# Should return 0 (no jobs with attempts > 1)

# Stop workers
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] All jobs completed
- [PASS] No job has attempts > 1
- [PASS] No duplicate processing occurred

---

## Test 15: Validation Script

**Purpose:** Run the automated validation script

**Steps:**
```bash
cd scripts
chmod +x validate_core_flows.sh
./validate_core_flows.sh
```

**Expected Results:**
- [PASS] Script runs without errors
- [PASS] All validation steps pass
- [PASS] Exit code is 0

---

## Test 16: Pytest Test Suite

**Purpose:** Run automated test suite

**Steps:**
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test
python3 -m pytest tests/test_enqueue_complete.py -v
python3 -m pytest tests/test_retry_dlq.py -v
python3 -m pytest tests/test_multiple_workers.py -v
python3 -m pytest tests/test_persistence_across_restart.py -v
```

**Expected Results:**
- [PASS] All tests pass
- [PASS] No failures or errors
- [PASS] Test coverage for all requirements

---

## Test 17: Job Priority Queues (Bonus Feature)

**Purpose:** Verify jobs with higher priority are processed first

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue jobs with different priorities (low, medium, high)
python3 -m queuectl enqueue --command "python3 -c \"print('low-priority')\"" --id job-low --priority 1
python3 -m queuectl enqueue --command "python3 -c \"print('high-priority')\"" --id job-high --priority 10
python3 -m queuectl enqueue --command "python3 -c \"print('medium-priority')\"" --id job-medium --priority 5

# Verify priority in list
python3 -m queuectl list --state pending

# Start worker
python3 -m queuectl worker start --count 1

# Wait 5 seconds
sleep 5

# Check completed jobs (should be in priority order: high, medium, low)
python3 -m queuectl list --state completed

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Jobs enqueued with different priorities
- [PASS] Priority shown in list output
- [PASS] Jobs executed in priority order (high → medium → low)
- [PASS] Higher priority jobs processed first

---

## Test 18: Job Output Logging (Bonus Feature)

**Purpose:** Verify job output (stdout/stderr) is stored and viewable

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue a successful job
python3 -m queuectl enqueue --command "python3 -c \"print('Success output'); print('Line 2')\"" --id output-test

# Start worker
python3 -m queuectl worker start --count 1

# Wait 3 seconds
sleep 3

# View job details with output
python3 -m queuectl show output-test

# Stop worker
python3 -m queuectl worker stop

# Test with failed job (stderr)
python3 -m queuectl config set backoff-base 1
python3 -m queuectl enqueue --command "python3 -c \"import sys; print('Error output', file=sys.stderr); sys.exit(1)\"" --id error-test --max-retries 1

# Start worker
python3 -m queuectl worker start --count 1

# Wait 5 seconds
sleep 5

# View failed job details with stderr
python3 -m queuectl show error-test

# Stop worker
python3 -m queuectl worker stop
```

**Expected Results:**
- [PASS] Successful job stdout stored and displayed
- [PASS] Failed job stderr stored and displayed
- [PASS] `queuectl show` command works correctly
- [PASS] Output visible in job details

---

## Test 19: Web Dashboard (Bonus Feature)

**Purpose:** Verify web dashboard starts and displays job information

**Steps:**
```bash
# Clean start
rm -rf data
python3 -m queuectl init-db

# Enqueue some jobs
python3 -m queuectl enqueue --command "python3 -c \"print('test1')\"" --id test1
python3 -m queuectl enqueue --command "python3 -c \"print('test2')\"" --id test2 --priority 5

# Start dashboard in background
python3 -m queuectl dashboard start --host 127.0.0.1 --port 5000 &
DASHBOARD_PID=$!

# Wait 2 seconds for dashboard to start
sleep 2

# Test dashboard API endpoint
curl http://127.0.0.1:5000/api/status

# Stop dashboard
kill $DASHBOARD_PID
```

**Expected Results:**
- [PASS] Dashboard starts without errors
- [PASS] Dashboard accessible at http://127.0.0.1:5000
- [PASS] API endpoint returns job statistics
- [PASS] Dashboard displays job list with priority

---

## Final Verification Checklist

Before considering testing complete, verify:

- [ ] Database initialization works
- [ ] Job enqueue (JSON format) works
- [ ] Job enqueue (CLI flags) works
- [ ] Auto-generated job IDs work
- [ ] Jobs execute and complete successfully
- [ ] Multiple workers process jobs in parallel
- [ ] Retry logic with exponential backoff works
- [ ] Failed jobs move to DLQ after max_retries
- [ ] DLQ retry functionality works
- [ ] Configuration get/set works
- [ ] Job listing with state filtering works
- [ ] Error handling for invalid inputs works
- [ ] Jobs persist across worker restarts
- [ ] Scheduled jobs (run-at) work
- [ ] Atomic job claiming prevents duplicates
- [ ] Validation script passes
- [ ] Pytest test suite passes
- [ ] All CLI commands work as specified
- [ ] Job priority queues work (bonus feature)
- [ ] Job output logging works (bonus feature)
- [ ] Web dashboard works (bonus feature)
- [ ] No AI/LLM mentions in code or output
- [ ] No emojis in output
- [ ] Conda environment setup in README (Rule #11)

---

## Common Issues and Solutions

**Issue:** Worker won't start
- **Solution:** Check if workers already running: `python3 -m queuectl status`
- **Solution:** Stop existing workers: `python3 -m queuectl worker stop`

**Issue:** Database errors
- **Solution:** Delete database and reinitialize: `rm -rf data && python3 -m queuectl init-db`

**Issue:** Jobs not completing
- **Solution:** Check logs: `cat ./data/queuectl.log`
- **Solution:** Verify Python command is correct (use `python3` not `python`)

**Issue:** Tests failing
- **Solution:** Ensure temporary database paths are used correctly
- **Solution:** Check worker processes are cleaned up properly

---

## Testing Completion

Once all tests pass, the project meets 100% of requirements with 0% error margin.

**Sign-off:** All tests completed successfully [PASS]

