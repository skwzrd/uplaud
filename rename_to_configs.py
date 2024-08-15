from utils import make_path

secret = 'jhfrjeghfjrghjlllloooooooooorgnvnfn' # change me

database_path = make_path('uplaud.db')

max_total_upload_size_b = 100 * 1024 * 1024
max_text_size_b = 10 * 1024 * 1024
max_server_data_size_b = 5 * 1024 * 1024 * 1024

max_text_size_chars = 10_000_000

default_expiration_minutes = 15
max_data_age_days = 5
max_data_age_hours = 24
max_data_age_minutes = 15

max_file_upload_count = 10

max_user_count = 20
