from datetime import timedelta

from utils import format_fsize, format_time_bin, make_path

sitename = 'Uplaud'
sysadmin_email = ""
secret: str = 'jhfrjeghfjrghjlllloooooooooorgnvnfn' # change me
database_path: str = make_path('uplaud.db')

max_total_upload_size_b: int = 100 * 1024 * 1024 # nginx will require setting `require client_max_body_size 100m`;
max_total_upload_size_str: str = format_fsize(max_total_upload_size_b)
max_text_size_b: int = 10 * 1024 * 1024
max_server_data_size_b: int = 5 * 1024 * 1024 * 1024
min_request_content_length_for_file_upload: int = 1024

max_text_size_chars: int = 10_000_000

default_expiration_minutes: int = 15
default_expiration_str: str = format_time_bin(default_expiration_minutes)

# these sum together to create a `max_data_age` for uploaded content
max_data_age_days: int = 5
max_data_age_hours: int = 24
max_data_age_minutes: int = 15
max_data_age: timedelta = timedelta(days=max_data_age_days, hours=max_data_age_hours, minutes=max_data_age_minutes)
max_data_age_str: str = format_time_bin(max_data_age.total_seconds() / 60)

max_file_upload_count: int = 10

max_user_count: int = 20

