"""CLI interface for QueueCTL job queue system"""

import typer
from typing import Optional, Dict, Any
import json
import uuid
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(help="QueueCTL - CLI Job Queue System")
worker_app = typer.Typer(help="Worker management commands")
dlq_app = typer.Typer(help="Dead Letter Queue commands")
config_app = typer.Typer(help="Configuration commands")
dashboard_app = typer.Typer(help="Dashboard commands")

app.add_typer(worker_app, name="worker")
app.add_typer(dlq_app, name="dlq")
app.add_typer(config_app, name="config")
app.add_typer(dashboard_app, name="dashboard")

console = Console()


@app.command("init-db")
def init_db():
    """Initialize the database and create tables"""
    from queuectl.store import Store
    store = Store()
    store.init_db()
    console.print("[green]Database initialized successfully at ./data/queuectl.db[/green]")


@app.command("enqueue")
def enqueue(
    json_string: Optional[str] = typer.Argument(None, help="Job JSON string"),
    command: Optional[str] = typer.Option(None, "--command", help="Command to execute"),
    id: Optional[str] = typer.Option(None, "--id", help="Job ID (auto-generated if not provided)"),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", help="Maximum retry attempts"),
    run_at: Optional[str] = typer.Option(None, "--run-at", help="Scheduled run time (ISO8601 format)"),
    priority: Optional[int] = typer.Option(0, "--priority", help="Job priority (higher number = higher priority, default: 0)")
):
    """
    Enqueue a new job
    
    Examples:
        queuectl enqueue '{"id":"email-notification-001","command":"python3 -c \"import time; time.sleep(2); print(\\\"Email sent\\\")\""}'
        queuectl enqueue --command "python3 -c \"import time; time.sleep(2); print('Data processing completed')\"" --id data-process-001 --max-retries 3
    """
    from queuectl.store import Store
    from queuectl.config import get_config
    
    store = Store()
    
    # Parse job data
    job_data: Dict[str, Any]
    if json_string:
        try:
            job_data = json.loads(json_string)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing JSON: {e}[/red]")
            raise typer.Exit(1)
    else:
        if not command:
            console.print("[red]Error: Either provide JSON string or use --command flag[/red]")
            raise typer.Exit(1)
        
        job_data = {
            "command": command,
            "priority": priority
        }
        if id:
            job_data["id"] = id
        if max_retries is not None:
            job_data["max_retries"] = max_retries
        if run_at:
            job_data["next_run_at"] = run_at
    
    # Set defaults
    if "id" not in job_data:
        job_data["id"] = str(uuid.uuid4())
    
    if "max_retries" not in job_data:
        config_max_retries = get_config(store, "max_retries")
        job_data["max_retries"] = int(config_max_retries) if config_max_retries else 3
    
    if "priority" not in job_data:
        job_data["priority"] = 0
    
    # Enqueue the job
    store.enqueue_job(job_data)
    console.print(f"[green]Job enqueued successfully: {job_data['id']}[/green]")


@app.command("status")
def status():
    """Show queue status and worker information"""
    from queuectl.store import Store
    from queuectl.worker_manager import is_manager_running, get_worker_count
    
    store = Store()
    counts = store.get_job_counts()
    
    console.print("\n[bold]Queue Status:[/bold]")
    console.print(f"  Pending: {counts.get('pending', 0)}")
    console.print(f"  Processing: {counts.get('processing', 0)}")
    console.print(f"  Completed: {counts.get('completed', 0)}")
    console.print(f"  Failed: {counts.get('failed', 0)}")
    console.print(f"  Dead (DLQ): {counts.get('dead', 0)}")
    
    console.print("\n[bold]Worker Status:[/bold]")
    if is_manager_running():
        worker_count = get_worker_count()
        console.print(f"  Manager: Running")
        console.print(f"  Active workers: {worker_count}")
    else:
        console.print(f"  Manager: Not running")
    console.print()


@app.command("list")
def list_jobs(
    state: Optional[str] = typer.Option(None, "--state", help="Filter by state (pending, processing, completed, failed, dead)"),
    limit: int = typer.Option(50, "--limit", help="Maximum number of jobs to display"),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination")
):
    """List jobs with optional filtering"""
    from queuectl.store import Store
    
    store = Store()
    jobs = store.list_jobs(state=state, limit=limit, offset=offset)
    
    if not jobs:
        console.print("[yellow]No jobs found[/yellow]")
        return
    
    table = Table(title=f"Jobs{' (' + state + ')' if state else ''}")
    table.add_column("ID", style="cyan")
    table.add_column("Command", style="white")
    table.add_column("State", style="yellow")
    table.add_column("Priority", justify="right")
    table.add_column("Attempts", justify="right")
    table.add_column("Max Retries", justify="right")
    table.add_column("Created At", style="dim")
    
    for job in jobs:
        table.add_row(
            job["id"][:16] + "..." if len(job["id"]) > 16 else job["id"],
            job["command"][:40] + "..." if len(job["command"]) > 40 else job["command"],
            job["state"],
            str(job.get("priority", 0)),
            str(job["attempts"]),
            str(job["max_retries"]),
            job["created_at"]
        )
    
    console.print(table)


@app.command("show")
def show_job(
    job_id: str = typer.Argument(..., help="Job ID to display")
):
    """Show detailed information about a specific job including output"""
    from queuectl.store import Store
    
    store = Store()
    job = store.get_job(job_id)
    
    if not job:
        console.print(f"[red]Error: Job '{job_id}' not found[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Job Details: {job_id}[/bold]")
    console.print(f"  Command: {job['command']}")
    console.print(f"  State: {job['state']}")
    console.print(f"  Attempts: {job['attempts']}/{job['max_retries']}")
    console.print(f"  Created At: {job['created_at']}")
    console.print(f"  Updated At: {job['updated_at']}")
    
    if job.get('started_at'):
        console.print(f"  Started At: {job['started_at']}")
    if job.get('finished_at'):
        console.print(f"  Finished At: {job['finished_at']}")
    if job.get('result_code') is not None:
        console.print(f"  Exit Code: {job['result_code']}")
    if job.get('last_error'):
        console.print(f"  Last Error: {job['last_error']}")
    if job.get('next_run_at'):
        console.print(f"  Next Run At: {job['next_run_at']}")
    
    # Show output if available
    stdout = job.get('stdout')
    stderr = job.get('stderr')
    
    if stdout:
        console.print(f"\n[bold]STDOUT:[/bold]")
        console.print(f"[green]{stdout}[/green]")
    
    if stderr:
        console.print(f"\n[bold]STDERR:[/bold]")
        console.print(f"[red]{stderr}[/red]")
    
    if not stdout and not stderr:
        console.print(f"\n[yellow]No output available (job may not have completed yet)[/yellow]")
    
    console.print()


@worker_app.command("start")
def worker_start(
    count: int = typer.Option(1, "--count", help="Number of worker processes to start")
):
    """
    Start worker processes
    
    Example:
        queuectl worker start --count 3
    """
    from queuectl.worker_manager import start_manager
    
    if count < 1:
        console.print("[red]Error: Worker count must be at least 1[/red]")
        raise typer.Exit(1)
    
    try:
        start_manager(count)
        console.print(f"[green]Started worker manager with {count} worker(s)[/green]")
    except Exception as e:
        console.print(f"[red]Error starting workers: {e}[/red]")
        raise typer.Exit(1)


@worker_app.command("stop")
def worker_stop():
    """
    Stop worker processes gracefully
    
    Example:
        queuectl worker stop
    """
    from queuectl.worker_manager import stop_manager
    
    try:
        stop_manager()
        console.print("[green]Worker manager stopped successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error stopping workers: {e}[/red]")
        raise typer.Exit(1)


@dlq_app.command("list")
def dlq_list(
    limit: int = typer.Option(50, "--limit", help="Maximum number of jobs to display"),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination")
):
    """List jobs in the Dead Letter Queue"""
    from queuectl.store import Store
    
    store = Store()
    jobs = store.list_jobs(state="dead", limit=limit, offset=offset)
    
    if not jobs:
        console.print("[yellow]No jobs in DLQ[/yellow]")
        return
    
    table = Table(title="Dead Letter Queue")
    table.add_column("ID", style="cyan")
    table.add_column("Command", style="white")
    table.add_column("Attempts", justify="right")
    table.add_column("Last Error", style="red")
    table.add_column("Finished At", style="dim")
    
    for job in jobs:
        last_error = job.get("last_error", "")
        table.add_row(
            job["id"][:16] + "..." if len(job["id"]) > 16 else job["id"],
            job["command"][:30] + "..." if len(job["command"]) > 30 else job["command"],
            str(job["attempts"]),
            last_error[:50] + "..." if last_error and len(last_error) > 50 else last_error or "N/A",
            job.get("finished_at", "N/A")
        )
    
    console.print(table)


@dlq_app.command("retry")
def dlq_retry(
    job_id: str = typer.Argument(..., help="Job ID to retry"),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", help="Update max retries for the job")
):
    """
    Retry a job from the Dead Letter Queue
    
    Example:
        queuectl dlq retry job1 --max-retries 5
    """
    from queuectl.store import Store
    
    store = Store()
    
    try:
        store.retry_job(job_id, max_retries)
        console.print(f"[green]Job {job_id} moved from DLQ to pending queue[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (max-retries/max_retries, backoff-base/backoff_base, worker-poll-interval/worker_poll_interval, db-path/db_path)"),
    value: str = typer.Argument(..., help="Config value")
):
    """
    Set configuration value
    
    Examples:
        queuectl config set max-retries 5
        queuectl config set max_retries 5
        queuectl config set backoff-base 2
        queuectl config set worker-poll-interval 1
    """
    from queuectl.store import Store
    from queuectl.config import normalize_config_key
    
    # Normalize key (accept both hyphen and underscore)
    normalized_key = normalize_config_key(key)
    
    valid_keys = ["max_retries", "backoff_base", "worker_poll_interval", "db_path"]
    valid_keys_with_hyphen = ["max-retries", "backoff-base", "worker-poll-interval", "db-path"]
    
    if normalized_key not in valid_keys:
        console.print(f"[red]Error: Invalid config key. Valid keys: {', '.join(valid_keys_with_hyphen)} or {', '.join(valid_keys)}[/red]")
        raise typer.Exit(1)
    
    store = Store()
    store.set_config(normalized_key, value)
    console.print(f"[green]Config updated: {normalized_key} = {value}[/green]")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Config key to retrieve (supports both hyphen and underscore formats)")
):
    """
    Get configuration value
    
    Examples:
        queuectl config get max-retries
        queuectl config get max_retries
    """
    from queuectl.store import Store
    from queuectl.config import get_config, normalize_config_key
    
    # Normalize key (accept both hyphen and underscore)
    normalized_key = normalize_config_key(key)
    
    store = Store()
    value = get_config(store, normalized_key)
    
    if value is None:
        console.print(f"[yellow]Config key '{normalized_key}' not set (using default)[/yellow]")
    else:
        console.print(f"{normalized_key} = {value}")


@dashboard_app.command("start")
def dashboard_start(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    port: int = typer.Option(5000, "--port", help="Port to bind to")
):
    """Start the web dashboard"""
    from queuectl.dashboard import start_dashboard
    
    try:
        start_dashboard(host=host, port=port)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting dashboard: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
