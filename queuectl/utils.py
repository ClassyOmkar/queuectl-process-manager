"""Utility functions for QueueCTL"""

import logging
import os
from datetime import datetime, timezone


def setup_logging():
    """Configure logging for QueueCTL"""
    log_dir = "./data"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "queuectl.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def get_utc_now() -> str:
    """Get current UTC time in ISO8601 format"""
    return datetime.now(timezone.utc).isoformat()
