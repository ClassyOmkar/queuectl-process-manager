"""Test enqueue and complete job flow"""

import pytest
import time
import multiprocessing
import os
from queuectl.store import Store
from queuectl.worker_manager import WorkerManager, start_manager, stop_manager, is_manager_running
from queuectl.worker import worker_process


def worker_process_with_db(worker_id, shutdown_event, db_path):
    """Worker process entry point with database path"""
    import os
    os.environ['QUEUECTL_DB_PATH'] = db_path
    from queuectl.utils import setup_logging
    from queuectl.worker import Worker
    setup_logging()
    worker = Worker(worker_id, shutdown_event)
    worker.run()


def worker_wrapper_func(shutdown_event, db_path):
    """Worker wrapper function for multiprocessing (must be at module level)"""
    import os
    os.environ['QUEUECTL_DB_PATH'] = db_path
    from queuectl.utils import setup_logging
    from queuectl.worker import Worker
    setup_logging()
    worker = Worker(1, shutdown_event)
    worker.run()


def test_enqueue_and_complete(store, temp_db_path):
    """Test that a job can be enqueued and completed successfully"""
    # Enqueue a job that will succeed
    job_id = "test-job-1"
    import sys
    python_cmd = sys.executable
    command = f'{python_cmd} -c "print(\'ok\')"'
    
    store.enqueue_job({
        "id": job_id,
        "command": command,
        "max_retries": 3
    })
    
    # Verify job is enqueued
    job = store.list_jobs(state="pending", limit=1)[0]
    assert job["id"] == job_id
    assert job["state"] == "pending"
    assert job["attempts"] == 0
    
    # Start a worker in a separate process with same database path
    shutdown_event = multiprocessing.Event()
    ctx = multiprocessing.get_context('spawn')
    
    # Use module-level function instead of local function
    worker = ctx.Process(target=worker_wrapper_func, args=(shutdown_event, temp_db_path))
    worker.start()
    
    # Wait for job to complete (max 10 seconds)
    max_wait = 10
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        jobs = store.list_jobs(state="completed", limit=1)
        if jobs and jobs[0]["id"] == job_id:
            break
        time.sleep(0.5)
    
    # Stop worker
    shutdown_event.set()
    worker.join(timeout=5)
    if worker.is_alive():
        worker.terminate()
        worker.join()
    
    # Verify job completed
    completed_jobs = store.list_jobs(state="completed", limit=1)
    assert len(completed_jobs) > 0, "Job should be completed"
    completed_job = completed_jobs[0]
    assert completed_job["id"] == job_id
    assert completed_job["state"] == "completed"
    assert completed_job["result_code"] == 0

