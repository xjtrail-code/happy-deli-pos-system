from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, SelectMultipleField, TextAreaField, BooleanField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Optional, NumberRange, Email, Length, EqualTo, ValidationError


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(message='Email is required.'), Email(message='Invalid email address.')])
    password = PasswordField('Password', validators=[DataRequired(message='Password is required.')])
    submit = SubmitField('Sign In')