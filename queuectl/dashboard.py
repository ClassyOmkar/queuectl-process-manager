"""Web dashboard for QueueCTL monitoring"""

import os
import logging
from typing import Dict, Any
from datetime import datetime
from flask import Flask, render_template_string, jsonify

logger = logging.getLogger(__name__)

# HTML template for dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueueCTL Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }
        .stat-card.pending .value { color: #ff9800; }
        .stat-card.processing .value { color: #2196f3; }
        .stat-card.completed .value { color: #4caf50; }
        .stat-card.failed .value { color: #f44336; }
        .stat-card.dead .value { color: #9e9e9e; }
        .jobs-table {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f9f9f9;
            font-weight: 600;
            color: #333;
        }
        .state-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .state-pending { background: #fff3cd; color: #856404; }
        .state-processing { background: #cfe2ff; color: #084298; }
        .state-completed { background: #d1e7dd; color: #0f5132; }
        .state-failed { background: #f8d7da; color: #842029; }
        .state-dead { background: #e9ecef; color: #495057; }
        .refresh-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #0056b3;
        }
        .auto-refresh {
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .auto-refresh label {
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>QueueCTL Dashboard</h1>
        
        <div class="auto-refresh">
            <button class="refresh-btn" onclick="refreshData()">Refresh</button>
            <label>
                <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()">
                Auto-refresh (5s)
            </label>
        </div>
        
        <div class="stats">
            <div class="stat-card pending">
                <h3>Pending</h3>
                <div class="value" id="stat-pending">0</div>
            </div>
            <div class="stat-card processing">
                <h3>Processing</h3>
                <div class="value" id="stat-processing">0</div>
            </div>
            <div class="stat-card completed">
                <h3>Completed</h3>
                <div class="value" id="stat-completed">0</div>
            </div>
            <div class="stat-card failed">
                <h3>Failed</h3>
                <div class="value" id="stat-failed">0</div>
            </div>
            <div class="stat-card dead">
                <h3>Dead (DLQ)</h3>
                <div class="value" id="stat-dead">0</div>
            </div>
        </div>
        
        <div class="jobs-table">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Command</th>
                        <th>State</th>
                        <th>Priority</th>
                        <th>Attempts</th>
                        <th>Created At</th>
                    </tr>
                </thead>
                <tbody id="jobs-table-body">
                    <tr><td colspan="6" style="text-align: center; padding: 20px;">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        
        function refreshData() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update stats
                    document.getElementById('stat-pending').textContent = data.counts.pending || 0;
                    document.getElementById('stat-processing').textContent = data.counts.processing || 0;
                    document.getElementById('stat-completed').textContent = data.counts.completed || 0;
                    document.getElementById('stat-failed').textContent = data.counts.failed || 0;
                    document.getElementById('stat-dead').textContent = data.counts.dead || 0;
                    
                    // Update jobs table
                    const tbody = document.getElementById('jobs-table-body');
                    if (data.jobs.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px;">No jobs found</td></tr>';
                    } else {
                        tbody.innerHTML = data.jobs.map(job => `
                            <tr>
                                <td>${job.id.substring(0, 16)}${job.id.length > 16 ? '...' : ''}</td>
                                <td>${job.command.substring(0, 40)}${job.command.length > 40 ? '...' : ''}</td>
                                <td><span class="state-badge state-${job.state}">${job.state}</span></td>
                                <td>${job.priority || 0}</td>
                                <td>${job.attempts}/${job.max_retries}</td>
                                <td>${new Date(job.created_at).toLocaleString()}</td>
                            </tr>
                        `).join('');
                    }
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                });
        }
        
        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');
            if (checkbox.checked) {
                autoRefreshInterval = setInterval(refreshData, 5000);
            } else {
                if (autoRefreshInterval) {
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                }
            }
        }
        
        // Initial load
        refreshData();
    </script>
</body>
</html>
"""


def create_dashboard_app(db_path: str = None) -> Flask:
    """Create and configure Flask app for dashboard"""
    app = Flask(__name__)
    
    # Set database path
    if db_path:
        os.environ['QUEUECTL_DB_PATH'] = db_path
    
    @app.route('/')
    def index():
        """Render dashboard page"""
        return render_template_string(DASHBOARD_TEMPLATE)
    
    @app.route('/api/status')
    def api_status():
        """API endpoint for queue status"""
        from queuectl.store import Store
        
        store = Store()
        counts = store.get_job_counts()
        jobs = store.list_jobs(limit=50)
        
        return jsonify({
            'counts': counts,
            'jobs': jobs
        })
    
    return app


def start_dashboard(host: str = '127.0.0.1', port: int = 5000, db_path: str = None):
    """Start the dashboard web server"""
    app = create_dashboard_app(db_path)
    logger.info(f"Starting QueueCTL dashboard on http://{host}:{port}")
    print(f"\nQueueCTL Dashboard running at: http://{host}:{port}")
    print(f"Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=False)

