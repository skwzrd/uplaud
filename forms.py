from flask_wtf import FlaskForm
from wtforms import (
    IntegerField,
    MultipleFileField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from configs import max_text_size_chars


class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=32)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=512)])
    submit = SubmitField('Submit')

class UploadForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=32)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=512)])
    text = TextAreaField('Text', validators=[Optional(), Length(min=1, max=max_text_size_chars)])
    files = MultipleFileField(validators=[Optional()])
    delete_days = IntegerField('Days', validators=[Optional(), NumberRange(0, 5)], default=0)
    delete_hours = IntegerField('Hours', validators=[Optional(), NumberRange(0, 24)], default=0)
    delete_minutes = IntegerField('Minutes', validators=[Optional(), NumberRange(0, 60)], default=15)
    upload = SubmitField('Upload')
