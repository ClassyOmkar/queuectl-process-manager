"""Test multiple workers processing jobs without overlap"""

import pytest
import time
import multiprocessing
import os
from queuectl.store import Store
from queuectl.worker import worker_process


def worker_wrapper_multi(worker_id, shutdown_event, db_path):
    """Worker wrapper function for multiprocessing (must be at module level)"""
    os.environ['QUEUECTL_DB_PATH'] = db_path
    worker_process(worker_id, shutdown_event)


def test_multiple_workers_no_overlap(store, temp_db_path):
    """Test that multiple workers process jobs without overlap"""
    # Enqueue multiple short-running jobs
    num_jobs = 5
    job_ids = []
    
    for i in range(num_jobs):
        job_id = f"test-multi-job-{i}"
        job_ids.append(job_id)
        import sys
        python_cmd = sys.executable
        store.enqueue_job({
            "id": job_id,
            "command": f'{python_cmd} -c "import time; time.sleep(0.5); print(\'x\')"',
            "max_retries": 3
        })
    
    # Start multiple workers with database path
    num_workers = 3
    shutdown_event = multiprocessing.Event()
    ctx = multiprocessing.get_context('spawn')
    workers = []
    
    for i in range(num_workers):
        worker = ctx.Process(
            target=worker_wrapper_multi,
            args=(i + 1, shutdown_event, temp_db_path)
        )
        worker.start()
        workers.append(worker)
    
    # Wait for all jobs to complete (max 30 seconds)
    max_wait = 30
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        completed_jobs = store.list_jobs(state="completed", limit=num_jobs)
        completed_ids = [j["id"] for j in completed_jobs]
        if all(jid in completed_ids for jid in job_ids):
            break
        time.sleep(0.5)
    
    # Stop workers
    shutdown_event.set()
    for worker in workers:
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()
            worker.join()
    
    # Verify all jobs completed
    completed_jobs = store.list_jobs(state="completed", limit=num_jobs)
    completed_ids = [j["id"] for j in completed_jobs]
    
    assert len(completed_ids) == num_jobs, f"Expected {num_jobs} completed jobs, got {len(completed_ids)}"
    assert all(jid in completed_ids for jid in job_ids), "All jobs should be completed"
    
    # Verify no job has attempts > 1 (no duplicate processing)
    for job in completed_jobs:
        assert job["attempts"] == 1, f"Job {job['id']} should have exactly 1 attempt, got {job['attempts']}"

