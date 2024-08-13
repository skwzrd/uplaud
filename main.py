import os
from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, url_for, session
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from configs import (
    database_path,
    default_expiration_minutes,
    max_data_age_days,
    max_data_age_hours,
    max_data_age_minutes,
    max_file_upload_count,
    max_server_data_size_b,
    max_text_size_b,
    max_total_upload_size_b,
    max_user_count,
    secret
)
from db import get_db_conn, init_db, query_db
from forms import UploadForm, UserForm
from limiter import limiter
from utils import (
    format_fsize,
    format_time_bin,
    get_bcount_from_string,
    get_current_datetime,
    get_current_datetime_w_us_str,
    get_date_format
)
from logg import logger

os.chdir(os.path.dirname(os.path.abspath(__file__)))


app = Flask(__name__)
app.config['SECRET_KEY'] = secret
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = max_total_upload_size_b
app.config['SESSION_COOKIE_NAME']='uplaudcookie'
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SECURE']=True


init_db(database_path)


def get_data(user_id):
    file_records = query_db(database_path, "SELECT * FROM files WHERE user_id=? ORDER BY file_id DESC;", (user_id,))
    text_records = query_db(database_path, "SELECT * FROM texts WHERE user_id=? ORDER BY text_id DESC;", (user_id,))

    now = get_current_datetime()

    for i, file in enumerate(file_records):
        delete_datetime = datetime.strptime(file['delete_datetime'], get_date_format())
        file_records[i]['days_to_expiration'] = format_time_bin((delete_datetime - now).seconds / 60)
        file_records[i]['file_size_b'] = format_fsize(file.file_size_b)

    for i, text in enumerate(text_records):
        delete_datetime = datetime.strptime(text['delete_datetime'], get_date_format())
        text_records[i]['days_to_expiration'] = format_time_bin((delete_datetime - now).seconds / 60)

    return file_records, text_records


@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    flash("Logged out", "success")
    return redirect(url_for('upload_get'))


@limiter.limit("20/day", methods=["GET"])
@limiter.limit("10/minute", methods=["GET"])
@app.route('/', methods=['GET'])
def upload_get():
    user_form: FlaskForm = UserForm()
    upload_form: FlaskForm = UploadForm()
    if session.get('user_id'):
        file_records, text_records = get_data(session.get('user_id'))
        return render_template('index.html', logged_in=True, upload_form=upload_form, user_form=user_form, file_records=file_records, text_records=text_records)

    return render_template('index.html', upload_form=upload_form, user_form=user_form)


@app.route('/p', methods=['POST'])
@limiter.limit("20/day", methods=["POST"])
@limiter.limit("10/minute", methods=["POST"])
def upload_post():
    user_form: FlaskForm = UserForm()
    upload_form: FlaskForm = UploadForm()

    if user_form.submit.data and user_form.validate_on_submit():
        username = user_form.username.data or None
        password_candidate = user_form.password.data or None

        user_form.data.clear()
        upload_form.data.clear()

        if username and password_candidate:
            user_record = query_db(database_path, "SELECT * FROM users WHERE username=?;", (username,), one=True)
            if user_record and check_password_hash(user_record["password"], password_candidate):
                session['user_id'] = user_record['user_id']
                flash("Welcome back!", "success")
                return redirect(url_for('upload_get'))

        flash("Incorrect username or password.", "danger")
        session.clear()
        return redirect(url_for('upload_get'))

    elif upload_form.upload.data and (upload_form.validate_on_submit() or session.get('user_id')):
        user_id = session.get('user_id')

        if not user_id:
            username = upload_form.username.data or None
            password_candidate = upload_form.password.data or None

            user_record = query_db(database_path, "SELECT * FROM users WHERE username=?;", (username,), one=True)
            if user_record and not check_password_hash(user_record["password"], password_candidate):      
                flash(f"The provided username may already exist. Unless you typed the wrong password, please use a different set of credentials for your submission.", "danger")
                return redirect(url_for('upload_get'))
        else:
            user_record = query_db(database_path, "SELECT * FROM users WHERE user_id=?;", (user_id,), one=True)

        if not user_record:
            user_count = query_db(database_path, """select count(*) as s from users;""", one=True)['s']
            if user_count + 1 > max_user_count:
                flash('Server resources are currently overburdened. Come back later.', 'warning')
                return redirect(url_for('upload_get'))


        # content sizes
        text = upload_form.text.data or None
        text_size_b = 0
        if text:
            # Note: wtforms takes care of text character count limit for us
    
            text_size_b = get_bcount_from_string(text)
            if text_size_b > max_text_size_b:
                flash(f'Text must be less than {max_text_size_b} MB. We received {text_size_b} MB.', 'danger')
                return redirect(url_for('upload_get'))

        is_files = any([f for f in upload_form.files.data])
        if (not is_files) and (not text):
            flash('Form must include either text or files.', 'danger')
            return redirect(url_for('upload_get'))

        if upload_form.files.data:
            if len(upload_form.files.data) > max_file_upload_count:
                flash(f'Total file count exceeds {max_file_upload_count}. We received {len(upload_form.files.data)} files.', 'danger')
                return redirect(url_for('upload_get'))


        total_server_file_size_b = query_db(database_path, "SELECT SUM(file_size_b) as s FROM files;", one=True)['s'] or 0
        total_server_text_size_b = query_db(database_path, "SELECT SUM(text_size_b) as s FROM texts;", one=True)['s'] or 0
        total_server_size_b = total_server_text_size_b + total_server_file_size_b

        if total_server_size_b > max_server_data_size_b:
            flash('Server resources are currently depleted. Come back later.', 'warning')
            return redirect(url_for('upload_get'))
        

        # expiration
        current_datetime = get_current_datetime()
        max_date = current_datetime + timedelta(days=max_data_age_days, hours=max_data_age_hours, minutes=max_data_age_minutes)
        default_expiration = current_datetime + timedelta(minutes=default_expiration_minutes)
        max_days_diff = (max_date - current_datetime).days

        delete_days = upload_form.delete_days.data or 0
        delete_hours = upload_form.delete_hours.data or 0
        delete_minutes = upload_form.delete_minutes.data or 0

        if not any([delete_days, delete_hours, delete_minutes]):
            flash(f'Deletion period not provided. Your data will expire in {default_expiration_minutes} minutes.', 'warning')
            delete_datetime = default_expiration
        else:
            delete_datetime = current_datetime + timedelta(days=delete_days, hours=delete_hours, minutes=delete_minutes)

            if delete_datetime > max_date:
                days_diff = (delete_datetime - max_date).days
                flash(f'The deletion period is {days_diff} days over the allowed range. Your data will instead expire in {max_days_diff} days.', 'warning')
                delete_datetime = max_date


        conn = get_db_conn(database_path)
        cursor = conn.cursor()

        if not user_id:
            sql_string = """select user_id from users where username = ?;"""
            cursor.execute(sql_string, (username,))
            user = cursor.fetchone()
            if user:
                user_id = user['user_id']
            else:
                password = generate_password_hash(password_candidate, method='scrypt', salt_length=16)
                sql_string = """INSERT INTO users (username, password, created_datetime) VALUES (?, ?, ?);"""
                params = (username, password, current_datetime)
                cursor.execute(sql_string, params)
                user_id = cursor.lastrowid

        if user_id is None or user_id < 0:
            flash('Internal mishap')
            return redirect(url_for('upload_get'))

        session['user_id'] = user_id

        if text:
            sql_string = """INSERT INTO texts (user_id, text, text_size_b, upload_datetime, delete_datetime) VALUES (?, ?, ?, ?, ?);"""
            params = (user_id, text, text_size_b, current_datetime, delete_datetime)
            cursor.execute(sql_string, params)

        datetime_us_str = get_current_datetime_w_us_str()

        for i, file in enumerate(upload_form.files.data):
            if file:
                filename_original = file.filename

                filename_secure = secure_filename(filename_original)
                unique_prefix = f'{datetime_us_str}__{str(i).zfill(2)}'
                filename_secure = f'{unique_prefix}__{filename_secure}'

                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_secure)
                with open(filepath, "wb") as f:
                    file_data = file.read()
                    f.write(file_data)
                os.chmod(filepath, 0o644)

                file_size_b = os.path.getsize(filepath)

                logger.info(f'New file uploaded: {filename_original}')
                logger.info(f'Size: {format_fsize(file_size_b)}')

                file_type = None
                for header in file.headers:
                    if header[0] == "Content-Type":
                        file_type = header[1].split("/")[-1]
                        break
                if file_type is None:
                    file_type = os.path.splitext(file.filename)[1].lower().strip('.')

                params = (user_id, filename_original, filename_secure, filepath, file_size_b, file_type, current_datetime, delete_datetime)
                sql_param_placeholder = ','.join(['?'] * len(params))
                sql_string = f"""INSERT INTO files (user_id, filename_original, filename_secure, file_path, file_size_b, file_type, upload_datetime, delete_datetime) VALUES ({sql_param_placeholder});"""

                cursor.execute(sql_string, params)

        conn.commit()
        conn.close()

        user_form.data.clear()
        upload_form.data.clear()

        flash('Upload successful.', 'success')
        return redirect(url_for('upload_get'))

    return redirect(url_for('upload_get'))


if __name__ == '__main__':
    app.run(debug=True, port=5500)
