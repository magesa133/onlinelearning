from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, 
    IntegerField, DateTimeField, FieldList, 
    FormField, FileField, BooleanField,
    SelectMultipleField
)
from wtforms.validators import (
    DataRequired, NumberRange, Length, 
    ValidationError, Optional, InputRequired,
    Regexp
)
from flask_wtf.file import FileAllowed, FileRequired
from flask_login import current_user
from datetime import datetime, timedelta
from wtforms.widgets import DateTimeInput
from flask import current_app as app
from models import Classroom, Subject



class CustomDateTimeField(DateTimeField):
    widget = DateTimeInput()
    
    def __init__(self, *args, **kwargs):
        kwargs['format'] = '%Y-%m-%dT%H:%M'  # HTML5 datetime-local format
        super().__init__(*args, **kwargs)
    
    def process_formdata(self, valuelist):
        if not valuelist or not valuelist[0]:
            self.data = None
            return
            
        try:
            # Handle the HTML5 datetime-local format (without seconds)
            self.data = datetime.strptime(valuelist[0], '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                # Fallback to format with seconds if needed
                self.data = datetime.strptime(valuelist[0], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                self.data = None
                raise ValueError('Please enter a valid date and time')
            
            
class TimeSinceFormatter:
    def __init__(self):
        self.format = '%Y-%m-%dT%H:%M'
        self.alternate_format = '%Y-%m-%dT%H:%M:%S'
    
    def format_time_since(self, dt, default="just now"):
        """Formats time difference in human-readable way"""
        if not dt:
            return default
            
        try:
            if isinstance(dt, str):
                try:
                    dt = datetime.strptime(dt, self.format)
                except ValueError:
                    dt = datetime.strptime(dt, self.alternate_format)
            
            now = datetime.utcnow()
            diff = now - dt
            
            if diff.days > 365:
                years = diff.days // 365
                return f"{years} year{'s' if years > 1 else ''} ago"
            elif diff.days > 30:
                months = diff.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
            elif diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                return default
                
        except ValueError:
            return default



class QuizCreateForm(FlaskForm):
    title = StringField('Quiz Title', validators=[
        DataRequired(message="Quiz title is required"),
        Length(max=150, message="Title cannot exceed 150 characters"),
        Regexp(r'^[\w\s\-\.\?\!]+$', message="Title contains invalid characters")
    ], render_kw={
        'placeholder': 'Enter quiz title',
        'class': 'form-control',
        'autocomplete': 'off',
        'minlength': '3',
        'maxlength': '150'
    })
    
    description = TextAreaField('Description (Optional)', 
        validators=[
            Optional(),
            Length(max=2000, message="Description cannot exceed 2000 characters")
        ],
        render_kw={
            'rows': 3,
            'placeholder': 'Quiz instructions, guidelines...',
            'class': 'form-control',
            'maxlength': '2000'
        })
    
    subject_id = SelectField('Subject', 
        coerce=int, 
        validators=[DataRequired(message="Please select a subject")],
        render_kw={
            'class': 'form-select',
            'data-validate': 'required'
        })
    
    classroom_id = SelectField('Classroom', 
        coerce=int, 
        validators=[DataRequired(message="Please select a classroom")],
        render_kw={
            'class': 'form-select',
            'data-validate': 'required'
        })
    
    due_date = CustomDateTimeField('Due Date', 
        validators=[
            DataRequired(message="Please select a due date")
        ],
        render_kw={
            'class': 'form-control',
            'min': (datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M'),
            'type': 'datetime-local',
            'data-validate': 'future-datetime'
        })
    
    time_limit = IntegerField('Time Limit (minutes)', 
        validators=[
            DataRequired(message="Please enter time limit"),
            NumberRange(min=5, max=360, message="Time must be between 5-360 minutes")
        ],
        default=30,
        render_kw={
            'class': 'form-control',
            'min': '5',
            'max': '360',
            'step': '5',
            'data-validate': 'number-range'
        })

    # New safe additions
    categories = SelectMultipleField('Categories',
        coerce=int,
        validators=[Optional()],
        render_kw={
            'class': 'form-select',
            'data-placeholder': 'Select categories (optional)'
        })
    
    allow_comments = BooleanField('Allow Student Comments',
        default=False,
        render_kw={
            'class': 'form-check-input'
        })

    def validate_due_date(self, field):
        if field.data < datetime.now() + timedelta(minutes=30):
            raise ValidationError("Due date must be at least 30 minutes from now")
        
def validate(self, extra_validators=None):
    initial_validation = super(QuizCreateForm, self).validate()
    if not initial_validation:
        return False
        
    # Get the classroom and subject
    classroom = Classroom.query.get(self.classroom_id.data)
    subject = Subject.query.get(self.subject_id.data)
    
    # Check if the classroom teaches this subject
    if classroom and subject not in classroom.subjects:
        self.classroom_id.errors.append("Selected classroom doesn't teach this subject")
        return False
        
    return True


class QuizEditForm(QuizCreateForm):
    is_published = BooleanField('Publish Immediately', default=False)
    notify_students = BooleanField('Notify Students About Changes', default=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove required validator for due_date in edit mode
        self.due_date.validators = [Optional()]
        
        # Adjust minimum due date for existing quizzes
        self.due_date.render_kw['min'] = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    def validate_due_date(self, field):
        """More lenient validation for editing existing quizzes"""
        if field.data and field.data < datetime.now():
            raise ValidationError("Due date cannot be in the past")
    
    def validate(self, extra_validators=None):
        initial_validation = super(QuizEditForm, self).validate()
        if not initial_validation:
            return False
            
        # For published quizzes, don't allow removing due date
        if self.is_published.data and not self.due_date.data:
            self.due_date.errors.append("Published quizzes must have a due date")
            return False
            
        return True


class MessageForm(FlaskForm):
    title = StringField('Subject', validators=[
        DataRequired(), 
        Length(max=200)
    ])
    content = TextAreaField('Message', validators=[
        DataRequired(),
        Length(min=10, message="Message must be at least 10 characters long")
    ])
    classroom_id = SelectField('Recipient Class', coerce=int)
    recipient_id = SelectField(
        'Recipient',
        choices=[],
        coerce=lambda x: int(x) if str(x).isdigit() else None,
        validate_choice=False
    )
    is_urgent = BooleanField('Mark as urgent')
    is_announcement = BooleanField('Send as announcement to all class members')


class QuestionForm(FlaskForm):
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer')
    ]
    
    question_type = SelectField('Question Type',
        choices=QUESTION_TYPES,
        default='multiple_choice',
        validators=[DataRequired()],
        render_kw={
            'class': 'form-select question-type'
        })
    
    time_limit = IntegerField('Time Limit (seconds)',
        validators=[
            Optional(),
            NumberRange(min=10, max=3600, message="Time must be between 10-3600 seconds")
        ],
        default=60,
        render_kw={
            'class': 'form-control question-time-limit',
            'min': '10',
            'max': '3600'
        })
    
    text = TextAreaField('Question', 
        validators=[
            DataRequired(message="Question text is required"),
            Length(max=1000, message="Question cannot exceed 1000 characters")
        ], 
        render_kw={
            'rows': 3,
            'placeholder': 'Enter your question here...',
            'class': 'form-control question-text',
            'maxlength': '1000'
        })
    
    options = StringField('Options', 
        validators=[
            Optional(),  # Changed to optional for non-MC questions
            Length(max=500, message="Options text too long")
        ], 
        render_kw={
            'placeholder': 'Option 1, Option 2, Option 3...',
            'class': 'form-control options-input',
            'maxlength': '500'
        })
    
    correct_option = SelectField('Correct Answer', 
        choices=[('', 'Select correct answer after entering options')],
        validators=[Optional()],  # Changed to optional
        render_kw={
            'class': 'form-select correct-answer',
            'disabled': True
        })
    
    points = IntegerField('Points', 
        validators=[
            DataRequired(message="Points value is required"),
            NumberRange(min=1, max=100, message="Points must be between 1-100")
        ], 
        default=10,
        render_kw={
            'class': 'form-control question-points',
            'min': '1',
            'max': '100'
        })
    
    image = FileField('Question Image (Optional)',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png'], 'Images only (JPEG, PNG)')
        ],
        render_kw={
            'class': 'form-control',
            'accept': 'image/*'
        })

    def validate_options(self, field):
        if self.question_type.data == 'multiple_choice':
            options = [opt.strip() for opt in field.data.split(',') if opt.strip()]
            
            if len(options) < 2:
                raise ValidationError("Multiple choice requires at least 2 options")
                
            if len(options) != len(set(options)):
                raise ValidationError("Options must be unique")
                
            if any(len(opt) > 100 for opt in options):
                raise ValidationError("Each option cannot exceed 100 characters")
    
    def validate_correct_option(self, field):
        if self.question_type.data == 'multiple_choice':
            if not field.data or not field.data.isdigit():
                raise ValidationError("Please select a valid correct option")
                
            options = [opt.strip() for opt in self.options.data.split(',') if opt.strip()]
            option_index = int(field.data)
            
            if option_index < 0 or option_index >= len(options):
                raise ValidationError("Selected correct answer is invalid")
    
    def validate_text(self, field):
        if len(field.data.strip()) < 10:
            raise ValidationError("Question should be at least 10 characters long")
            
        if any(char in field.data for char in ['<', '>', '\\']):
            raise ValidationError("Question contains invalid characters")
    
    def validate_image(self, field):
        if field.data:
            if len(field.data.read()) > 2 * 1024 * 1024:  # 2MB limit
                raise ValidationError("Image must be less than 2MB")
            field.data.seek(0)  # Reset file pointer


class AssignmentForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(message="Title is required"),
        Length(max=200, message="Title cannot exceed 200 characters")
    ], render_kw={
        'placeholder': 'Assignment title...'
    })
    
    description = TextAreaField('Description', validators=[
        DataRequired(message="Description is required"),
        Length(max=5000, message="Description cannot exceed 5000 characters")
    ], render_kw={
        'placeholder': 'Detailed instructions...',
        'rows': 5
    })
    
    input_method = SelectField('Question Input Method', choices=[
        ('manual', 'Manual Entry'),
        ('file', 'Upload PDF'),
        ('bulk', 'Bulk Upload')
    ], default='manual')
    
    questions = TextAreaField('Questions', validators=[
        Optional(),
        Length(max=10000, message="Questions text too long")
    ], render_kw={
        'placeholder': 'Enter questions here...',
        'rows': 8,
        'data-input-method': 'manual'
    })
    
    question_file = FileField('Question File', validators=[
        Optional(),
        FileAllowed(['pdf'], 'Only PDF files are allowed')
    ], render_kw={
        'data-input-method': 'file',
        'accept': '.pdf'
    })
    
    bulk_questions = FileField('Bulk Questions', validators=[
        Optional(),
        FileAllowed(['csv', 'xlsx'], 'Only CSV or Excel files allowed')
    ], render_kw={
        'data-input-method': 'bulk',
        'accept': '.csv,.xlsx'
    })
    
    due_date = CustomDateTimeField('Due Date', 
        validators=[DataRequired(message="Due date is required")],
        render_kw={
            'type': 'datetime-local',
            'min': (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        }
    )
    
    max_score = IntegerField('Maximum Score', validators=[
        DataRequired(message="Maximum score is required"),
        NumberRange(min=1, max=1000, message="Score must be 1-1000")
    ], default=100, render_kw={
        'min': 1,
        'max': 1000
    })
    
    subject_id = SelectField('Subject', 
        coerce=lambda x: int(x) if x else None,
        validators=[DataRequired(message="Please select a subject")],
        choices=[]
    )
    
    classroom_id = SelectField('Classroom', 
        coerce=lambda x: int(x) if x else None,
        validators=[DataRequired(message="Please select a classroom")],
        choices=[]
    )
    
    is_group = BooleanField('Group Assignment', default=False)
    allow_late = BooleanField('Allow Late Submissions', default=False)
    resubmit_allowed = BooleanField('Allow Resubmission', default=False)
    
    # Add the missing is_draft field
    is_draft = BooleanField('Save as Draft', default=False)
    is_published = BooleanField('Save as Draft', default=False)

    # Renamed from is_published to be more clear when used with is_draft
    publish_now = BooleanField('Publish Immediately', default=True)
    
    def validate(self, extra_validators=None):
        # Run standard validators first
        if not super().validate(extra_validators):
            return False
            
        # Custom validation for question input methods
        if not any([
            self.input_method.data == 'manual' and self.questions.data,
            self.input_method.data == 'file' and self.question_file.data,
            self.input_method.data == 'bulk' and self.bulk_questions.data
        ]):
            if self.input_method.data == 'manual':
                self.questions.errors.append('Please enter questions')
            elif self.input_method.data == 'file':
                self.question_file.errors.append('Please upload a file')
            else:
                self.bulk_questions.errors.append('Please upload a file')
            return False
            
        # Additional validation for subject and classroom
        try:
            if self.subject_id.data is None:
                self.subject_id.errors.append('Please select a subject')
                return False
            if self.classroom_id.data is None:
                self.classroom_id.errors.append('Please select a classroom')
                return False
        except ValueError:
            self.subject_id.errors.append('Invalid subject selection')
            self.classroom_id.errors.append('Invalid classroom selection')
            return False
            
        return True


class SubmissionForm(FlaskForm):
    content = TextAreaField('Your Answer', validators=[
        Optional(),
        Length(max=10000, message="Answer cannot exceed 10,000 characters")
    ], render_kw={
        'placeholder': 'Type your answer here...',
        'rows': 8
    })
    
    file = FileField('Attachment', validators=[
        Optional(),
        FileAllowed(
            ['pdf', 'docx', 'txt', 'zip', 'pptx', 'png', 'jpg', 'jpeg'],
            'Allowed types: PDF, Word, Text, ZIP, PowerPoint, PNG, JPG'
        )
    ], render_kw={
        'accept': '.pdf,.docx,.txt,.zip,.pptx,.png,.jpg,.jpeg'
    })
    
    confirm = BooleanField('I confirm this is my own work', validators=[
        DataRequired(message="You must confirm this is your own work")
    ])
    
    def validate(self, extra_validators=None):
        if not super().validate():
            return False
            
        if not self.content.data and not self.file.data:
            self.content.errors.append('Please provide either text or a file')
            return False
            
        return True