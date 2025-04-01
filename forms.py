
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DateTimeField, FieldList, FormField
from wtforms.validators import DataRequired, NumberRange, Length, ValidationError, Optional
from datetime import datetime, timedelta

class QuestionForm(FlaskForm):
    text = TextAreaField('Question Text', validators=[
        DataRequired(),
        Length(max=1000)
    ])
    options = StringField('Options', validators=[
        DataRequired(),
        Length(max=500)
    ])
    correct_option = StringField('Correct Answer', validators=[DataRequired()])
    points = IntegerField('Points', validators=[
        DataRequired(),
        NumberRange(min=1, max=100)
    ])
    time_limit = IntegerField('Time Limit', validators=[
        DataRequired(),
        NumberRange(min=10, max=3600)
    ])

class QuizCreateForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(),
        Length(max=200)
    ])
    description = TextAreaField('Description', validators=[Length(max=2000)])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    classroom_id = SelectField('Classroom', coerce=int, validators=[DataRequired()])
    due_date = DateTimeField('Due Date', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    duration = IntegerField('Total Duration (minutes)', validators=[  # Add this
        DataRequired(),
        NumberRange(min=5, max=360)
    ])
    questions = FieldList(FormField(QuestionForm), min_entries=1)
        
class AssignmentForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(message="Title is required"),
        Length(max=200, message="Title cannot exceed 200 characters")
    ])
    
    description = TextAreaField('Description', validators=[
        DataRequired(message="Description is required"),
        Length(max=2000, message="Description cannot exceed 2000 characters")
    ])
    
    due_date = DateTimeField('Due Date', format='%Y-%m-%d %H:%M', validators=[
        DataRequired(message="Due date is required")
    ])
    
    max_score = IntegerField('Max Score', validators=[
        DataRequired(message="Maximum score is required"),
        NumberRange(min=1, max=1000, message="Score must be between 1-1000")
    ])
    
    subject_id = SelectField('Subject', coerce=int, validators=[
        DataRequired(message="Please select a subject")
    ])
    
    classroom_id = SelectField('Classroom', coerce=int, validators=[
        DataRequired(message="Please select a classroom")
    ])

    def validate_due_date(self, field):
        """Ensure due date is in the future"""
        if field.data and field.data < datetime.now() + timedelta(minutes=30):
            raise ValidationError("Due date must be at least 30 minutes from now")

class SubmissionForm(FlaskForm):
    content = TextAreaField('Your Answer', validators=[
        Optional(),
        Length(max=10000, message="Answer cannot exceed 10,000 characters")
    ])