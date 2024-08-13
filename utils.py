import os
from datetime import datetime


def get_date_format():
    return '%Y-%m-%d %H:%M:%S'

def get_current_datetime():
    now = datetime.now()
    return datetime.strptime(now.strftime(get_date_format()), get_date_format())

def get_current_datetime_w_us_str():
    now = datetime.now()
    return now.strftime('%Y%m%d_%H%M%S_%f')

def format_fsize(bytes_size):
    if not isinstance(bytes_size, int):
        return None

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    threshold = 1024

    if bytes_size == 0:
        return "0B"

    size = bytes_size
    unit_index = 0

    while size >= threshold and unit_index < len(units) - 1:
        size /= threshold
        unit_index += 1

    formatted_size = f"{size:.1f}{units[unit_index]}"
    if formatted_size.endswith(".0"):
        formatted_size = formatted_size[:-2]
    
    return formatted_size

def format_time_bin(minutes):
    if minutes < 60:
        return f"{round(minutes, 1)}min" if minutes != 1 else "1min"
    elif minutes < 1440:
        hours = minutes // 60
        return f"{round(hours, 1)}h" if hours != 1 else "1h"
    else:
        days = minutes // 1440
        return f"{round(days, 1)}d" if days != 1 else "1d"

def get_bcount_from_string(s):
    return len(s.encode('utf-8'))

def make_path(*filepaths):
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), *filepaths)
