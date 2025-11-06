"""Worker manager for spawning and controlling worker processes"""

import os
import logging
import multiprocessing
from multiprocessing import Process, Event
from typing import List, Any
import time
import platform
import psutil

logger = logging.getLogger(__name__)

PID_FILE = "./data/worker_manager.pid"
SHUTDOWN_FILE = "./data/worker_manager.shutdown"


class WorkerManager:
    """Manages multiple worker processes"""
    
    def __init__(self, worker_count: int):
        self.worker_count = worker_count
        self.workers: List[Any] = []
        self.shutdown_event = Event()
        logger.info(f"WorkerManager initialized with {worker_count} workers")
    
    def start(self):
        """Start all worker processes"""
        from queuectl.worker import worker_process
        
        # Use spawn method for cross-platform compatibility
        ctx = multiprocessing.get_context('spawn')
        
        for i in range(self.worker_count):
            worker = ctx.Process(
                target=worker_process,
                args=(i + 1, self.shutdown_event),
                name=f"Worker-{i + 1}"
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker {i + 1} (PID: {worker.pid})")
        
        # Write PID file
        self._write_pid_file()
        
        # Monitor for shutdown signal via file
        self._monitor_shutdown()
    
    def _monitor_shutdown(self):
        """Monitor for shutdown signal and wait for workers"""
        try:
            while True:
                # Check if shutdown file exists
                if os.path.exists(SHUTDOWN_FILE):
                    logger.info("Shutdown signal received via file")
                    self.stop()
                    break
                
                # Check if all workers are done
                all_done = all(not w.is_alive() for w in self.workers)
                if all_done:
                    logger.info("All workers finished")
                    break
                
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.stop()
    
    def stop(self):
        """Stop all worker processes gracefully"""
        logger.info("Stopping all workers...")
        self.shutdown_event.set()
        
        # Give workers time to finish current job
        for worker in self.workers:
            worker.join(timeout=10)
            if worker.is_alive():
                logger.warning(f"Force terminating worker {worker.name}")
                worker.terminate()
                worker.join()
        
        # Clean up files
        self._remove_pid_file()
        self._remove_shutdown_file()
        logger.info("All workers stopped")
    
    def _write_pid_file(self):
        """Write manager PID to file"""
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID file written: {PID_FILE}")
    
    def _remove_pid_file(self):
        """Remove PID file"""
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
                logger.info(f"PID file removed: {PID_FILE}")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
    
    def _remove_shutdown_file(self):
        """Remove shutdown signal file"""
        try:
            if os.path.exists(SHUTDOWN_FILE):
                os.remove(SHUTDOWN_FILE)
        except Exception as e:
            logger.error(f"Error removing shutdown file: {e}")


def manager_main_process(worker_count: int):
    """Main entry point for the manager process"""
    from queuectl.utils import setup_logging
    setup_logging()
    
    manager = WorkerManager(worker_count)
    manager.start()


def start_manager(worker_count: int):
    """Start the worker manager (called from CLI)"""
    # Check if manager is already running
    if is_manager_running():
        raise Exception("Worker manager is already running")
    
    # Remove any stale shutdown file
    if os.path.exists(SHUTDOWN_FILE):
        os.remove(SHUTDOWN_FILE)
    
    # Start manager in background process
    ctx = multiprocessing.get_context('spawn')
    manager_process = ctx.Process(
        target=manager_main_process,
        args=(worker_count,),
        name="WorkerManager",
        daemon=False
    )
    manager_process.start()
    
    # Wait a moment for manager to start
    time.sleep(1.0)
    
    # Verify it started
    if not is_manager_running():
        raise Exception("Failed to start worker manager")


def stop_manager():
    """Stop the worker manager (called from CLI)"""
    if not is_manager_running():
        raise Exception("Worker manager is not running")
    
    try:
        # Create shutdown signal file
        os.makedirs(os.path.dirname(SHUTDOWN_FILE), exist_ok=True)
        with open(SHUTDOWN_FILE, 'w') as f:
            f.write('stop')
        
        # Wait for manager to stop
        for _ in range(50):
            if not is_manager_running():
                logger.info("Worker manager stopped successfully")
                return
            time.sleep(0.2)
        
        # If still running, try to terminate forcefully
        if is_manager_running():
            logger.warning("Manager did not stop gracefully, attempting force termination")
            try:
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                
                # Use psutil for cross-platform process termination
                process = None
                try:
                    process = psutil.Process(pid)
                    process.terminate()
                    process.wait(timeout=5)
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    if process:
                        process.kill()
            except Exception as e:
                logger.error(f"Error force terminating manager: {e}")
            finally:
                # Clean up files
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
                if os.path.exists(SHUTDOWN_FILE):
                    os.remove(SHUTDOWN_FILE)
            
    except Exception as e:
        raise Exception(f"Error stopping manager: {e}")


def is_manager_running() -> bool:
    """Check if worker manager is running"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists using psutil (cross-platform)
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            # Process doesn't exist, clean up stale PID file
            try:
                os.remove(PID_FILE)
            except:
                pass
            return False
    except (OSError, ValueError):
        # PID file is invalid, clean up
        try:
            os.remove(PID_FILE)
        except:
            pass
        return False


def get_worker_count() -> int:
    """Get number of active worker processes"""
    if not is_manager_running():
        return 0
    
    try:
        with open(PID_FILE, 'r') as f:
            manager_pid = int(f.read().strip())
        
        # Count child processes using psutil (cross-platform)
        try:
            parent = psutil.Process(manager_pid)
            children = parent.children(recursive=False)
            return len(children)
        except psutil.NoSuchProcess:
            return 0
    except Exception as e:
        logger.debug(f"Error counting workers: {e}")
        return 0
