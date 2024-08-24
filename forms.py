from datetime import timedelta

from flask import flash, g, redirect, url_for, session
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import (
    MultipleFileField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, ValidationError

from configs import (
    database_path,
    default_expiration_minutes,
    max_data_age_days,
    max_data_age_hours,
    max_data_age_minutes,
    max_file_upload_count,
    max_server_data_size_b,
    max_text_size_b,
    max_text_size_chars, 
    max_user_count
)
from db import query_db, get_db_conn
from utils import get_bcount_from_string, format_fsize


def get_user(username):
    return query_db(database_path, 'SELECT * FROM users WHERE username=?;', (username,), one=True)


def is_correct_password(user_record, password_candidate):
    return check_password_hash(user_record['password'], password_candidate)


def create_user(username, password_candidate):
    password = generate_password_hash(password_candidate, method='scrypt', salt_length=16)
    conn = get_db_conn(database_path)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username, password, created_datetime) VALUES (?, ?, ?);', (username, password, g.current_datetime))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    assert user_id >= 0
    return user_id


def validate_username_is_provided(form, field):
    username = form.username.data

    if username:
        form.username.data = username.strip()

    if not username:
        flash('Please provide a username.', 'warning')
        raise ValidationError('Please provide a username.')


def validate_login_user(form, field):
    '''Login user should already exist.'''

    username = form.username.data
    password_candidate = form.password.data

    user_record = get_user(username)

    if not user_record or not is_correct_password(user_record, password_candidate):
        flash('Incorrect username or password.', 'warning')
        raise ValidationError('Incorrect username or password.')

    session['user_id'] = user_record['user_id']


def validate_uploading_user(form, field):
    '''Uploading users can be existing users, or new users.'''

    if session.get('user_id'):
        return

    username = form.username.data
    password_candidate = form.password.data

    user_record = get_user(username)

    if not user_record:
        user_count = query_db(database_path, '''select count(*) as s from users;''', one=True)['s']
        if user_count + 1 > max_user_count:
            flash('Server resources are currently overburdened. Come back later.', 'warning')
            return redirect(url_for('upload_get'))

        session['user_id'] = create_user(username, password_candidate)
        return

    if not is_correct_password(user_record, password_candidate):      
        flash(f'The provided username may already exist. Unless you typed the wrong password, please use a different set of credentials for your submission.', 'danger')
        return redirect(url_for('upload_get'))

    session['user_id'] = user_record['user_id']


def validate_upload(form, field):
    text = form.text.data or None
    form.text.data = text

    if text:
        text_size_b = get_bcount_from_string(text)
        if text_size_b > max_text_size_b:
            flash(f'Text must be less than {format_fsize(max_text_size_b)}. We received {format_fsize(text_size_b)}.', 'warning')
            raise ValidationError(f'Text must be less than {format_fsize(max_text_size_b)}. We received {format_fsize(text_size_b)}.')

    files = [f for f in form.files.data]
    file_count = len(files)
    is_files = any(files)
    if not text and not is_files:
        flash('Form must include either text or files.', 'warning')
        raise ValidationError('Form must include either text or files.')

    if file_count > max_file_upload_count:
        flash(f'Total file count exceeds {max_file_upload_count}. We received {file_count} files.')
        raise ValidationError(f'Total file count exceeds {max_file_upload_count}. We received {file_count} files.')


def validate_minutes(form, field):
    if form.delete_days.data > max_data_age_minutes:
        flash(f'There is currently a limit of {max_data_age_days} days. This limit was used.', 'warning')
        form.deleted_days.data = max_data_age_days


def validate_hours(form, field):
    if form.delete_hours.data > max_data_age_hours:
        flash(f'There is currently a limit of {max_data_age_days} hours. This limit was used.', 'warning')
        form.delete_hours.data = max_data_age_days


def validate_unit_of_time(field_name):
    '''Coerces the data, will not raise a ValidationError'''

    def _validate_unit_of_time(form, field):
        try:
            value = int(form[field_name].data)
            if value < 0:
                value = 0
        except:
            value = 0

        form[field_name].data = value

    return _validate_unit_of_time


def validate_unit_of_times(form, field):
    '''Coerces the data, will not raise a ValidationError'''

    current_datetime = g.current_datetime
    max_date = current_datetime + timedelta(days=max_data_age_days, hours=max_data_age_hours, minutes=max_data_age_minutes)
    default_expiration = current_datetime + timedelta(minutes=default_expiration_minutes)

    delete_days = form.delete_days.data or 0
    delete_hours = form.delete_hours.data or 0
    delete_minutes = form.delete_minutes.data or 0

    if not any([delete_days, delete_hours, delete_minutes]):
        flash(f'Deletion period not provided. Your data will expire in {default_expiration_minutes} minutes.', 'warning')
        g.delete_datetime = default_expiration
        return

    delete_datetime = current_datetime + timedelta(days=delete_days, hours=delete_hours, minutes=delete_minutes)
    if delete_datetime > max_date:
        days_diff = (delete_datetime - max_date).days
        flash(f'The deletion period is {days_diff} days over the allowed range. Your data will instead expire in {max_data_age_days} days.', 'warning')
        g.delete_datetime = max_date
        return

    g.delete_datetime = delete_datetime
    return


def validate_server_capacity(form, field):
    total_server_file_size_b = query_db(database_path, 'SELECT SUM(file_size_b) as s FROM files;', one=True)['s'] or 0
    total_server_text_size_b = query_db(database_path, 'SELECT SUM(text_size_b) as s FROM texts;', one=True)['s'] or 0
    total_server_size_b = total_server_text_size_b + total_server_file_size_b

    if total_server_size_b > max_server_data_size_b:
        flash('Server resources are currently depleted. Come back later.', 'warning')
        raise ValidationError('Server resources are currently depleted. Come back later.')


class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=512), validate_username_is_provided], description='We trim whitespace from usernames.', render_kw={'placeholder': 'Username'})
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=512), validate_login_user], description='We do not trim whitespace from passwords.', render_kw={'placeholder': 'Password'})
    submit = SubmitField('Submit')


class UploadForm(FlaskForm):
    username = StringField('Username', validators=[Length(min=0, max=512), validate_uploading_user], render_kw={'placeholder': 'Username'})
    password = PasswordField('Password', validators=[Length(min=0, max=512)], render_kw={'placeholder': 'Password'})

    text = TextAreaField('Text', [Length(min=0, max=max_text_size_chars)])
    files = MultipleFileField('Files', [validate_upload, validate_server_capacity])

    delete_days = StringField('Delete in Days', [Length(0, 4), validate_unit_of_time('delete_days')], description=f'Limit of {max_data_age_days} days', render_kw={'placeholder': 'Days', 'style': 'width: 4em;'})
    delete_hours = StringField('Delete in Hours', [Length(0, 4), validate_unit_of_time('delete_hours')], description=f'Limit of {max_data_age_hours} hours', render_kw={'placeholder': 'Hours', 'style': 'width: 4em;'})
    delete_minutes = StringField('Delete in Minutes', [Length(0, 4), validate_unit_of_time('delete_minutes'), validate_unit_of_times], description=f'Limit of {max_data_age_minutes} minutes', render_kw={'placeholder': 'Minutes', 'style': 'width: 4em;'})

    upload = SubmitField('Upload', validators=[])

