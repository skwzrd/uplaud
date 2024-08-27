import os
from datetime import datetime

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from configs import (
    database_path,
    default_expiration_str,
    max_data_age_str,
    max_file_upload_count,
    max_total_upload_size_b,
    max_total_upload_size_str,
    secret,
    sitename,
    sysadmin_email
)
from db import init_db, query_db
from forms import UploadForm, UserForm
from limiter import limiter
from logg import logger
from utils import (
    format_fsize,
    format_time_bin,
    get_bcount_from_string,
    get_current_datetime,
    get_current_datetime_w_us_str,
    get_date_format
)


def create_app():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config['SECRET_KEY'] = secret
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    app.config['MAX_CONTENT_LENGTH'] = max_total_upload_size_b
    app.config['SESSION_COOKIE_NAME'] = 'cookiedough'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True

    limiter.init_app(app)
    init_db(database_path)
    
    return app


app = create_app()


def get_data(user_id):
    file_records = query_db(database_path, 'SELECT * FROM files WHERE user_id=? ORDER BY file_id DESC;', (user_id,))
    text_records = query_db(database_path, 'SELECT * FROM texts WHERE user_id=? ORDER BY text_id DESC;', (user_id,))

    now = get_current_datetime()

    for i, file in enumerate(file_records):
        delete_datetime = datetime.strptime(file['delete_datetime'], get_date_format())
        file_records[i]['expiration_str'] = format_time_bin((delete_datetime - now).total_seconds() / 60)
        file_records[i]['file_size_str'] = format_fsize(file.file_size_b)

    for i, text in enumerate(text_records):
        delete_datetime = datetime.strptime(text['delete_datetime'], get_date_format())
        text_records[i]['expiration_str'] = format_time_bin((delete_datetime - now).total_seconds() / 60)

    return file_records, text_records


def save_text(text, user_id, delete_datetime):
    if not text:
        return

    text_size_b = get_bcount_from_string(text)
    current_datetime = get_current_datetime()

    sql_string = '''INSERT INTO texts (user_id, text, text_size_b, upload_datetime, delete_datetime) VALUES (?, ?, ?, ?, ?);'''
    params = (user_id, text, text_size_b, current_datetime, delete_datetime)
    query_db(database_path, sql_string, params, commit=True)


def save_files(files, user_id, delete_datetime):
    if not files:
        return

    datetime_us_str = get_current_datetime_w_us_str()

    for i, file in enumerate(files):
        if not file:
            continue

        filename_original = file.filename
        filename_secure = secure_filename(filename_original)
        unique_prefix = f'{datetime_us_str}__{str(i).zfill(2)}'
        filename_secure = f'{unique_prefix}__{filename_secure}'

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_secure)
        with open(filepath, 'wb') as f:
            file_data = file.read()
            f.write(file_data)
        os.chmod(filepath, 0o644) # o+r+w g+r a+r, no +x

        file_size_b = os.path.getsize(filepath)

        d = dict(
            current_datetime=g.current_datetime,
            user_id=user_id,
            x_forwarded_for=request.headers.get("X-Forwarded-For", None),
            remote_addr=request.headers.get("Remote-Addr", None),
            referrer=request.referrer,
            content_md5=request.content_md5,
            origin=request.origin,
            scheme=request.scheme,
            method=request.method,
            root_path=request.root_path,
            path=request.path,
            query_string=request.query_string.decode(),
            user_agent=request.user_agent.__str__(),
            x_forwarded_proto=request.headers.get("X-Forwarded-Proto", None),
            x_forwarded_host=request.headers.get("X-Forwarded-Host", None),
            x_forwarded_prefix=request.headers.get("X-Forwarded-Prefix", None),
            host=request.headers.get("Host", None),
            connection=request.headers.get("Connection", None),
            content_length=request.content_length,
        )
        sql_placeholder = ','.join(['?'] * len(d))
        cols = ','.join([k for k in d])
        sql_string = f'''INSERT INTO logs ({cols}) VALUES ({sql_placeholder});'''
        params = [v for v in d.values()]
        query_db(database_path, sql_string, params, commit=True)

        file_type = None
        for header in file.headers:
            if header[0] == 'Content-Type':
                file_type = header[1].split('/')[-1]
                break

        if file_type is None:
            file_type = os.path.splitext(file.filename)[1].lower().strip('.')

        params = (user_id, filename_original, filename_secure, filepath, file_size_b, file_type, g.current_datetime, delete_datetime)
        sql_placeholder = ','.join(['?'] * len(params))
        sql_string = f'''INSERT INTO files (user_id, filename_original, filename_secure, file_path, file_size_b, file_type, upload_datetime, delete_datetime) VALUES ({sql_placeholder});'''

        query_db(database_path, sql_string, params, commit=True)


@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    flash('See you later!', 'success')
    return redirect(url_for('upload_get'))


@app.route('/', methods=['GET'])
def upload_get():
    user_form: UserForm = UserForm()
    upload_form: UploadForm = UploadForm()

    d = dict(
        upload_form=upload_form,
        user_form=user_form,
        default_expiration_str=default_expiration_str,
        max_data_age_str=max_data_age_str,
        logged_in=session.get('user_id'),
        sitename=sitename,
        max_total_upload_size_b=max_total_upload_size_b,
        max_file_upload_count=max_file_upload_count,
        max_total_upload_size_str=max_total_upload_size_str,
        sysadmin_email=sysadmin_email,
    )

    if session.get('user_id'):
        file_records, text_records = get_data(session.get('user_id'))
        d.update(dict(
            file_records=file_records,
            text_records=text_records,
        ))
        return render_template('index.html', **d)

    return render_template('index.html', **d)


@app.route('/p', methods=['POST'])
@limiter.limit('20/day', methods=['POST'])
@limiter.limit('10/minute', methods=['POST'])
def upload_post():
    user_form: UserForm = UserForm()
    upload_form: UploadForm = UploadForm()

    g.current_datetime = get_current_datetime()

    if user_form.submit.data and user_form.validate_on_submit():
        # form validation process will set session id, effectively logging the user in
        return redirect(url_for('upload_get'))

    elif upload_form.upload.data and upload_form.validate_on_submit() and session.get('user_id'):

        # set during form validation
        user_id = session['user_id']
        delete_datetime = g.delete_datetime

        save_text(upload_form.text.data, user_id, delete_datetime)
        save_files(upload_form.files.data, user_id, delete_datetime)

        flash('Upload successful.', 'success')

    return redirect(url_for('upload_get'))


if __name__ == '__main__':
    app.run(debug=True, port=5500)
