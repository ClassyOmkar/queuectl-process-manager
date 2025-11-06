"""Test retry logic and DLQ functionality"""

import pytest
import time
import multiprocessing
import os
from queuectl.store import Store
from queuectl.worker import worker_process


def worker_wrapper_retry(worker_id, shutdown_event, db_path):
    """Worker wrapper function for multiprocessing (must be at module level)"""
    os.environ['QUEUECTL_DB_PATH'] = db_path
    worker_process(worker_id, shutdown_event)


def test_failed_job_retries_and_dlq(store, temp_db_path):
    """Test that a failed job retries and moves to DLQ after max retries"""
    # Set backoff_base to 1 for fast testing
    store.set_config("backoff_base", "1")
    
    # Enqueue a job that will fail
    job_id = "test-fail-job"
    import sys
    python_cmd = sys.executable
    command = f'{python_cmd} -c "import sys; sys.exit(1)"'
    max_retries = 2
    
    store.enqueue_job({
        "id": job_id,
        "command": command,
        "max_retries": max_retries
    })
    
    # Start a worker in a separate process with database path
    shutdown_event = multiprocessing.Event()
    ctx = multiprocessing.get_context('spawn')
    
    worker = ctx.Process(
        target=worker_wrapper_retry,
        args=(1, shutdown_event, temp_db_path)
    )
    worker.start()
    
    # Wait for job to move to DLQ (max 30 seconds to account for retries)
    max_wait = 30
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        dlq_jobs = store.list_jobs(state="dead", limit=10)
        if dlq_jobs and any(j["id"] == job_id for j in dlq_jobs):
            break
        time.sleep(0.5)
    
    # Stop worker
    shutdown_event.set()
    worker.join(timeout=5)
    if worker.is_alive():
        worker.terminate()
        worker.join()
    
    # Verify job is in DLQ
    dlq_jobs = store.list_jobs(state="dead", limit=10)
    job = next((j for j in dlq_jobs if j["id"] == job_id), None)
    
    assert job is not None, "Job should be in DLQ"
    assert job["state"] == "dead"
    assert job["attempts"] >= max_retries, f"Job should have {max_retries} or more attempts, got {job['attempts']}"
    assert job["result_code"] != 0, "Failed job should have non-zero exit code"

