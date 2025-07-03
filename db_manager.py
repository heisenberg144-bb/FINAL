
"""
Database Management System for O-kharcha
Handles scaling, backup, cleanup, and user data management
"""

import sqlite3
import os
import shutil
import gzip
import json
from datetime import datetime, timedelta
import threading
import time

class DatabaseManager:
    def __init__(self, db_path='okharcha.db'):
        self.db_path = db_path
        self.backup_dir = 'backups'
        self.max_backup_files = 30
        self.cleanup_thread = None
        self.setup_backup_directory()
    
    def setup_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def create_backup(self):
        """Create compressed backup of the database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'okharcha_backup_{timestamp}.db.gz'
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            with open(self.db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            print(f"✅ Database backup created: {backup_filename}")
            self.cleanup_old_backups()
            return backup_path
        except Exception as e:
            print(f"❌ Backup failed: {str(e)}")
            return None
    
    def cleanup_old_backups(self):
        """Remove old backup files to save space"""
        try:
            backup_files = []
            for f in os.listdir(self.backup_dir):
                if f.startswith('okharcha_backup_') and f.endswith('.db.gz'):
                    backup_files.append(os.path.join(self.backup_dir, f))
            
            backup_files.sort(key=os.path.getctime, reverse=True)
            
            # Keep only the latest backups
            for old_backup in backup_files[self.max_backup_files:]:
                os.remove(old_backup)
                print(f"🗑️ Removed old backup: {os.path.basename(old_backup)}")
        except Exception as e:
            print(f"❌ Cleanup failed: {str(e)}")
    
    def get_database_stats(self):
        """Get comprehensive database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Table row counts
        tables = ['expenses', 'budget', 'daily_notes', 'travel_expenses', 'money_collection']
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                stats[f'{table}_count'] = cursor.fetchone()[0]
            except:
                stats[f'{table}_count'] = 0
        
        # Database size
        if os.path.exists(self.db_path):
            stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
        else:
            stats['db_size_mb'] = 0
        
        # Total expenses amount
        try:
            cursor.execute('SELECT SUM(amount) FROM expenses WHERE type = "expense"')
            total_expenses = cursor.fetchone()[0] or 0
            stats['total_expenses'] = total_expenses
        except:
            stats['total_expenses'] = 0
        
        # Total income amount
        try:
            cursor.execute('SELECT SUM(amount) FROM expenses WHERE type = "income"')
            total_income = cursor.fetchone()[0] or 0
            stats['total_income'] = total_income
        except:
            stats['total_income'] = 0
        
        conn.close()
        return stats
    
    def vacuum_database(self):
        """Optimize database and reclaim space"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('VACUUM')
            conn.close()
            print("✅ Database optimized and space reclaimed")
        except Exception as e:
            print(f"❌ Database optimization failed: {str(e)}")
    
    def export_user_data(self, output_format='json'):
        """Export all user data for backup or migration"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            export_data = {}
            export_data['export_timestamp'] = datetime.now().isoformat()
            export_data['app_version'] = 'O-kharcha v1.0'
            
            # Export all tables
            tables = ['expenses', 'budget', 'daily_notes', 'travel_expenses', 'money_collection']
            
            for table in tables:
                try:
                    cursor.execute(f'SELECT * FROM {table}')
                    rows = cursor.fetchall()
                    export_data[table] = [dict(row) for row in rows]
                except:
                    export_data[table] = []
            
            conn.close()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'okharcha_export_{timestamp}.json'
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"📤 Data exported to: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Export failed: {str(e)}")
            return None

# Global database manager instance
db_manager = DatabaseManager()
