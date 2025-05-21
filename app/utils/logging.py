from datetime import datetime
from ..models.database import get_db

def log_activity(user_id, action, details=None):
    """Log user activity to the database."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''INSERT INTO activity_logs 
                        (user_id, action, details, timestamp) 
                        VALUES (%s, %s, %s, %s)''',
                     (user_id, action, details, now))
    except Exception as e:
        print(f"Error logging activity: {e}") 