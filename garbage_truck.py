import datetime
import os

from configs import database_path
from db import get_db_conn
from logg import logger
from utils import make_path


def remove_expired_data():
    conn = get_db_conn(database_path)
    cursor = conn.cursor()
    cursor.execute('SELECT file_path FROM files WHERE delete_datetime < ?', (datetime.datetime.now(),))
    rows = cursor.fetchall()

    if rows:
        logger.warning(f'Expired: {len(rows)}')

    for row in rows:
        filepath = make_path(row['file_path']) 
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.warning(f'Rm: {filepath}')

    cursor.execute('DELETE FROM files WHERE delete_datetime < ?', (datetime.datetime.now(),))
    cursor.execute('DELETE FROM texts WHERE delete_datetime < ?', (datetime.datetime.now(),))

    cursor.execute('''
    DELETE FROM users
    WHERE user_id NOT IN (
        SELECT DISTINCT user_id FROM files
        UNION
        SELECT DISTINCT user_id FROM texts
    );
    ''')
    conn.commit()
    conn.close()
    

if __name__=='__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    remove_expired_data()
