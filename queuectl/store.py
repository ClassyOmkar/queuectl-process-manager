"""Database storage layer for QueueCTL"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class Store:
    """SQLite-based persistent storage for jobs and configuration"""
    
    def __init__(self, db_path: str = None):
        # Check environment variable first, then use provided path, then default
        if db_path is None:
            db_path = os.environ.get('QUEUECTL_DB_PATH', './data/queuectl.db')
        self.db_path = db_path
        self._ensure_data_dir()
        
    def _ensure_data_dir(self):
        """Ensure the data directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        try:
            # Create config table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Create jobs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('pending','processing','completed','failed','dead')),
                    attempts INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    result_code INTEGER,
                    last_error TEXT,
                    next_run_at TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    priority INTEGER DEFAULT 0
                )
            """)
            
            # Add stdout and stderr columns if they don't exist (migration for existing databases)
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN stdout TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN stderr TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add priority column if it doesn't exist (migration for existing databases)
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create index for efficient job claiming
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_state_created 
                ON jobs(state, created_at)
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
        finally:
            conn.close()
    
    def enqueue_job(self, job_data: Dict[str, Any]):
        """Enqueue a new job"""
        conn = self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            conn.execute("""
                INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority)
                VALUES (?, ?, 'pending', 0, ?, ?, ?, ?, ?)
            """, (
                job_data["id"],
                job_data["command"],
                job_data.get("max_retries", 3),
                now,
                now,
                job_data.get("next_run_at"),
                job_data.get("priority", 0)
            ))
            conn.commit()
            logger.info(f"Job enqueued: {job_data['id']}")
        finally:
            conn.close()
    
    def claim_job(self) -> Optional[Dict[str, Any]]:
        """
        Atomically claim a job for processing
        Returns job data if successful, None if no job available
        """
        conn = self._get_connection()
        try:
            # Begin IMMEDIATE transaction to get RESERVED lock
            conn.execute("BEGIN IMMEDIATE")
            
            now = datetime.now(timezone.utc).isoformat()
            
            # Find a claimable job (order by priority DESC, then created_at ASC)
            # Higher priority (larger number) = higher priority
            cursor = conn.execute("""
                SELECT id FROM jobs 
                WHERE state='pending' 
                  AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """, (now,))
            
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return None
            
            job_id = row["id"]
            
            # Attempt to claim it
            cursor = conn.execute("""
                UPDATE jobs 
                SET state='processing', 
                    attempts = attempts + 1, 
                    started_at = ?,
                    updated_at = ?
                WHERE id = ? AND state='pending'
            """, (now, now, job_id))
            
            if cursor.rowcount == 0:
                # Job was claimed by another worker
                conn.rollback()
                return None
            
            # Get the full job data
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            job = dict(cursor.fetchone())
            
            conn.commit()
            logger.info(f"Job claimed: {job_id} (attempt {job['attempts']})")
            return job
            
        except sqlite3.OperationalError as e:
            logger.warning(f"Database busy during claim: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def mark_job_completed(self, job_id: str, result_code: int, stdout: Optional[str] = None, stderr: Optional[str] = None):
        """Mark a job as completed"""
        conn = self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Truncate stdout/stderr to reasonable size (max 10000 chars each)
            truncated_stdout = stdout[:10000] if stdout else None
            truncated_stderr = stderr[:10000] if stderr else None
            
            conn.execute("""
                UPDATE jobs 
                SET state='completed',
                    result_code=?,
                    finished_at=?,
                    updated_at=?,
                    stdout=?,
                    stderr=?
                WHERE id=?
            """, (result_code, now, now, truncated_stdout, truncated_stderr, job_id))
            conn.commit()
            logger.info(f"Job completed: {job_id}")
        finally:
            conn.close()
    
    def mark_job_failed(self, job_id: str, result_code: int, error: str, max_retries: int, backoff_base: int, attempts: int, stdout: Optional[str] = None, stderr: Optional[str] = None):
        """
        Mark a job as failed and schedule retry or move to DLQ
        """
        conn = self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Truncate error to 2000 chars
            truncated_error = error[:2000] if error else None
            
            # Truncate stdout/stderr to reasonable size (max 10000 chars each)
            truncated_stdout = stdout[:10000] if stdout else None
            truncated_stderr = stderr[:10000] if stderr else None
            
            if attempts >= max_retries:
                # Move to DLQ
                conn.execute("""
                    UPDATE jobs 
                    SET state='dead',
                        result_code=?,
                        last_error=?,
                        finished_at=?,
                        updated_at=?,
                        stdout=?,
                        stderr=?
                    WHERE id=?
                """, (result_code, truncated_error, now, now, truncated_stdout, truncated_stderr, job_id))
                logger.info(f"Job moved to DLQ: {job_id} (attempts: {attempts})")
            else:
                # Schedule retry with exponential backoff
                from datetime import timedelta
                delay_seconds = backoff_base ** attempts
                next_run = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                next_run_at = next_run.isoformat()
                
                conn.execute("""
                    UPDATE jobs 
                    SET state='pending',
                        result_code=?,
                        last_error=?,
                        next_run_at=?,
                        updated_at=?,
                        stdout=?,
                        stderr=?
                    WHERE id=?
                """, (result_code, truncated_error, next_run_at, now, truncated_stdout, truncated_stderr, job_id))
                logger.info(f"Job retry scheduled: {job_id} (attempts: {attempts}, next run: {next_run_at})")
            
            conn.commit()
        finally:
            conn.close()
    
    def get_job_counts(self) -> Dict[str, int]:
        """Get count of jobs by state"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT state, COUNT(*) as count 
                FROM jobs 
                GROUP BY state
            """)
            counts = {row["state"]: row["count"] for row in cursor.fetchall()}
            return counts
        finally:
            conn.close()
    
    def list_jobs(self, state: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List jobs with optional filtering"""
        conn = self._get_connection()
        try:
            if state:
                cursor = conn.execute("""
                    SELECT * FROM jobs 
                    WHERE state=? 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (state, limit, offset))
            else:
                cursor = conn.execute("""
                    SELECT * FROM jobs 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def retry_job(self, job_id: str, max_retries: Optional[int] = None):
        """Move a job from DLQ back to pending queue"""
        conn = self._get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Check if job exists and is in DLQ
            cursor = conn.execute("SELECT state FROM jobs WHERE id=?", (job_id,))
            row = cursor.fetchone()
            
            if not row:
                raise ValueError(f"Job {job_id} not found")
            
            if row["state"] != "dead":
                raise ValueError(f"Job {job_id} is not in DLQ (current state: {row['state']})")
            
            # Reset job to pending
            if max_retries is not None:
                conn.execute("""
                    UPDATE jobs 
                    SET state='pending',
                        attempts=0,
                        max_retries=?,
                        next_run_at=NULL,
                        updated_at=?
                    WHERE id=?
                """, (max_retries, now, job_id))
            else:
                conn.execute("""
                    UPDATE jobs 
                    SET state='pending',
                        attempts=0,
                        next_run_at=NULL,
                        updated_at=?
                    WHERE id=?
                """, (now, job_id))
            
            conn.commit()
            logger.info(f"Job retried from DLQ: {job_id}")
        finally:
            conn.close()
    
    def set_config(self, key: str, value: str):
        """Set a configuration value"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO config (key, value) 
                VALUES (?, ?)
            """, (key, value))
            conn.commit()
        finally:
            conn.close()
    
    def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT value FROM config WHERE key=?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
        finally:
            conn.close()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
