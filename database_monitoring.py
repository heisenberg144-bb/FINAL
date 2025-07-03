
"""
Real-time Database Monitoring for O-kharcha
Monitors database performance and user activity patterns
"""

import sqlite3
import time
import json
from datetime import datetime, timedelta
import os

class DatabaseMonitor:
    def __init__(self, db_path='okharcha.db'):
        self.db_path = db_path
        self.monitoring_active = False
        self.alert_thresholds = {
            'db_size_mb': 500,  # Alert if DB exceeds 500MB
            'daily_transactions': 10000,  # Alert if daily transactions exceed 10k
            'response_time_ms': 1000,  # Alert if queries take >1 second
        }
    
    def check_database_health(self):
        """Perform comprehensive database health check"""
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'alerts': [],
            'metrics': {}
        }
        
        try:
            # Check database file size
            if os.path.exists(self.db_path):
                db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
                health_report['metrics']['db_size_mb'] = round(db_size_mb, 2)
                
                if db_size_mb > self.alert_thresholds['db_size_mb']:
                    health_report['alerts'].append({
                        'type': 'warning',
                        'message': f'Database size ({db_size_mb:.2f}MB) exceeds threshold'
                    })
            
            # Check database connectivity and response time
            start_time = time.time()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM expenses')
            total_expenses = cursor.fetchone()[0]
            conn.close()
            
            response_time_ms = (time.time() - start_time) * 1000
            health_report['metrics']['response_time_ms'] = round(response_time_ms, 2)
            health_report['metrics']['total_expenses'] = total_expenses
            
            if response_time_ms > self.alert_thresholds['response_time_ms']:
                health_report['alerts'].append({
                    'type': 'warning',
                    'message': f'Database response time ({response_time_ms:.2f}ms) is slow'
                })
            
            # Set overall status based on alerts
            if any(alert['type'] == 'error' for alert in health_report['alerts']):
                health_report['status'] = 'error'
            elif any(alert['type'] == 'warning' for alert in health_report['alerts']):
                health_report['status'] = 'warning'
            
        except Exception as e:
            health_report['status'] = 'error'
            health_report['alerts'].append({
                'type': 'error',
                'message': f'Health check failed: {str(e)}'
            })
        
        return health_report

# Global database monitor instance
db_monitor = DatabaseMonitor()
