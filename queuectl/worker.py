"""Worker process for executing jobs"""

import logging
import time
from multiprocessing import Event
from multiprocessing.synchronize import Event as EventType
from queuectl.store import Store
from queuectl.executor import execute_job_command
from queuectl.config import get_config_int

logger = logging.getLogger(__name__)


class Worker:
    """Worker process that claims and executes jobs"""
    
    def __init__(self, worker_id: int, shutdown_event: EventType):
        self.worker_id = worker_id
        self.shutdown_event = shutdown_event
        self.store = Store()
        logger.info(f"Worker {worker_id} initialized")
    
    def run(self):
        """Main worker loop"""
        logger.info(f"Worker {self.worker_id} started")
        
        while not self.shutdown_event.is_set():
            try:
                # Try to claim a job
                job = self.store.claim_job()
                
                if job is None:
                    # No job available, sleep before trying again
                    poll_interval = get_config_int(self.store, "worker_poll_interval")
                    if poll_interval <= 0:
                        poll_interval = 1
                    time.sleep(poll_interval)
                    continue
                
                # Execute the job
                self._execute_job(job)
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                time.sleep(1)
        
        logger.info(f"Worker {self.worker_id} shutting down")
    
    def _execute_job(self, job: dict):
        """Execute a single job"""
        job_id = job["id"]
        command = job["command"]
        attempts = job["attempts"]
        max_retries = job["max_retries"]
        
        logger.info(f"Worker {self.worker_id} executing job {job_id}: {command}")
        
        try:
            # Execute the command
            result = execute_job_command(command)
            
            if result["success"]:
                # Job completed successfully
                stdout = result.get("output", "")
                stderr = result.get("error", "")
                self.store.mark_job_completed(job_id, result["exit_code"], stdout=stdout, stderr=stderr)
                logger.info(f"Worker {self.worker_id} completed job {job_id}")
            else:
                # Job failed
                stdout = result.get("output", "")
                stderr = result.get("error", "")
                exit_code = result.get("exit_code", 1)
                
                # Create meaningful error message
                if stderr:
                    error_msg = stderr
                elif stdout:
                    error_msg = stdout
                else:
                    # No stderr or stdout, create a generic error message
                    error_msg = f"Command failed with exit code {exit_code}"
                
                backoff_base = get_config_int(self.store, "backoff_base")
                if backoff_base <= 0:
                    backoff_base = 2
                
                self.store.mark_job_failed(
                    job_id,
                    exit_code,
                    error_msg,
                    max_retries,
                    backoff_base,
                    attempts,
                    stdout=stdout,
                    stderr=stderr
                )
                logger.warning(f"Worker {self.worker_id} job {job_id} failed (attempt {attempts}/{max_retries})")
        
        except Exception as e:
            logger.error(f"Worker {self.worker_id} exception executing job {job_id}: {e}")
            # Mark job as failed with exception info
            backoff_base = get_config_int(self.store, "backoff_base")
            if backoff_base <= 0:
                backoff_base = 2
            
            self.store.mark_job_failed(
                job_id,
                1,
                str(e),
                max_retries,
                backoff_base,
                attempts,
                stdout=None,
                stderr=str(e)
            )


def worker_process(worker_id: int, shutdown_event: EventType):
    """Entry point for worker subprocess"""
    from queuectl.utils import setup_logging
    setup_logging()
    
    worker = Worker(worker_id, shutdown_event)
    worker.run()
