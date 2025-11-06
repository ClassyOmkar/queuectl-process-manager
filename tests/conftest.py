"""Pytest configuration and fixtures"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path for testing"""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    db_path = db_dir / "queuectl.db"
    return str(db_path)


@pytest.fixture
def store(temp_db_path):
    """Create a Store instance with temporary database"""
    from queuectl.store import Store
    store = Store(db_path=temp_db_path)
    store.init_db()
    return store


@pytest.fixture(autouse=True)
def cleanup_processes():
    """Cleanup any running worker processes after tests"""
    yield
    # Cleanup will happen in teardown
    import os
    import psutil
    pid_file = "./data/worker_manager.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            try:
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=2)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                pass
        except:
            pass
        try:
            os.remove(pid_file)
        except:
            pass

