"""Test persistence across worker manager restart"""

import pytest
import time
import multiprocessing
import os
from queuectl.store import Store
from queuectl.worker_manager import start_manager, stop_manager, is_manager_running
from queuectl.worker import worker_process


def worker_wrapper_persist(worker_id, shutdown_event, db_path):
    """Worker wrapper function for multiprocessing (must be at module level)"""
    os.environ['QUEUECTL_DB_PATH'] = db_path
    worker_process(worker_id, shutdown_event)


def test_persistence_across_restart(store, temp_db_path):
    """Test that jobs persist across worker manager restart"""
    # Enqueue a job
    job_id = "test-persist-job"
    import sys
    python_cmd = sys.executable
    command = f'{python_cmd} -c "import time; time.sleep(1); print(\'persisted\')"'
    
    store.enqueue_job({
        "id": job_id,
        "command": command,
        "max_retries": 3
    })
    
    # Verify job is enqueued
    pending_jobs = store.list_jobs(state="pending", limit=1)
    assert len(pending_jobs) > 0
    assert pending_jobs[0]["id"] == job_id
    
    # Start worker manager with 1 worker
    # Note: We'll use the direct worker process approach for testing
    # since start_manager requires file system operations
    
    shutdown_event = multiprocessing.Event()
    ctx = multiprocessing.get_context('spawn')
    worker = ctx.Process(
        target=worker_wrapper_persist,
        args=(1, shutdown_event, temp_db_path)
    )
    worker.start()
    
    # Wait a bit for processing to start
    time.sleep(0.5)
    
    # Stop worker (simulate restart)
    shutdown_event.set()
    worker.join(timeout=5)
    if worker.is_alive():
        worker.terminate()
        worker.join()
    
    # Verify job is still in database (either pending or processing)
    jobs = store.list_jobs(limit=10)
    job = next((j for j in jobs if j["id"] == job_id), None)
    
    assert job is not None, "Job should still exist in database"
    assert job["id"] == job_id
    
    # Start worker again (simulate restart)
    shutdown_event = multiprocessing.Event()
    worker2 = ctx.Process(
        target=worker_wrapper_persist,
        args=(1, shutdown_event, temp_db_path)
    )
    worker2.start()
    
    # Wait for job to complete (max 10 seconds)
    max_wait = 10
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        completed_jobs = store.list_jobs(state="completed", limit=1)
        if completed_jobs and completed_jobs[0]["id"] == job_id:
            break
        time.sleep(0.5)
    
    # Stop worker
    shutdown_event.set()
    worker2.join(timeout=5)
    if worker2.is_alive():
        worker2.terminate()
        worker2.join()
    
    # Verify job completed
    completed_jobs = store.list_jobs(state="completed", limit=1)
    assert len(completed_jobs) > 0
    assert completed_jobs[0]["id"] == job_id
    assert completed_jobs[0]["state"] == "completed"

