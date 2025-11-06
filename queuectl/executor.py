"""Command execution module with cross-platform support"""

import subprocess
import platform
import logging

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Executes shell commands with cross-platform considerations"""
    
    def __init__(self):
        self.os_type = platform.system()
        logger.info(f"Executor initialized for OS: {self.os_type}")
    
    def execute(self, command: str) -> tuple:
        """
        Execute a shell command and return result
        
        Returns:
            tuple: (exit_code, stdout, stderr)
        """
        try:
            logger.info(f"Executing command: {command}")
            
            # Run command as-is in shell
            # Do not translate or modify user commands
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
            
            logger.info(f"Command completed with exit code: {exit_code}")
            
            return (exit_code, stdout, stderr)
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after 300 seconds: {command}")
            return (124, "", "Command execution timed out after 300 seconds")
        
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return (1, "", f"Execution error: {str(e)}")


def execute_job_command(command: str) -> dict:
    """
    Execute a job command and return detailed results
    
    Returns:
        dict with keys: success (bool), exit_code (int), output (str), error (str)
    """
    executor = CommandExecutor()
    exit_code, stdout, stderr = executor.execute(command)
    
    success = exit_code == 0
    
    # Combine stdout and stderr for error reporting
    output = stdout
    error = stderr if stderr else None
    
    return {
        "success": success,
        "exit_code": exit_code,
        "output": output,
        "error": error
    }
