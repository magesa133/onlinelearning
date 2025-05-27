import base64
import os
import io
import random
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import uuid
from io import StringIO, BytesIO
from io import BytesIO
import pytz as pytz_timezone
from pytz.exceptions import UnknownTimeZoneError
import humanize
from flask import render_template, session as flask_session, send_file, make_response
from flask_wtf import FlaskForm
from flask_wtf.csrf import generate_csrf
from wtforms import RadioField
from wtforms.validators import DataRequired, ValidationError
from zoneinfo import ZoneInfo  # Python 3.9+ (preferred) or use pytz as fallback
from forms import AssignmentForm, SubmissionForm, QuizEditForm  # Import the forms
from forms import QuizCreateForm, QuestionForm, MessageForm # Ensure this import is added at the top of the file
import pandas as pd
from markdown import markdown
from bleach import clean  # Add this import at the top of the file if not already present
from sqlalchemy.exc import SQLAlchemyError
import logging
import traceback
from werkzeug.exceptions import HTTPException
import bisect
import json
from flask import abort, flash, jsonify, redirect, render_template, request, \
                   send_from_directory, url_for, current_app
import traceback
from flask_login import current_user, login_required, login_user, logout_user
import face_recognition  # Add this import for face recognition functionality
from PIL import Image
from sqlalchemy import and_, func, exists, case
from sqlalchemy.orm import joinedload, load_only
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename, safe_join

from app import app, db
from models import (Activity, Assignment, Attendance, Classroom, Department,
                    Grade, Resource, OnlineSession, Question, Quiz, Student,
                    Submission, Subject, Teacher, User, Enrollment, QuizAttempt, QuizAnswer, Message, ClassAnnouncement, ClassroomActivity, ResourceComment, Notification, NotificationSettings)
import csv
import re  # Add this import for regular expressions
from reportlab.pdfgen import canvas  # For PDF export
# routes.py
from app import socketio
from apscheduler.schedulers.background import BackgroundScheduler



@app.template_filter('humanize')
def humanize_time(dt):
    """Convert datetime to human-readable relative time using humanize package."""
    return humanize.naturaltime(datetime.utcnow() - dt)

@app.template_filter('score_color')
def score_color(score, max_score=None):
    """Determine badge color based on score"""
    if score is None:
        return 'secondary'
    if max_score:
        percentage = (score/max_score)*100
    else:
        percentage = score
    return 'success' if percentage >= 70 else 'warning' if percentage >= 50 else 'danger'

@app.template_filter('format_time')
def format_time(seconds):
    """Format seconds into MM:SS"""
    if not seconds:
        return "0:00"
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


@app.template_filter('format_relative_time')
def format_relative_time(dt):
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 365:
        return f"{diff.days//365}y ago"
    elif diff.days > 30:
        return f"{diff.days//30}mo ago"
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds//3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds//60}m ago"
    else:
        return "just now"

@app.template_filter('to_letter')
def to_letter_grade(score):
    """Convert numerical score to letter grade"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'
from zoneinfo import ZoneInfo
from pytz import timezone as pytz_timezone, utc
local_timezone = pytz_timezone('Africa/Dar_es_Salaam')
import pytz  # Add this import

from zoneinfo import ZoneInfo
# Timezone setup
APP_TIMEZONE = 'Africa/Dar_es_Salaam'  # Using Nairobi as it's the same as Dar es Salaam time
local_tz = ZoneInfo(APP_TIMEZONE)


# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Define allowed extensions by resource type
ALLOWED_EXTENSIONS = {
    'document': {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'rtf', 'odt', 'xls', 'xlsx'},
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp'},
    'video': {'mp4', 'mov', 'avi', 'mkv', 'webm'},
    'audio': {'mp3', 'wav', 'ogg', 'm4a'},
    'archive': {'zip', 'rar', '7z', 'tar', 'gz'}
}

MIME_TYPES = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'ppt': 'application/vnd.ms-powerpoint',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'zip': 'application/zip',
    'rar': 'application/vnd.rar',
    '7z': 'application/x-7z-compressed',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'avi': 'video/x-msvideo',
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav'
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
app.config['MIME_TYPES'] = MIME_TYPES

def allowed_file(filename, resource_type):
    """Check if the file extension is allowed for the resource type"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(resource_type, set())

def get_resource_folder(resource_type):
    """Get the upload directory path for a resource type, creating if needed"""
    resource_dir = os.path.join(
        app.config['UPLOAD_FOLDER'],
        f"{resource_type}s"
    )
    os.makedirs(resource_dir, exist_ok=True)
    return resource_dir

def get_mime_type(filename):
    """Get MIME type based on file extension"""
    ext = filename.split('.')[-1].lower()
    return app.config['MIME_TYPES'].get(ext, 'application/octet-stream')


@app.template_filter('time_ago')
def time_ago_filter(dt):
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()
    
    intervals = (
        ('year', 31536000),
        ('month', 2592000),
        ('week', 604800),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1)
    )
    
    for name, count in intervals:
        value = seconds // count
        if value:
            if value == 1:
                return f"{int(value)} {name} ago"
            return f"{int(value)} {name}s ago"
    return "just now"
# ---------- AUTHENTICATION ROUTES ----------

@app.route('/')
def index():
    """Home page route."""
    current_year = datetime.now().year
    return render_template('index.html', current_year=current_year)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if request.method == 'POST':
        username = request.form.get('username').strip().capitalize()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip()
        image_data = request.form.get('image_data')  # Base64-encoded image data

        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))

        # Handle face image
        image_filename = None
        if image_data:
            try:
                # Add your code here
                pass
            except Exception as e:
                current_app.logger.error(f"An error occurred: {str(e)}", exc_info=True)
                flash('An error occurred while processing your request.', 'danger')
                _, encoded = image_data.split(",", 1)
                face_image = face_recognition.load_image_file(BytesIO(base64.b64decode(encoded)))
                image_filename = secure_filename(f"{username}_face.jpg")
                image_path = os.path.join(UPLOAD_FOLDER, image_filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                Image.fromarray(face_image).save(image_path)
            except Exception as e:
                flash(f"Error processing face image: {e}", 'danger')
                return redirect(url_for('register'))

        # Create user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role='student',
            face_image=image_filename
        )

        try:
            # Add your code here
            pass
        except Exception as e:
            current_app.logger.error(f"An error occurred: {str(e)}")
            flash("An error occurred while processing your request.", "danger")
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Registration successful!', 'success')
            return redirect(url_for('student_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving user to database: {e}", 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route with face recognition option."""
    if request.method == 'POST':
        # Standard username/password login
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        
        if not all([identifier, password]):
            flash('Both fields are required.', 'danger')
            return redirect(url_for('login'))

        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for(f'{user.role}_dashboard'))
        
        flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout route."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ---------- DASHBOARD ROUTES ----------

def get_recent_submissions(student, limit=5):
    """Retrieve the most recent submissions for a student."""
    try:
        return Submission.query.filter_by(student_id=student.id)\
            .order_by(Submission.submitted_at.desc())\
            .limit(limit).all()
    except Exception as e:
        current_app.logger.error(f"Error fetching recent submissions: {str(e)}", exc_info=True)
        return []


def get_grades_summary(student):
    """Summarize grades for a student."""
    try:
        grades = Grade.query.filter_by(student_id=student.id).all()
        return {
            'average': sum(g.score for g in grades) / len(grades) if grades else 0,
            'total': len(grades),
            'subjects': {g.subject_id: g.score for g in grades}
        }
    except Exception as e:
        current_app.logger.error(f"Error fetching grades summary: {str(e)}")
        return {'average': 0, 'total': 0, 'subjects': {}}

from enum import Enum, unique
from datetime import datetime, timedelta
from flask import render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

@unique
class QuizStatus(Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'
    DELETED = 'deleted'


@app.route('/student_dashboard')
@login_required
def student_dashboard():
    """Student dashboard with robust timezone handling and validation"""
    try:
        # Authentication and authorization
        if current_user.role != 'student' or not current_user.student_profile:
            abort(403)

        # Timezone setup
        student = current_user.student_profile
        user_tz = ZoneInfo(current_user.timezone) if current_user.timezone else ZoneInfo(APP_TIMEZONE)
        current_utc = datetime.now(timezone.utc)
        now_local = current_utc.astimezone(user_tz)

        # Get enrolled classrooms
        enrollments = Enrollment.query.filter_by(student_id=student.id).options(
            joinedload(Enrollment.classroom).joinedload(Classroom.subject)
        ).all()
        class_ids = [e.classroom.id for e in enrollments] if enrollments else []

        # --- Quizzes ---
        quizzes = Quiz.query.filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == QuizStatus.PUBLISHED.value
        ).options(
            joinedload(Quiz.classroom),
            joinedload(Quiz.teacher)
        ).all() if class_ids else []

        upcoming_quizzes = []
        for quiz in quizzes:
            if quiz.due_date:
                due_date_utc = make_timezone_aware(quiz.due_date)
                if due_date_utc > current_utc:
                    upcoming_quizzes.append({
                        'quiz': quiz,
                        'due_date_local': localize_time(due_date_utc, current_user.timezone),
                        'time_remaining': due_date_utc - current_utc,
                        'status': quiz.status
                    })
        upcoming_quizzes.sort(key=lambda x: x['due_date_local'])

        # --- Assignments ---
        assignments = Assignment.query.filter(
            Assignment.class_id.in_(class_ids),
            Assignment.is_published == True
        ).options(
            joinedload(Assignment.classroom),
            joinedload(Assignment.subject)
        ).all()

        assignment_data = []
        for assignment in assignments:
            due_date_utc = make_timezone_aware(assignment.due_date)
            assignment_data.append({
                'assignment': assignment,
                'due_date_local': localize_time(due_date_utc, current_user.timezone),
                'is_past_due': due_date_utc < current_utc
            })

        # --- Submissions ---
        recent_submissions = []
        for submission in get_recent_submissions(student):
            try:
                # Create regular attributes instead of trying to set properties
                if submission.submitted_at:
                    submission._submitted_at_aware = make_timezone_aware(submission.submitted_at)
                    submission._submitted_at_local = localize_time(submission._submitted_at_aware, current_user.timezone)
                if submission.last_modified:
                    submission._last_modified_aware = make_timezone_aware(submission.last_modified)
                    submission._last_modified_local = localize_time(submission._last_modified_aware, current_user.timezone)
                recent_submissions.append(submission)
            except Exception as e:
                current_app.logger.error(f"Error processing submission {submission.id}: {str(e)}")

        # --- Online Sessions ---
        active_sessions = []
        for session in OnlineSession.query.filter(OnlineSession.class_id.in_(class_ids)).all():
            try:
                # Ensure timezone awareness
                session.start_time = make_timezone_aware(session.start_time)
                session.end_time = make_timezone_aware(session.end_time)
                
                # Get status and other properties (don't try to set the read-only properties)
                session.status = session.get_status(current_utc)
                session.class_name = session.classroom.class_name if session.classroom else "Unknown Class"
                
                active_sessions.append(session)
            except Exception as e:
                current_app.logger.error(f"Error processing session {session.id}: {str(e)}")
                continue

        # --- Quiz Attempts ---
        recent_attempts = QuizAttempt.query.filter(
            QuizAttempt.student_id == student.id,
            QuizAttempt.completed_at.isnot(None)
        ).options(
            joinedload(QuizAttempt.quiz).joinedload(Quiz.subject)
        ).order_by(QuizAttempt.completed_at.desc()).limit(2).all()

        for attempt in recent_attempts:
            if attempt.completed_at:
                attempt.completed_at_aware = make_timezone_aware(attempt.completed_at)
                attempt.completed_at_local = localize_time(attempt.completed_at_aware, current_user.timezone)

        return render_template('student_dashboard.html',
            student=student,
            quizzes=upcoming_quizzes,
            assignments=assignment_data,
            now=now_local,
            user_timezone=user_tz,
            grades_summary=get_grades_summary(student),
            recent_submissions=recent_submissions,
            recent_quiz_attempts=recent_attempts,
            QuizStatus=QuizStatus,
            humanize=humanize,
            enrollments=enrollments,
            active_sessions=active_sessions,
            
            debug_info={
                'student': f"{current_user.username} (ID: {current_user.id})",
                'current_time_utc': current_utc.strftime('%Y-%m-%d %H:%M %Z'),
                'current_time_local': now_local.strftime('%Y-%m-%d %H:%M %Z'),
                'enrolled_classrooms': [e.classroom.class_name for e in enrollments],
                'time_zone': str(user_tz)
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error loading student dashboard: {str(e)}", exc_info=True)
        return render_template('error.html',
            error="We encountered an error loading your dashboard",
            error_details=str(e) if current_app.debug else None,
            debug=current_app.debug
        ), 500
    

# Helper functions with proper timezone support

def make_timezone_aware(dt, tz=timezone.utc):
    """Ensure a datetime object is timezone-aware"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)
    
def localize_time(dt, user_timezone):
    """Convert a datetime to user's local timezone"""
    if dt is None:
        return None
    if not user_timezone:
        return dt
    return dt.astimezone(ZoneInfo(user_timezone))

def get_student_quizzes(student, class_ids, now_utc):
    """Retrieve and organize quizzes by status with timezone awareness"""
    try:
        quizzes = Quiz.query.filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == QuizStatus.PUBLISHED.value
        ).options(
            joinedload(Quiz.subject),
            joinedload(Quiz.classroom),
            joinedload(Quiz.teacher)
        ).order_by(Quiz.due_date.asc()).all()

        attempts = {a.quiz_id: a for a in student.quiz_attempts}
        
        organized = {
            'upcoming': [],
            'past': [],
            'attempted': []
        }
        
        for quiz in quizzes:
            if not quiz.due_date:
                continue
                
            # Ensure due_date is timezone-aware UTC
            due_date_utc = quiz.due_date if quiz.due_date.tzinfo else pytz.utc.localize(quiz.due_date)
            
            if quiz.id in attempts:
                organized['attempted'].append(quiz)
            elif due_date_utc > now_utc:
                organized['upcoming'].append(quiz)
            else:
                organized['past'].append(quiz)
                
        return organized
    except Exception as e:
        current_app.logger.error(f"Error fetching quizzes: {str(e)}")
        return {'upcoming': [], 'past': [], 'attempted': []}

def get_student_assignments(student, class_ids, now_utc):
    """Retrieve and organize assignments by status with UTC comparison"""
    try:
        assignments = Assignment.query.filter(
            Assignment.class_id.in_(class_ids),
            Assignment.is_published == True
        ).options(
            joinedload(Assignment.subject),
            joinedload(Assignment.classroom),
            joinedload(Assignment.author)
        ).order_by(Assignment.due_date.asc()).all()

        submitted_ids = {s.assignment_id for s in student.submissions}
        
        organized = {
            'upcoming': [],
            'pending': [],
            'submitted': []
        }
        
        for assignment in assignments:
            if not assignment.due_date:
                continue
                
            # Ensure due_date is timezone-aware UTC
            due_date_utc = assignment.due_date if assignment.due_date.tzinfo else pytz.utc.localize(assignment.due_date)
            
            if assignment.id in submitted_ids:
                organized['submitted'].append(assignment)
            elif due_date_utc > now_utc:
                organized['upcoming'].append(assignment)
            else:
                organized['pending'].append(assignment)
                
        return organized
    except Exception as e:
        current_app.logger.error(f"Error fetching assignments: {str(e)}")
        return {'upcoming': [], 'pending': [], 'submitted': []}

def get_student_sessions(class_ids, now_utc):
    """Retrieve online sessions grouped by status with UTC comparison"""
    try:
        all_sessions = OnlineSession.query.filter(
            OnlineSession.class_id.in_(class_ids)
        ).options(
            joinedload(OnlineSession.classroom)
        ).order_by(OnlineSession.start_time.asc()).all()
        
        active_sessions = []
        past_sessions = []
        
        for session in all_sessions:
            # Ensure session times are timezone-aware UTC
            start_utc = session.start_time if session.start_time.tzinfo else pytz.utc.localize(session.start_time)
            end_utc = session.end_time if session.end_time.tzinfo else pytz.utc.localize(session.end_time)
            
            # Determine if the session is active or upcoming
            if start_utc <= now_utc <= end_utc:
                active_sessions.append(session)
            elif now_utc < start_utc:  # Upcoming sessions
                active_sessions.append(session)
            else:
                past_sessions.append(session)
                
        return {
            'active': active_sessions,
            'past': past_sessions[:5]  # Limit past sessions to 5 most recent
        }
    except Exception as e:
        current_app.logger.error(f"Error fetching sessions: {str(e)}")
        return {'active': [], 'past': []}


def format_datetime(dt, format_str='%B %d, %Y at %H:%M', tz='Africa/Dar_es_Salaam'):
    """Safe datetime formatting with timezone conversion"""
    if not dt:
        return "Not set"
        
    try:
        # Convert to timezone-aware UTC if naive
        dt_utc = dt if dt.tzinfo else pytz.utc.localize(dt)
        # Convert to target timezone
        target_tz = pytz.timezone(tz)
        return dt_utc.astimezone(target_tz).strftime(format_str)
    except Exception as e:
        current_app.logger.error(f"Error formatting datetime: {str(e)}")
        return "Invalid date"


@app.context_processor
def inject_unread_count():
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        return {'unread_count': unread_count}
    return {'unread_count': 0}

@app.route('/debug/quizzes/<int:student_id>')
def debug_quizzes(student_id):
    """Debug endpoint to check quiz visibility"""
    student = StudentProfile.query.get_or_404(student_id)
    class_ids = [e.class_id for e in student.enrollments]
    now=local_timezone.localize(datetime.now())
    
    quizzes = Quiz.query.filter(
        Quiz.classroom_id.in_(class_ids),
        Quiz.status == 'published',
        Quiz.is_deleted == False,
        Quiz.due_date > now
    ).all()
    
    return jsonify({
        'student': student_id,
        'classrooms': class_ids,
        'quizzes': [{
            'id': q.id,
            'title': q.title,
            'classroom': q.classroom_id,
            'due_date': q.due_date.isoformat(),
            'status': q.status
        } for q in quizzes]
    })


# ------- Grades Area for all Quiz and Assignemt for teacher purpose ------

class AssessmentType(Enum):
    ASSIGNMENT = 'assignment'
    QUIZ = 'quiz'

def calculate_grade(score, max_score):
    """Calculate letter grade based on percentage"""
    if score is None or max_score == 0:
        return None
    percentage = (score / max_score) * 100
    if percentage >= 90: return 'A'
    if percentage >= 80: return 'B'
    if percentage >= 70: return 'C'
    if percentage >= 60: return 'D'
    return 'F'

def get_current_term_range():
    """Determine current academic term dates"""
    today = datetime.now()
    if today.month >= 8:  # Fall term (Aug-Jan)
        return (datetime(today.year, 8, 1), datetime(today.year + 1, 1, 1))
    else:  # Spring term (Jan-Aug)
        return (datetime(today.year, 1, 1), datetime(today.year, 8, 1))

def calculate_assessment_stats(assessment, assessment_type, classroom):
    """Calculate statistics for an assessment"""
    try:
        # Get submissions based on assessment type
        if assessment_type == AssessmentType.ASSIGNMENT:
            submissions = assessment.submissions
            max_score = assessment.max_score
        else:  # Quiz
            submissions = []
            for attempt in assessment.attempts:
                submissions.append({
                    'id': attempt.id,
                    'student': attempt.student,
                    'score': attempt.score,
                    'submitted_at': attempt.completed_at,
                    'graded_at': attempt.completed_at
                })
            max_score = assessment.total_points

        # Calculate basic stats
        total_submissions = len(submissions)
        graded_submissions = sum(1 for s in submissions if s and s.get('score') is not None)

        # Calculate average score
        average = None
        if graded_submissions > 0:
            valid_scores = [s.get('score') for s in submissions if s and s.get('score') is not None]
            average = sum(valid_scores) / len(valid_scores) if valid_scores else None

        # Calculate grade distribution
        distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for submission in submissions:
            if submission and submission.get('score') is not None:
                grade = calculate_grade(submission.get('score'), max_score)
                if grade in distribution:
                    distribution[grade] += 1

        return {
            'id': assessment.id,
            'title': assessment.title,
            'type': assessment_type.value,
            'class_name': classroom.class_name,
            'class_id': classroom.id,
            'due_date': assessment.due_date,
            'max_score': max_score,
            'submissions': submissions,
            'total_submissions': total_submissions,
            'graded_submissions': graded_submissions,
            'completion': (graded_submissions / total_submissions * 100) if total_submissions else 0,
            'average': average,
            'distribution': distribution,
            'created_at': assessment.created_at
        }
    except Exception as e:
        app.logger.error(f"Error calculating stats for {assessment.id}: {str(e)}\n{traceback.format_exc()}")
        raise


@app.route('/gradebook')
@login_required
def view_gradebook():
    """Display comprehensive gradebook for teacher"""
    if current_user.role != 'teacher':
        flash('Only teachers can access the gradebook', 'danger')
        return redirect(url_for('teacher_dashboard'))

    try:
        # Get all classes taught by this teacher with counts
        classes = (Classroom.query
                  .filter_by(teacher_id=current_user.id)
                  .options(
                      joinedload(Classroom.assignments),
                      joinedload(Classroom.quizzes))
                  .all())

        # Log diagnostic information
        app.logger.info(f"Found {len(classes)} classes for teacher {current_user.id}")
        for i, class_obj in enumerate(classes):
            app.logger.info(f"Class {i+1}: {class_obj.class_name} - "
                          f"Assignments: {len(class_obj.assignments)}, "
                          f"Quizzes: {len(class_obj.quizzes)}")

        assignments = []
        quizzes = []

        for class_obj in classes:
            # Process assignments
            for assignment in class_obj.assignments:
                try:
                    stats = calculate_assessment_stats(assignment, AssessmentType.ASSIGNMENT, class_obj)
                    assignments.append(stats)
                except Exception as e:
                    app.logger.error(f"Error processing assignment {assignment.id}: {str(e)}")
                    continue

            # Process quizzes
            for quiz in class_obj.quizzes:
                if quiz.is_published:  # Only include published quizzes
                    try:
                        stats = calculate_assessment_stats(quiz, AssessmentType.QUIZ, class_obj)
                        quizzes.append(stats)
                    except Exception as e:
                        app.logger.error(f"Error processing quiz {quiz.id}: {str(e)}")
                        continue

        # Calculate overall metrics
        total_assignments = len(assignments)
        total_quizzes = len(quizzes)
        total_graded = sum(1 for a in assignments + quizzes if a['completion'] == 100)
        total_assessments = total_assignments + total_quizzes

        return render_template('teacher/grades/gradebook.html',
                            classes=classes,
                            assignments=assignments,
                            quizzes=quizzes,
                            overall_completion=(total_graded / total_assessments * 100) if total_assessments else 0,
                            total_assignments=total_assignments,
                            total_quizzes=total_quizzes)

    except Exception as e:
        app.logger.error(f"Full error traceback: {traceback.format_exc()}")
        current_app.logger.error(f"Current user: {current_user.id}, Role: {current_user.role}")
        current_app.logger.error(f"Classes found: {len(classes)}")
        if classes:
            current_app.logger.error(f"First class assignments: {len(classes[0].assignments)}")
            current_app.logger.error(f"First class quizzes: {len(classes[0].quizzes)}")
        flash(f'Failed to load gradebook data. Administrator has been notified.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    


@app.route('/gradebook/export')
@login_required
def export_grades():
    """Export gradebook data in various formats"""
    if current_user.role != 'teacher':
        abort(403)
    
    try:
        # Get export parameters from request
        export_format = request.args.get('format', 'csv')
        content_type = request.args.get('content_type', 'all')
        date_range = request.args.get('date_range', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        selected_fields = request.args.getlist('fields')
        
        # Validate date range if custom is selected
        if date_range == 'custom' and (not start_date or not end_date):
            flash('Please specify both start and end dates for custom range', 'warning')
            return redirect(url_for('view_gradebook'))
        
        # Query data based on filters
        query = Classroom.query.filter_by(teacher_id=current_user.id)
        
        # Apply date filters if specified
        if date_range == 'current':
            # Current term (assuming academic year starts in September)
            today = datetime.now()
            if today.month >= 9:  # September or later
                term_start = datetime(today.year, 9, 1)
            else:  # January-August
                term_start = datetime(today.year - 1, 9, 1)
            query = query.filter(Assignment.due_date >= term_start)
        elif date_range == 'last_month':
            last_month = datetime.now() - timedelta(days=30)
            query = query.filter(Assignment.due_date >= last_month)
        elif date_range == 'custom' and start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Assignment.due_date.between(start_date, end_date))
        
        # Eager load related data
        classes = query.options(
            joinedload(Classroom.assignments)
            .joinedload(Assignment.submissions)
            .joinedload(Submission.student)
            .joinedload(Student.user),
            joinedload(Classroom.quizzes)
            .joinedload(Quiz.attempts)
            .joinedload(QuizAttempt.student)
            .joinedload(Student.user)
        ).all()
        
        # Prepare export data based on selected fields
        export_data = []
        field_mapping = {
            'student': ('Student', lambda x: f"{x.student.user.last_name}, {x.student.user.first_name}"),
            'student_id': ('Student ID', lambda x: x.student.student_id),
            'email': ('Email', lambda x: x.student.user.email),
            'class': ('Class', lambda x: x.classroom.name),
            'type': ('Type', lambda x: x.assignment.type if hasattr(x, 'assignment') else 'quiz'),
            'title': ('Title', lambda x: x.assignment.title if hasattr(x, 'assignment') else x.quiz.title),
            'due_date': ('Due Date', lambda x: x.assignment.due_date.strftime('%Y-%m-%d') if hasattr(x, 'assignment') 
                         else (x.quiz.due_date.strftime('%Y-%m-%d') if x.quiz.due_date else '')),
            'score': ('Score', lambda x: x.score),
            'max_score': ('Max Score', lambda x: x.assignment.max_score if hasattr(x, 'assignment') else x.quiz.total_points),
            'grade': ('Grade', lambda x: calculate_grade(x.score, x.assignment.max_score) if hasattr(x, 'assignment') 
                     else calculate_grade(x.score, x.quiz.total_points)),
            'submitted_at': ('Submitted At', lambda x: x.submitted_at.strftime('%Y-%m-%d %H:%M') if hasattr(x, 'submitted_at') 
                            else (x.completed_at.strftime('%Y-%m-%d %H:%M') if x.completed_at else '')),
            'status': ('Status', lambda x: 'Graded' if x.score is not None else 'Pending' if hasattr(x, 'submitted_at') 
                      else 'Completed' if x.completed_at else 'In Progress')
        }
        
        # Filter fields if specific fields were selected
        if selected_fields:
            field_mapping = {k: v for k, v in field_mapping.items() if k in selected_fields}
        
        # Process data based on content type
        for class_obj in classes:
            # Process assignments if requested
            if content_type in ['all', 'assignments']:
                for assignment in class_obj.assignments:
                    for submission in assignment.submissions:
                        item = {
                            'classroom': class_obj,
                            'assignment': assignment,
                            'submission': submission,
                            'student': submission.student
                        }
                        export_data.append({
                            field: getter(item) for field, (_, getter) in field_mapping.items()
                        })
            
            # Process quizzes if requested
            if content_type in ['all', 'quizzes']:
                for quiz in [q for q in class_obj.quizzes if q.is_published]:
                    for attempt in quiz.attempts:
                        item = {
                            'classroom': class_obj,
                            'quiz': quiz,
                            'attempt': attempt,
                            'student': attempt.student
                        }
                        export_data.append({
                            field: getter(item) for field, (_, getter) in field_mapping.items()
                        })
        
        if not export_data:
            flash('No data available for export with current filters', 'warning')
            return redirect(url_for('view_gradebook'))
        
        # Generate export based on format
        if export_format == 'csv':
            return _export_csv(export_data, field_mapping)
        elif export_format == 'json':
            return _export_json(export_data)
        elif export_format == 'pdf':
            return _export_pdf(export_data, field_mapping)
        else:
            flash('Invalid export format', 'danger')
            return redirect(url_for('view_gradebook'))

    except Exception as e:
        app.logger.error(f"Export error: {str(e)}", exc_info=True)
        flash('Failed to generate export', 'danger')
        return redirect(url_for('view_gradebook'))

def _export_csv(data, field_mapping):
    """Generate CSV export"""
    output = StringIO()
    
    # Write header
    writer = csv.DictWriter(output, fieldnames=field_mapping.keys())
    writer.writerow({field: header for field, (header, _) in field_mapping.items()})
    
    # Write data
    writer.writerows(data)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=gradebook_export.csv'
    return response

def _export_json(data):
    """Generate JSON export"""
    response = make_response(json.dumps(data, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=gradebook_export.json'
    return response

def _export_pdf(data, field_mapping):
    """Generate PDF export"""
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    
    # PDF Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "Gradebook Export Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 780, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    p.drawString(100, 760, f"Total Records: {len(data)}")
    
    # PDF Content - Column headers
    p.setFont("Helvetica-Bold", 10)
    y_position = 730
    col_width = 500 / len(field_mapping)  # Distribute columns across page
    
    for i, (header, _) in enumerate(field_mapping.values()):
        p.drawString(100 + i * col_width, y_position, header)
    
    # Data rows
    p.setFont("Helvetica", 8)
    y_position -= 20
    
    for row in data:
        if y_position < 50:  # New page if we're at the bottom
            p.showPage()
            y_position = 800
            p.setFont("Helvetica-Bold", 10)
            for i, (header, _) in enumerate(field_mapping.values()):
                p.drawString(100 + i * col_width, y_position, header)
            y_position -= 20
            p.setFont("Helvetica", 8)
        
        for i, (field, _) in enumerate(field_mapping.items()):
            value = str(row.get(field, ''))[:20]  # Truncate long values
            p.drawString(100 + i * col_width, y_position, value)
        
        y_position -= 15
    
    p.save()
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=gradebook_export.pdf'
    return response


# ---------- STUDENT RESOURCES ROUTES ----------
# Resources Section

# ---------- MISCELLANEOUS ROUTES ----------

@app.route('/grades')
@login_required
def grades():
    """View grades with all necessary context."""
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('teacher_dashboard'))

    # Get all assignments with their submissions
    assignments = Assignment.query.filter_by(author_id=current_user.id).options(
        joinedload(Assignment.submissions)
    ).all()

    # Prepare gradebook data
    gradebook = []
    for assignment in assignments:
        graded_count = len([s for s in assignment.submissions if s.score is not None])
        gradebook.append({
            'assignment': assignment,
            'graded_count': graded_count,
            'total_count': len(assignment.submissions),
            'completion': (graded_count / len(assignment.submissions)) * 100 if assignment.submissions else 0
        })

    return render_template('teacher/assignments/grade.html',
                         gradebook=gradebook,
                         now=datetime.now(timezone.utc))

# ---------- STUDY RESOURCES ROUTES ----------
from datetime import datetime, timedelta
from sqlalchemy import or_

@app.route('/study-resources')
@login_required
def study_resources():
    try:
        if current_user.role != 'student' or not current_user.student_profile:
            abort(403)

        student = current_user.student_profile
        enrolled_class_ids = [enrollment.class_id for enrollment in student.enrollments]
        
        # Base query
        query = Resource.query.filter(
            Resource.classroom_id.in_(enrolled_class_ids),
            Resource.is_approved == True
        ).options(
            joinedload(Resource.subject),
            joinedload(Resource.classroom),
            joinedload(Resource.teacher)
        )
        
        # Apply filters
        subject_filter = request.args.get('subject')
        if subject_filter and subject_filter.isdigit():
            query = query.filter(Resource.subject_id == int(subject_filter))
        
        type_filter = request.args.get('type')
        if type_filter:
            if type_filter == 'video':
                query = query.filter(Resource.resource_type.in_(['mp4', 'mov', 'avi']))
            else:
                query = query.filter(Resource.resource_type.startswith(type_filter))
        
        date_filter = request.args.get('date')
        if date_filter:
            today = datetime.utcnow()
            if date_filter == 'week':
                query = query.filter(Resource.upload_date >= today - timedelta(days=7))
            elif date_filter == 'month':
                query = query.filter(Resource.upload_date >= today - timedelta(days=30))
            elif date_filter == 'year':
                query = query.filter(Resource.upload_date >= today - timedelta(days=365))
        
        # Get all subjects for filter dropdown
        subjects = Subject.query.join(Classroom).join(Enrollment).filter(
            Enrollment.student_id == student.id
        ).distinct().all()
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        pagination = query.order_by(Resource.upload_date.desc()).paginate(
            page=page, 
            per_page=10,
            error_out=False
        )
        
        return render_template('student/resources/list.html',
                            resources=pagination.items,
                            subjects=subjects,
                            pagination=pagination,
                            current_user=current_user)

    except Exception as e:
        current_app.logger.error(f"Error loading resources: {str(e)}")
        return render_template('error.html',
            error="We couldn't load the resources",
            error_details=str(e) if current_app.debug else None
        ), 500

@app.route('/study-resources/<int:resource_id>')
@login_required
def study_resource_detail(resource_id):
    try:
        if current_user.role != 'student' or not current_user.student_profile:
            abort(403)

        student = current_user.student_profile
        resource = Resource.query.options(
            joinedload(Resource.subject),
            joinedload(Resource.classroom),
            joinedload(Resource.teacher)  # Just load the User directly
        ).get_or_404(resource_id)

            # Get related resources (example - same subject and type)
        related_resources = Resource.query.filter(
            Resource.subject_id == resource.subject_id,
            Resource.resource_type == resource.resource_type,
            Resource.id != resource.id
        ).order_by(func.random()).limit(3).all()

        enrollment = Enrollment.query.filter_by(
            student_id=student.id,
            class_id=resource.classroom_id
        ).first()
        if not enrollment:
            abort(403)

        resource.views_count += 1
        db.session.commit()

        return render_template('student/resources/detail.html',
                            resource=resource,
                            current_user=current_user,
                            related_resources=related_resources)

    except Exception as e:
        current_app.logger.error(f"Error loading resource {resource_id}: {str(e)}")
        return render_template('error.html',
            error="We couldn't load this resource",
            error_details=str(e) if current_app.debug else None
        ), 500

@app.route('/download-resource/<int:resource_id>')
@login_required
def student_download_resource(resource_id):
    """Handle secure resource downloads with authorization checks"""
    try:
        # Verify user is a student
        if current_user.role != 'student' or not current_user.student_profile:
            current_app.logger.warning(f"Unauthorized download attempt by user {current_user.id}")
            abort(403)

        student = current_user.student_profile

        # Get the resource with minimal query
        resource = Resource.query.options(
            joinedload(Resource.classroom)
        ).get_or_404(resource_id)

        # Verify student enrollment in the class
        enrollment = Enrollment.query.filter_by(
            student_id=student.id,
            class_id=resource.classroom_id
        ).first()
        if not enrollment:
            current_app.logger.warning(
                f"Student {student.id} attempted to download unauthorized resource {resource_id}"
            )
            abort(403)

        # Build secure file path
        resources_dir = current_app.config['RESOURCES_UPLOAD_FOLDER']
        file_path = safe_join(resources_dir, resource.file_path)
        
        if not os.path.exists(file_path):
            current_app.logger.error(f"Resource file not found: {file_path}")
            abort(404)

        # Update download count
        resource.download_count += 1
        db.session.commit()

        # Log the download
        current_app.logger.info(
            f"Resource {resource_id} downloaded by student {student.id}"
        )

        # Send file with original filename
        return send_from_directory(
            directory=resources_dir,
            path=resource.file_path,
            as_attachment=True,
            download_name=resource.file_name
        )

    except Exception as e:
        current_app.logger.error(
            f"Error downloading resource {resource_id}: {str(e)}",
            exc_info=True
        )
        return render_template('error.html',
            error="We couldn't download this resource",
            error_details=str(e) if current_app.debug else None
        ), 500
    
@app.route('/student/resources/<int:resource_id>/download')
@login_required
def students_download_resource(resource_id):
    """Download a resource file"""
    try:
        if current_user.role != 'student':
            abort(403)

        student = current_user.student_profile
        resource = Resource.query.get_or_404(resource_id)

        # Verify access
        if resource.classroom_id not in [e.class_id for e in student.enrollments]:
            abort(403)

        # Track download
        resource.download_count = Resource.download_count + 1
        db.session.commit()

        return send_from_directory(
            os.path.dirname(resource.file_path),
            os.path.basename(resource.file_path),
            as_attachment=True,
            download_name=resource.file_name
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading resource {resource_id}: {str(e)}")
        flash("Error downloading file", "danger")
        return redirect(url_for('study_resource_detail', resource_id=resource_id))

@app.route('/resources/<int:resource_id>/comment', methods=['POST'])
@login_required
def add_resource_comment(resource_id):
    try:
        if current_user.role != 'student':
            flash('Only students can comment on resources', 'error')
            return redirect(url_for('study_resource_detail', resource_id=resource_id))

        # Get the comment content from form
        comment_content = request.form.get('comment')
        if not comment_content or len(comment_content.strip()) == 0:
            flash('Comment cannot be empty', 'error')
            return redirect(url_for('study_resource_detail', resource_id=resource_id))

        # Verify the resource exists and student has access
        resource = Resource.query.get_or_404(resource_id)
        student = current_user.student_profile
        
        # Check if student is enrolled in the class
        enrollment = Enrollment.query.filter_by(
            student_id=student.id,
            class_id=resource.classroom_id
        ).first()
        
        if not enrollment:
            abort(403)

        # Create and save the comment
        new_comment = ResourceComment(
            content=comment_content.strip(),
            resource_id=resource_id,
            author_id=current_user.id
        )
        
        db.session.add(new_comment)
        db.session.commit()

        flash('Your comment has been added', 'success')
        return redirect(url_for('study_resource_detail', resource_id=resource_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding comment to resource {resource_id}: {str(e)}")
        flash('An error occurred while adding your comment', 'error')
        return redirect(url_for('study_resource_detail', resource_id=resource_id))
    
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    # Normalize path (convert backslashes to forward slashes)
    filename = filename.replace('\\', '/')
    
    # Construct full path to uploads directory
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    
    # Ensure the path is secure
    try:
        return send_from_directory(uploads_dir, filename)
    except FileNotFoundError:
        current_app.logger.error(f"File not found: {filename}")
        abort(404)



# STUDENT ASSIGNMENT AREA

@app.route('/student/assignments')
@login_required
def student_assignments():
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    class_ids = [e.class_id for e in student.enrollments]
    status_filter = request.args.get('status', 'all')
    subject_id = request.args.get('subject_id', type=int)

    # Get current time in UTC
    now_utc = datetime.now(utc)
    
    # Base query
    query = Assignment.query.filter(
        Assignment.class_id.in_(class_ids),
        Assignment.is_published == True
    ).options(
        joinedload(Assignment.classroom),
        joinedload(Assignment.subject)
    )

    # Get all submissions for the student
    submissions = {s.assignment_id: s for s in student.submissions}
    submitted_ids = list(submissions.keys())

    # Apply status filter with timezone-aware comparisons
    if status_filter == 'submitted':
        query = query.filter(Assignment.id.in_(submitted_ids))
    elif status_filter == 'pending':
        query = query.filter(
            Assignment.id.notin_(submitted_ids),
            Assignment.due_date > now_utc
        )
    elif status_filter == 'overdue':
        query = query.filter(
            Assignment.id.notin_(submitted_ids),
            Assignment.due_date < now_utc
        )

    # Apply subject filter
    if subject_id:
        query = query.filter(Assignment.subject_id == subject_id)

    assignments = query.order_by(Assignment.due_date.asc()).all()

    # Get subjects for filter dropdown
    subjects = Subject.query.join(Classroom).filter(
        Classroom.id.in_(class_ids)
    ).distinct().all()

    return render_template('student/assignments/list.html',
        assignments=assignments,
        submissions=submissions,
        status_filter=status_filter,
        subjects=subjects,
        selected_subject=subject_id,
        now=now_utc,  # Pass current UTC time
        local_timezone=local_timezone,
        utc=utc  # Pass utc timezone object
    )

@app.route('/student/assignments/<int:assignment_id>')
@login_required
def student_view_assignment(assignment_id):
    # Authentication and authorization checks
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile

    # Load assignment with relationships
    assignment = Assignment.query.options(
        joinedload(Assignment.classroom),
        joinedload(Assignment.subject),
        joinedload(Assignment.author)
    ).get_or_404(assignment_id)

    # Verify enrollment
    if not Enrollment.query.filter_by(
        student_id=student.id,
        class_id=assignment.class_id
    ).first():
        abort(403)

    # Get user's timezone with proper fallback
    user_tz_string = getattr(current_user, 'timezone', 'UTC')
    
    # Calculate time-related values
    now_utc = datetime.now(pytz.utc)
    time_remaining = assignment.time_remaining(user_tz_string)
    local_due_date = assignment.local_due_date(user_tz_string)
    status_class, status_text, status_icon = assignment.status(user_tz_string)

    submission = Submission.query.filter_by(
        assignment_id=assignment.id,
        student_id=student.id
    ).first()
    
    # Get localized timestamps
    localized_times = submission.to_local_timezone(user_tz_string) if submission else None
    
    return render_template(
        'student/assignments/view.html',
        assignment=assignment,
        submission=submission,
        localized_times=localized_times,  # Pass the converted times separately
        now=now_utc,
        time_remaining=time_remaining,
        local_due_date=local_due_date,
        status_class=status_class,
        status_text=status_text,
        status_icon=status_icon,
        user_timezone=user_tz_string
    )

@app.route('/student/assignments/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
def student_submit_assignment(assignment_id):
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    # Get assignment and ensure it's timezone-aware
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.due_date.tzinfo is None:
        assignment_due_date = assignment.due_date.replace(tzinfo=utc)
    else:
        assignment_due_date = assignment.due_date

    student = current_user.student_profile
    now_utc = datetime.now(utc)

    # Check if submission is still allowed
    if assignment_due_date < now_utc:
        flash('The submission period for this assignment has ended', 'danger')
        return redirect(url_for('student_view_assignment', assignment_id=assignment_id))

    # Check for existing submission
    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student.id
    ).first()

    if request.method == 'POST':
        # Handle form submission
        content = request.form.get('content', '').strip()
        file = request.files.get('file')

        # Validate at least one submission method
        if not content and not file:
            flash('Please provide either a written answer or upload a file', 'danger')
            return redirect(request.url)

        # Handle file upload
        file_path = None
        if file and file.filename:
            # Then the function would be:
            def allowed_submission_file(filename):
                return '.' in filename and \
                    filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
            
            # Create student-specific upload directory
            upload_dir = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                f'student_{student.id}'
            )
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = secure_filename(f"assignment_{assignment_id}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)

        # Create or update submission
        if submission:
            # Update existing submission
            if content:
                submission.content = content
            if file_path:
                # Remove old file if exists
                if submission.file_path and os.path.exists(submission.file_path):
                    try:
                        os.remove(submission.file_path)
                    except OSError:
                        pass  # File might have been already deleted
                submission.file_path = file_path
            submission.submitted_at = now_utc
            db.session.commit()
            flash('Submission updated successfully', 'success')
        else:
            # Create new submission
            submission = Submission(
                assignment_id=assignment_id,
                student_id=student.id,
                content=content,
                file_path=file_path,
                submitted_at=now_utc
            )
            db.session.add(submission)
            db.session.commit()
            flash('Submission created successfully', 'success')

        return redirect(url_for('student_view_assignment', assignment_id=assignment_id))

    # Calculate time remaining properly
    time_remaining = assignment_due_date - now_utc

    return render_template('student/assignments/submit.html',
        assignment=assignment,
        submission=submission,
        now=now_utc,
        time_remaining=time_remaining
    )

@app.route('/submissions/<int:submission_id>/download')
@login_required
def download_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    
    # Verify the requesting user has permission
    if current_user.role == 'student' and submission.student.user_id != current_user.id:
        abort(403)
    elif current_user.role == 'teacher' and submission.assignment.author_id != current_user.id:
        abort(403)
    
    if not submission.file_path or not os.path.exists(submission.file_path):
        abort(404)
    
    return send_file(
        submission.file_path,
        as_attachment=True,
        download_name=submission.get_file_name()
    )

# ---------- STUNDENT GRADE AREA ----------

@app.route('/my-grades')
@login_required
def view_grades():
    """Display all grades for the current student"""
    if current_user.role != 'student':
        flash('Access denied', 'danger')
        return redirect(url_for('teacher_dashboard'))

    # Get assignments with submissions
    assignments = Assignment.query.join(Submission).filter(
        Submission.student_id == current_user.student_profile.id
    ).options(
        joinedload(Assignment.subject),
        joinedload(Assignment.classroom)
    ).all()

    # Get completed quiz attempts with scores
    quiz_attempts = QuizAttempt.query.filter(
        QuizAttempt.student_id == current_user.student_profile.id,
        QuizAttempt.completed_at.isnot(None),
        QuizAttempt.score.isnot(None)
    ).options(
        joinedload(QuizAttempt.quiz).joinedload(Quiz.subject)
    ).all()

    # Calculate statistics
    assignment_stats = {
        'average': calculate_assignment_average(assignments),
        'completed': len([a for a in assignments if a.submissions[0].score is not None]),
        'total': len(assignments)
    }

    quiz_stats = {
        'average': calculate_quiz_average(quiz_attempts),
        'completed': len(quiz_attempts),
        'passed': len([q for q in quiz_attempts if q.is_passed]),
        'total': QuizAttempt.query.filter_by(student_id=current_user.student_profile.id).count()
    }

    return render_template('student/grades/view_grades.html',
                         assignments=assignments,
                         quiz_attempts=quiz_attempts,
                         assignment_stats=assignment_stats,
                         quiz_stats=quiz_stats)

def calculate_assignment_average(assignments):
    """Helper function to calculate assignment average"""
    graded = [a.submissions[0].score for a in assignments if a.submissions[0].score is not None]
    return round(sum(graded)/len(graded), 2) if graded else 0

def calculate_quiz_average(quiz_attempts):
    """Helper function to calculate quiz average"""
    return round(sum(q.score for q in quiz_attempts)/len(quiz_attempts), 2) if quiz_attempts else 0


@app.route('/student/quiz_results/<int:attempt_id>')
@login_required
def quiz_results(attempt_id):
    """Show quiz results"""
    if not current_user.is_authenticated or not hasattr(current_user, 'student_profile'):
        abort(403)
    
    attempt = QuizAttempt.query.options(
        joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
        joinedload(QuizAttempt.answers)
    ).get_or_404(attempt_id)

    if attempt.student_id != current_user.student_profile.id:
        abort(403)

    quiz = attempt.quiz
    correct_count = sum(1 for a in attempt.answers if a.is_correct)
    total_questions = len(quiz.questions)
    percentage_score = (correct_count / total_questions * 100) if total_questions > 0 else 0

    return render_template('student/quizzes/results.html',
        attempt=attempt,
        quiz=quiz,
        correct_count=correct_count,
        total_questions=total_questions,
        percentage_score=percentage_score
    )



# ------------- LIBRARY AREA -------------

@app.route('/library')
def library():
    # Get filter parameters from request
    resource_type = request.args.get('type', 'all')
    subject_id = request.args.get('subject', None, type=int)
    classroom_id = request.args.get('classroom', None, type=int)
    search_query = request.args.get('q', '').strip()
    
    # Start building the query with eager loading
    query = Resource.query.filter_by(is_approved=True)\
                .options(db.joinedload(Resource.subject),
                         db.joinedload(Resource.classroom),
                         db.joinedload(Resource.teacher))
    
    # Apply filters
    if resource_type != 'all':
        query = query.filter_by(resource_type=resource_type)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if classroom_id:
        query = query.filter_by(classroom_id=classroom_id)
    if search_query:
        query = query.filter(
            db.or_(
                Resource.title.ilike(f'%{search_query}%'),
                Resource.description.ilike(f'%{search_query}%')
            )
        )
    
    # Get sorting option
    sort_by = request.args.get('sort', 'recent')
    if sort_by == 'recent':
        query = query.order_by(Resource.upload_date.desc())
    elif sort_by == 'popular':
        query = query.order_by(Resource.download_count.desc())
    elif sort_by == 'views':
        query = query.order_by(Resource.views_count.desc())
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 12
    resources = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Debug output
    app.logger.debug(f"Resources query: {query}")
    app.logger.debug(f"Found {resources.total} resources")
    
    # Get filter options
    subjects = Subject.query.order_by(Subject.name).all()
    classrooms = Classroom.query.order_by(Classroom.class_name).all()
    
    return render_template('library/library.html', 
                        resources=resources,
                        subjects=subjects,
                        classrooms=classrooms,
                        current_type=resource_type,
                        current_subject=subject_id,
                        current_classroom=classroom_id,
                        search_query=search_query,
                        sort_by=sort_by)

@app.route('/resources/download/<int:resource_id>')
def download_library_resource(resource_id):
    """Download a resource file with proper MIME type and security checks"""
    resource = Resource.query.get_or_404(resource_id)
    
    # Security checks
    if '..' in resource.file_path or resource.file_path.startswith('/'):
        current_app.logger.warning(f"Potential path traversal attempt: {resource.file_path}")
        abort(400, description="Invalid file path")
    
    # Increment download count
    resource.download_count += 1
    db.session.commit()
    
    # Build absolute file path
    base_dir = current_app.config['UPLOAD_FOLDER']
    file_dir = os.path.join(base_dir, os.path.dirname(resource.file_path))
    filename = os.path.basename(resource.file_path)
    full_path = os.path.join(file_dir, filename)
    
    # Verify file exists
    if not os.path.exists(full_path):
        current_app.logger.error(f"File not found. Expected at: {full_path}")
        current_app.logger.error(f"Upload folder: {base_dir}")
        current_app.logger.error(f"Resource path: {resource.file_path}")
        abort(404, description="File not found")
    
    try:
        return send_from_directory(
            directory=file_dir,
            path=filename,
            as_attachment=True,
            download_name=resource.file_name,
            mimetype=get_mime_type(resource.file_name)
        )
    except Exception as e:
        current_app.logger.error(f"Failed to send file: {str(e)}")
        abort(500, description="File download failed")

@app.route('/resources/view/<int:resource_id>')
def view_library_resource(resource_id):
    """View resource details with integrated preview functionality"""
    resource = Resource.query.options(
        db.joinedload(Resource.subject),
        db.joinedload(Resource.classroom),
        db.joinedload(Resource.teacher)
    ).get_or_404(resource_id)
    
    # Increment view count
    resource.views_count += 1
    db.session.commit()
    
    # Get comments
    comments = ResourceComment.query.filter_by(resource_id=resource_id)\
                .order_by(ResourceComment.created_at.desc()).all()
    
    # Determine preview capability
    preview_config = {
        'can_preview': False,
        'preview_type': None,
        'preview_url': None,
        'download_url': url_for('download_library_resource', resource_id=resource.id)
    }
    
    # Set preview options based on file type
    if resource.file_type.lower() == 'pdf':
        preview_config.update({
            'can_preview': True,
            'preview_type': 'pdf',
            'preview_url': url_for('download_library_resource', resource_id=resource.id) + '#toolbar=0'
        })
    elif resource.file_type.lower() in ['jpg', 'jpeg', 'png', 'gif']:
        preview_config.update({
            'can_preview': True,
            'preview_type': 'image',
            'preview_url': url_for('download_library_resource', resource_id=resource.id)
        })
    elif resource.file_type.lower() in ['mp4', 'webm', 'ogg']:
        preview_config.update({
            'can_preview': True,
            'preview_type': 'video',
            'preview_url': url_for('download_library_resource', resource_id=resource.id)
        })
    elif resource.file_type.lower() in ['mp3', 'wav', 'ogg']:
        preview_config.update({
            'can_preview': True,
            'preview_type': 'audio',
            'preview_url': url_for('download_library_resource', resource_id=resource.id)
        })
    
    return render_template('library/view_library_resource.html',
                         resource=resource,
                         comments=comments,
                         preview=preview_config)


# STUDENT QUIZ AREA - IMPROVED VERSION

# Enhanced utility functions
def get_student_quiz_data(student_id):
    """Get all quiz-related data for a student in one optimized query"""
    return (
        db.session.query(Enrollment, Classroom, Subject)
        .join(Classroom, Enrollment.class_id == Classroom.id)
        .join(Subject, Classroom.subject_id == Subject.id)
        .filter(Enrollment.student_id == student_id)
        .all()
    )

@app.route('/student/quizzes/<int:quiz_id>/start', methods=['GET', 'POST'])
@login_required
def student_start_quiz(quiz_id):
    """Start a quiz with timezone awareness"""
    if not current_user.is_authenticated or not hasattr(current_user, 'student_profile'):
        abort(403)
        
    quiz = Quiz.query.get_or_404(quiz_id)
    user_tz = getattr(current_user, 'timezone', ZoneInfo(APP_TIMEZONE))
    current_utc = now_utc()
    
    # Convert quiz times to local timezone for display
    if quiz.due_date:
        if isinstance(user_tz, str):
            user_tz = ZoneInfo(user_tz)
        quiz.due_date_local = quiz.due_date.astimezone(user_tz)
    
    # Check if already has incomplete attempt
    existing_attempt = QuizAttempt.query.filter_by(
        quiz_id=quiz_id,
        student_id=current_user.student_profile.id,
        completed_at=None
    ).first()
    
    if existing_attempt:
        return redirect(url_for('student_take_quiz', attempt_id=existing_attempt.id))
    
    if request.method == 'POST':
        # Create new attempt with UTC timestamp
        new_attempt = QuizAttempt(
            student_id=current_user.student_profile.id,
            quiz_id=quiz_id,
            started_at=current_utc
        )
        db.session.add(new_attempt)
        db.session.commit()
        
        return redirect(url_for('student_take_quiz', attempt_id=new_attempt.id))
    
    # For GET requests, show confirmation page with local times
    return render_template('student/quizzes/start_quiz.html',
        quiz=quiz,
        time_limit=quiz.time_limit,
        now_local=current_utc.astimezone(user_tz)
    )


# In your routes.py or views.py
@app.route('/student/quizzes/attempt/<int:attempt_id>', methods=['GET', 'POST'])
@login_required
def student_take_quiz(attempt_id):
    """Handle the quiz taking process including answer submission and navigation"""
    
    # 1. Authentication and Authorization
    if not current_user.is_authenticated or not hasattr(current_user, 'student_profile'):
        abort(403)  # Forbidden if not logged in or not a student
    
    # 2. Load Quiz Attempt Data
    attempt = QuizAttempt.query.options(
        joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
        joinedload(QuizAttempt.answers)
    ).get_or_404(attempt_id)

    if attempt.student_id != current_user.student_profile.id:
        abort(403)  # Forbidden if not the student's attempt

    quiz = attempt.quiz
    questions = sorted(quiz.questions, key=lambda q: q.position) if quiz.questions else []
    total_questions = len(questions)

    # 3. Quiz Availability Checks
    if quiz.due_date and quiz.due_date.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        flash('This quiz is no longer available.', 'danger')
        return redirect(url_for('student_view_quiz', quiz_id=quiz.id))

    if attempt.completed_at:
        flash('You have already completed this quiz.', 'info')
        return redirect(url_for('student_quiz_results', attempt_id=attempt.id))

    # 4. Handle Current Question Index
    try:
        current_index = int(request.args.get('q', 0))
        current_index = max(0, min(current_index, total_questions - 1))  # Clamp between 0 and max index
    except (ValueError, TypeError):
        current_index = 0

    # 5. Process Form Submissions (POST requests)
    if request.method == 'POST':
        return handle_quiz_submission(attempt_id, attempt, questions, current_index, total_questions)

    # 6. Display Current Question (GET requests)
    return display_quiz_question(attempt, quiz, questions, current_index, total_questions)


def handle_quiz_submission(attempt_id, attempt, questions, current_index, total_questions):
    """Process the submission of a quiz answer and handle navigation"""
    
    # 1. Get form data
    question_id = request.form.get('question_id', type=int)
    answer = request.form.get('answer', '').strip()
    current_index = request.form.get('current_index', type=int, default=current_index)

    # 2. Validate current question
    current_question = next((q for q in questions if q.id == question_id), None)
    if not current_question:
        flash('Invalid question.', 'danger')
        return redirect(url_for('student_take_quiz', attempt_id=attempt_id, q=current_index))

    # 3. Validate answer exists (unless question is optional)
    if not answer and not current_question.is_optional:
        flash('Please provide an answer.', 'danger')
        return redirect(url_for('student_take_quiz', attempt_id=attempt_id, q=current_index))

    # 4. Save the answer if provided
    if answer or current_question.is_optional:
        save_quiz_answer(attempt, current_question, answer)

    # 5. Handle final submission
    if 'confirm-submit' in request.form:
        return handle_quiz_completion(attempt_id, attempt, current_index, total_questions)

    # 6. Navigate to next question or stay on current if at end
    next_index = current_index + 1
    return redirect(url_for('student_take_quiz', 
        attempt_id=attempt_id, 
        q=next_index if next_index < total_questions else current_index
    ))


def save_quiz_answer(attempt, question, answer):
    """Save or update a quiz answer with proper validation"""
    
    # 1. Find existing answer or create new
    existing_answer = next((a for a in attempt.answers if a.question_id == question.id), None)
    now = datetime.now(timezone.utc)
    
    # 2. Determine if answer is correct
    is_correct = check_answer_correctness(question, answer)
    
    # 3. Update existing answer or create new one
    if existing_answer:
        update_existing_answer(existing_answer, question, answer, is_correct, now)
    else:
        create_new_answer(attempt, question, answer, is_correct, now)
    
    db.session.commit()


def check_answer_correctness(question, answer):
    """Determine if the submitted answer matches the correct answer"""
    
    # Handle empty answers
    if not answer:
        return False

    # Multiple Choice Questions
    if question.question_type == 'multiple_choice':
        # Handle dictionary format options (e.g., {'A': 'Option 1', 'B': 'Option 2'})
        if isinstance(question.options, dict):
            return str(answer).strip().upper() == str(question.correct_option).strip().upper()
        
        # Handle list format options (e.g., ['Option 1', 'Option 2'])
        elif isinstance(question.options, list):
            try:
                selected_index = int(answer)
                if 0 <= selected_index < len(question.options):
                    selected_text = str(question.options[selected_index]).strip().upper()
                    correct_text = str(question.correct_option).strip().upper()
                    return selected_text == correct_text
            except (ValueError, IndexError):
                return False
    
    # True/False Questions
    elif question.question_type == 'true_false':
        user_answer = str(answer).strip().upper()
        correct_answer = str(question.correct_option).strip().upper()
        return user_answer == correct_answer
    
    # Short Answer Questions
    elif question.question_type == 'short_answer':
        user_answer = str(answer).strip().lower()
        # Handle multiple correct answers separated by pipes (e.g., "Paris|paris|PARIS")
        correct_answers = [a.strip().lower() for a in str(question.correct_option).split('|')]
        return user_answer in correct_answers
    
    return False


def update_existing_answer(answer, question, user_answer, is_correct, timestamp):
    """Update an existing answer record"""
    if question.question_type == 'short_answer':
        answer.answer_text = str(user_answer).strip()
        answer.selected_answer = None
    else:
        answer.selected_answer = str(user_answer).strip()
        answer.answer_text = None
    
    answer.is_correct = is_correct
    answer.updated_at = timestamp


def create_new_answer(attempt, question, answer, is_correct, timestamp):
    """Create a new answer record"""
    new_answer = QuizAnswer(
        attempt_id=attempt.id,
        question_id=question.id,
        selected_answer=str(answer).strip() if question.question_type != 'short_answer' else None,
        answer_text=str(answer).strip() if question.question_type == 'short_answer' else None,
        is_correct=is_correct,
        answered_at=timestamp,
        created_at=timestamp
    )
    db.session.add(new_answer)


def handle_quiz_completion(attempt_id, attempt, current_index, total_questions):
    """Finalize the quiz attempt and show results"""
    
    # 1. Check if all questions are answered
    answered_questions = {a.question_id for a in attempt.answers if a.has_answer}
    unanswered_count = total_questions - len(answered_questions)
    
    if unanswered_count > 0:
        flash(f'You have {unanswered_count} unanswered question(s).', 'warning')
        return redirect(url_for('student_take_quiz', attempt_id=attempt_id, q=current_index))
    
    # 2. Mark attempt as completed
    attempt.completed_at = datetime.now(timezone.utc)
    attempt.calculate_score()  # Assuming this method exists to calculate total score
    db.session.commit()
    
    # 3. Redirect to results page
    return redirect(url_for('student_quiz_results', attempt_id=attempt_id))


def display_quiz_question(attempt, quiz, questions, current_index, total_questions):
    """Render the quiz question page with all necessary context"""
    
    current_question = questions[current_index]
    current_answer = next((a for a in attempt.answers if a.question_id == current_question.id), None)

    # Calculate progress metrics
    answered_ids = {a.question_id for a in attempt.answers if a.has_answer}
    unanswered_count = total_questions - len(answered_ids)
    
    time_remaining = calculate_time_remaining(quiz, attempt)  # Assuming this helper exists
    progress = int((len(answered_ids) / total_questions) * 100) if total_questions else 0

    return render_template('student/quizzes/take_quiz.html',
        attempt=attempt,
        quiz=quiz,
        questions=questions,
        current_question=current_question,
        current_index=current_index,
        current_answer=current_answer,
        time_remaining=time_remaining,
        unanswered_count=unanswered_count,
        total_questions=total_questions,
        progress=progress
    )

def calculate_time_remaining(quiz, attempt):
    """Calculate remaining time for timed quizzes"""
    if not quiz.time_limit or not attempt.started_at:
        return 0
    
    elapsed = (datetime.now(timezone.utc) - attempt.started_at.replace(tzinfo=timezone.utc)).total_seconds()
    return max(0, quiz.time_limit * 60 - elapsed)


@app.route('/student/quizzes')
@login_required
def student_quizzes():
    """List quizzes for student with proper timezone handling and attempt status"""
    try:
        status_filter = request.args.get('status', 'upcoming')
        subject_id = request.args.get('subject_id', type=int)
        now_utc = datetime.now(timezone.utc)

        # Get enrolled classes
        enrollments = Enrollment.query.filter_by(
            student_id=current_user.student_profile.id,
            is_dropped=False
        ).all()

        if not enrollments:
            return render_template('student/quizzes/list.html',
                                quizzes=[],
                                subjects=[],
                                status_filter=status_filter,
                                selected_subject=subject_id,
                                now=now_utc)

        class_ids = [e.class_id for e in enrollments]

        # Base query
        query = Quiz.query.options(
            joinedload(Quiz.classroom).joinedload(Classroom.subject),
            joinedload(Quiz.attempts)
        ).filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == 'published',
            Quiz.deleted_at.is_(None)
        )

        # Apply filters based on status
        if status_filter == 'upcoming':
            # Show quizzes that are not completed and not expired
            query = query.filter(
                or_(
                    Quiz.due_date.is_(None),
                    Quiz.due_date > now_utc.replace(tzinfo=None)
                )
            ).filter(
                ~exists().where(and_(
                    QuizAttempt.quiz_id == Quiz.id,
                    QuizAttempt.student_id == current_user.student_profile.id,
                    QuizAttempt.completed_at.isnot(None)
                ))
            ).order_by(Quiz.due_date.asc())

        elif status_filter == 'completed':
            # Show only completed quizzes (most recent first)
            query = query.join(QuizAttempt).filter(
                QuizAttempt.student_id == current_user.student_profile.id,
                QuizAttempt.completed_at.isnot(None)
            ).order_by(QuizAttempt.completed_at.desc()).limit(5)

        elif status_filter == 'expired':
            # Show expired quizzes (most recent due date first)
            query = query.filter(
                Quiz.due_date <= now_utc.replace(tzinfo=None),
                ~exists().where(and_(
                    QuizAttempt.quiz_id == Quiz.id,
                    QuizAttempt.student_id == current_user.student_profile.id,
                    QuizAttempt.completed_at.isnot(None)
                ))
            ).order_by(Quiz.due_date.desc()).limit(5)

        if subject_id:
            query = query.join(Classroom).filter(Classroom.subject_id == subject_id)

        quizzes = query.all()

        # Convert all due dates to UTC for template display
        for quiz in quizzes:
            if quiz.due_date and not quiz.due_date.tzinfo:
                quiz.due_date = quiz.due_date.replace(tzinfo=timezone.utc)

        subjects = Subject.query.join(Classroom).filter(
            Classroom.id.in_(class_ids)
        ).distinct().all()

        return render_template('student/quizzes/list.html',
                            quizzes=quizzes,
                            subjects=subjects,
                            status_filter=status_filter,
                            selected_subject=subject_id,
                            now=now_utc)

    except Exception as e:
        current_app.logger.error(f"Error loading quizzes: {str(e)}", exc_info=True)
        flash('Error loading quizzes. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
    

@app.route('/student/quizzes/<int:quiz_id>')
@login_required
def student_view_quiz(quiz_id):
    """Show details for a specific quiz"""
    try:
        quiz = Quiz.query.get_or_404(quiz_id)
        now = datetime.now(timezone.utc)
        
        # Verify student is enrolled
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.student_profile.id,
            class_id=quiz.classroom_id,
            is_dropped=False
        ).first_or_404()

        # Check for existing attempt
        attempt = QuizAttempt.query.filter_by(
            student_id=current_user.student_profile.id,
            quiz_id=quiz.id
        ).order_by(QuizAttempt.created_at.desc()).first()

        # Ensure quiz.due_date is timezone-aware if it exists
        if quiz.due_date and quiz.due_date.tzinfo is None:
            quiz.due_date = quiz.due_date.replace(tzinfo=timezone.utc)

        return render_template('student/quizzes/detail.html',
                            quiz=quiz,
                            attempt=attempt,
                            now=now)

    except Exception as e:
        current_app.logger.error(f"Error loading quiz: {str(e)}")
        flash('Error loading quiz details', 'danger')
        return redirect(url_for('student_quizzes'))
    

@app.route('/student/quizzes/attempt/<int:attempt_id>/results')
@login_required
def student_quiz_results(attempt_id):
    """Show quiz results"""
    if not current_user.is_authenticated or not hasattr(current_user, 'student_profile'):
        abort(403)
    
    attempt = QuizAttempt.query.options(
        joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
        joinedload(QuizAttempt.answers).joinedload(QuizAnswer.question)  # Ensure question is loaded for each answer
    ).get_or_404(attempt_id)

    if attempt.student_id != current_user.student_profile.id:
        abort(403)

    quiz = attempt.quiz
    
    # Calculate score by comparing each answer with its question's correct answer
    correct_count = 0
    for answer in attempt.answers:
        question = answer.question
        if question.question_type == 'multiple_choice':
            answer.is_correct = (answer.selected_answer == question.correct_option)
        elif question.question_type == 'true_false':
            answer.is_correct = (answer.selected_answer == question.correct_option)
        elif question.question_type == 'short_answer':
            # For short answers, do case-insensitive comparison after stripping whitespace
            correct_answers = [a.strip().lower() for a in question.correct_option.split('|')]
            answer.is_correct = (answer.answer_text and 
                                str(answer.answer_text).strip().lower() in correct_answers)
        
        if answer.is_correct:
            correct_count += 1
    
    total_questions = len(quiz.questions)
    percentage_score = (correct_count / total_questions * 100) if total_questions > 0 else 0

    return render_template('student/quizzes/results.html',
        attempt=attempt,
        quiz=quiz,
        correct_count=correct_count,
        total_questions=total_questions,
        percentage_score=percentage_score
    )


# STUDENT MESSAGE AREA

@app.route('/student/messages')
@login_required
def student_messages():
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    class_ids = [e.class_id for e in student.enrollments]
    
    # Get filters from query params
    message_type = request.args.get('type', 'all')
    is_read = request.args.get('read', None)
    page = request.args.get('page', 1, type=int)
    
    # Base query
    query = Message.query.filter(
        db.or_(
            Message.class_id.in_(class_ids),
            Message.recipient_id == student.id
        ),
        Message.sender_role == 'teacher'  # Only show messages from teachers
    )
    
    # Apply filters
    if message_type == 'announcement':
        query = query.filter(Message.is_announcement == True)
    elif message_type == 'personal':
        query = query.filter(Message.is_announcement == False)
    
    if is_read == 'read':
        query = query.filter(Message.is_read == True)
    elif is_read == 'unread':
        query = query.filter(Message.is_read == False)
    
    messages = query.options(
        joinedload(Message.sender_user),
        joinedload(Message.classroom),
        joinedload(Message.parent)
    ).order_by(
        Message.is_read.asc(),  # Unread first
        Message.timestamp.desc()
    ).paginate(page=page, per_page=10)
    
    return render_template('student/messages/inbox.html',
        messages=messages,
        message_type=message_type,
        is_read=is_read
    )


@app.route('/student/messages/<int:message_id>/reply', methods=['POST'])
@login_required
def student_reply_message(message_id):
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    original_message = Message.query.get_or_404(message_id)
    
    # Verify access
    if (original_message.recipient_id and original_message.recipient_id != student.id) or \
       (original_message.class_id and original_message.class_id not in [e.class_id for e in student.enrollments]):
        abort(403)
    
    content = request.form.get('content')
    if not content:
        flash('Message content cannot be empty', 'danger')
        return redirect(url_for('student_view_message', message_id=message_id))
    
    reply = original_message.reply(
        content=content,
        sender_id=current_user.id,
        sender_role='student'
    )
    
    db.session.add(reply)
    db.session.commit()
    
    flash('Your reply has been sent', 'success')
    return redirect(url_for('student_view_message', message_id=message_id))

@app.route('/student/messages/new', methods=['GET', 'POST'])
@login_required
def student_new_message():
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    class_ids = [e.class_id for e in student.enrollments]
    
    if request.method == 'POST':
        recipient_id = request.form.get('recipient_id')
        class_id = request.form.get('class_id')
        title = request.form.get('title')
        content = request.form.get('content')
        
        # Validate recipient (must be a teacher in one of student's classes)
        valid_recipient = False
        if class_id:
            classroom = Classroom.query.get(class_id)
            if classroom and classroom.id in class_ids:
                recipient_id = classroom.teacher.id
                valid_recipient = True
        elif recipient_id:
            teacher = Teacher.query.get(recipient_id)
            if teacher and any(c.teacher_id == teacher.id for c in student.classrooms):
                valid_recipient = True
        
        if not valid_recipient or not title or not content:
            flash('Invalid message parameters', 'danger')
            return redirect(url_for('student_new_message'))
        
        message = Message(
            title=title,
            content=content,
            class_id=class_id if class_id else None,
            sender_id=current_user.id,
            sender_role='student',
            recipient_id=recipient_id,
            is_urgent=False
        )
        
        db.session.add(message)
        db.session.commit()
        flash('Message sent successfully', 'success')
        return redirect(url_for('student_messages'))
    
    # GET request - show form
    classrooms = Classroom.query.filter(
        Classroom.id.in_(class_ids)
    ).options(
        joinedload(Classroom.teacher).joinedload(Teacher.username)
    ).all()
    
    return render_template('student/messages/new.html',
        classrooms=classrooms
    )

@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    """Teacher dashboard route."""
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    # Get teacher's classrooms and students
    classrooms = Classroom.query.filter_by(teacher_id=current_user.id).all()
    classes = [{
        'classroom': classroom,
        'students': Enrollment.query.filter_by(class_id=classroom.id).all(),
        'quizzes': Quiz.query.filter_by(classroom_id=classroom.id).all()  # Add this line if you have quizzes
    } for classroom in classrooms]

    messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).all()

    return render_template(
        'teacher_dashboard.html',
        username=current_user.username,
        email=current_user.email,
        classes=classes,
        messages=messages
    )


@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard route with statistics."""
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    # Time period calculations
    current_time = datetime.now(local_timezone)
    last_month_time = current_time - timedelta(days=30)
    last_month_start = last_month_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def get_percentage_change(model, filter_condition=None):
        """Calculate count and percentage change from last month."""
        query = model.query
        if filter_condition:
            query = query.filter(filter_condition)

        current_count = query.count()
        current_month_count = query.filter(model.created_at >= current_month_start).count()
        last_month_count = query.filter(
            and_(
                model.created_at >= last_month_start,
                model.created_at < current_month_start
            )
        ).count()

        change_percent = 100.0 if (last_month_count == 0 and current_month_count > 0) else (
            ((current_month_count - last_month_count) / last_month_count) * 100 if last_month_count != 0 else 0.0
        )

        return {
            'total_count': current_count,
            'current_month_count': current_month_count,
            'last_month_count': last_month_count,
            'change_percent': change_percent
        }

    stats = {
        'teachers': get_percentage_change(User, User.role == 'teacher'),
        'students': get_percentage_change(User, User.role == 'student'),
        'classes': get_percentage_change(Classroom),
        'departments': get_percentage_change(Department)
    }

    recent_activities = Activity.query.order_by(Activity.timestamp.desc()).limit(5).all()

    return render_template(
        'admin_dashboard.html',
        username=current_user.username,
        stats=stats,
        recent_activities=recent_activities
    )

# ---------- SESSION MANAGEMENT ROUTES ----------

def sanitize_input(input_string):
    """Sanitize input to prevent potential security issues."""
    return ''.join(c for c in input_string if c.isalnum() or c.isspace()).strip()

@app.route('/video_conference')
@login_required
def video_conference():
    """Enhanced video conference management for teachers"""
    # Check if user is a teacher
    if current_user.role != 'teacher':
        return render_template('error.html', 
            message="Access Denied",
            error_details="Only teachers can access video conference features"), 403
    
    try:
        # Get all classes the teacher can access
        classes = Classroom.query.filter_by(teacher_id=current_user.id).all()
        
        # Get sessions with proper timezone handling
        sessions = OnlineSession.query.filter_by(creator_id=current_user.id)\
            .order_by(OnlineSession.start_time.desc())\
            .limit(20).all()  # Limit to 20 most recent sessions

        now_utc = datetime.now(timezone.utc)
        
        # Process sessions with timezone awareness
        processed_sessions = []
        for session in sessions:
            try:
                # Ensure timezone awareness
                if not session.start_time.tzinfo:
                    session.start_time = session.start_time.replace(tzinfo=timezone.utc)
                if session.end_time and not session.end_time.tzinfo:
                    session.end_time = session.end_time.replace(tzinfo=timezone.utc)
                
                # Calculate local times
                tz = ZoneInfo(session.original_timezone or current_user.timezone or 'Africa/Dar_es_Salaam')
                session.start_local = session.start_time.astimezone(tz)
                session.end_local = session.end_time.astimezone(tz) if session.end_time else None
                
                # Determine status
                session.status = 'upcoming' if now_utc < session.start_time else \
                               'live' if now_utc <= session.end_time else \
                               'ended'
                
                processed_sessions.append(session)
            except Exception as e:
                current_app.logger.error(f"Error processing session {session.id}: {e}")
                continue

        # Get current times for display
        server_time = now_utc.strftime('%b %d, %Y %H:%M:%S UTC')
        dar_time = now_utc.astimezone(ZoneInfo("Africa/Dar_es_Salaam"))
        dar_time_str = dar_time.strftime('%b %d, %Y %H:%M:%S EAT')

        return render_template(
            'video_conference.html',
            classes=classes,
            sessions=processed_sessions,
            now_utc=now_utc,
            server_time=server_time,
            dar_time_str=dar_time_str,
            csrf_token=flask_session.get('_csrf_token'),
            user_timezone=current_user.timezone or 'Africa/Dar_es_Salaam'
        )

    except Exception as e:
        current_app.logger.error(f"Video conference error: {e}", exc_info=True)
        return render_template('error.html', 
            message="Failed to load session management",
            error_details=str(e)), 500

@app.route('/start_session', methods=['POST'])
@login_required
def start_session():
    """Create a new online session with robust timezone handling"""
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Only teachers can create sessions'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request data'}), 400

    try:
        # Extract and validate data
        class_id = data.get('class_id')
        session_name = (data.get('session_name') or '').strip()
        user_timezone = data.get('timezone') or current_user.timezone or 'Africa/Dar_es_Salaam'

        # Validate class existence
        classroom = Classroom.query.get(class_id)
        if not classroom:
            return jsonify({'success': False, 'error': 'Class not found'}), 404

        # Validate session name
        if not (1 <= len(session_name) <= 100):
            return jsonify({'success': False, 'error': 'Session name must be between 1 and 100 characters'}), 400

        # Parse and validate times
        try:
            tz = ZoneInfo(user_timezone)
            
            # Parse start time
            start_time = datetime.fromisoformat(data['start_time'])
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=tz)
            start_time_utc = start_time.astimezone(timezone.utc)

            # Parse end time
            end_time = datetime.fromisoformat(data['end_time'])
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=tz)
            end_time_utc = end_time.astimezone(timezone.utc)

            # Validate time logic
            if end_time_utc <= start_time_utc:
                return jsonify({'success': False, 'error': 'End time must be after start time'}), 400

            duration_minutes = int((end_time_utc - start_time_utc).total_seconds() / 60)
            if duration_minutes > 480:
                return jsonify({'success': False, 'error': 'Session cannot exceed 8 hours'}), 400

        except Exception as e:
            current_app.logger.error(f"Time parsing error: {e}")
            return jsonify({'success': False, 'error': f'Invalid time data: {str(e)}'}), 400

        # Create new session
        room_id = f"class-{class_id}-{uuid.uuid4().hex[:6]}"
        new_session = OnlineSession(
            room_id=room_id,
            session_name=session_name,
            session_link=f"{request.host_url.rstrip('/')}/join/{room_id}",
            class_id=class_id,
            creator_id=current_user.id,
            start_time=start_time_utc,
            end_time=end_time_utc,
            original_timezone=user_timezone,
            duration_minutes=duration_minutes,
            status='scheduled',
            video_url=f"{request.host_url.rstrip('/')}/join/{room_id}"
        )

        db.session.add(new_session)
        db.session.commit()

        return jsonify({
            'success': True,
            'session': new_session.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Session creation failed: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


def parse_and_localize(iso_str, tz):
    """Parse ISO datetime string and localize if naive."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)

# ... (other imports)
@app.route('/student_sessions')
@login_required
def student_sessions():
    """Display all upcoming and current sessions for the student"""
    if current_user.role != 'student':
        abort(403)

    try:
        current_utc = datetime.now(timezone.utc)
        local_tz = ZoneInfo(current_user.timezone or 'Africa/Dar_es_Salaam')
        current_local = current_utc.astimezone(local_tz)

        # Get enrolled class IDs
        enrolled_class_ids = [e.class_id for e in current_user.student_profile.enrollments] or []

        if not enrolled_class_ids:
            return render_template('student/student_sessions.html',
                                active_sessions=[],
                                now=current_local,
                                timezone=str(local_tz),
                                no_classes=True)

        # Query sessions with proper validation
        sessions = (db.session.query(OnlineSession)
            .join(Classroom)
            .join(User, OnlineSession.creator_id == User.id)
            .filter(
                OnlineSession.class_id.in_(enrolled_class_ids),
                OnlineSession.end_time >= current_utc - timedelta(days=30)
            )
            .order_by(OnlineSession.start_time.asc())
            .all())

        processed_sessions = []
        for session in sessions:
            try:
                start_local = session.start_time.astimezone(local_tz)
                end_local = session.end_time.astimezone(local_tz) if session.end_time else None
                
                processed_sessions.append({
                    'id': session.id,
                    'class_name': session.classroom.class_name,
                    'session_name': session.session_name or "Untitled Session",
                    'instructor': session.creator.username,
                    'start_time': start_local,
                    'end_time': end_local,
                    'room_id': session.room_id,
                    'recording_url': session.recording_url,
                    'status': session.get_status(current_utc),
                    'is_valid': session.is_valid,
                    'time_until': (start_local - current_local) if session.get_status() == 'upcoming' else None
                })
            except Exception as e:
                current_app.logger.error(f"Error processing session {session.id}: {e}")
                continue

        return render_template('student/student_sessions.html',
                            active_sessions=processed_sessions,
                            now=current_local,
                            timezone=str(local_tz),
                            no_classes=False)

    except Exception as e:
        current_app.logger.error(f"student_sessions error: {e}")
        return render_template('error.html', 
                            message="Error loading sessions",
                            error=str(e)), 500


@app.route('/join_session/<room_id>')
@login_required
def join_session(room_id):
    """Handle student joining a session with proper timezone handling and enhanced validation"""
    try:
        # Get session details with proper locking to prevent race conditions
        session = OnlineSession.query.filter_by(room_id=room_id).with_for_update().first_or_404()
        
        # Enhanced enrollment check for students
        if current_user.role == 'student':
            enrollment_check = db.session.query(
                exists().where(
                    and_(
                        Enrollment.class_id == session.class_id,
                        Enrollment.student_id == current_user.student_profile.id,
                        Enrollment.is_dropped == False
                    )
                )
            ).scalar()
            
            if not enrollment_check:
                flash('You are not enrolled in this class or your enrollment is inactive', 'danger')
                return redirect(url_for('student_dashboard'))

        # Get current time in UTC (timezone-aware)
        now_utc = datetime.now(timezone.utc)
        
        # Ensure session times are timezone-aware (defensive programming)
        if session.start_time and not session.start_time.tzinfo:
            session.start_time = session.start_time.replace(tzinfo=timezone.utc)
        if session.end_time and not session.end_time.tzinfo:
            session.end_time = session.end_time.replace(tzinfo=timezone.utc)

        # Calculate local times for display using the session's original timezone
        try:
            tz = ZoneInfo(session.original_timezone or 'Africa/Dar_es_Salaam')
        except Exception:
            tz = ZoneInfo('Africa/Dar_es_Salaam')  # Fallback to default
            
        start_local = session.start_time.astimezone(tz) if session.start_time else None
        end_local = session.end_time.astimezone(tz) if session.end_time else None

        # Prepare context data with additional session information
        context = {
            'session': session,
            'now_utc': now_utc,
            'random': random.randint(1000, 9999),
            'csrf_token': generate_csrf(),
            'start_local': start_local,
            'end_local': end_local,
            'classroom': session.classroom  # Include classroom details
        }

        # Session timing validation with proper timezone comparisons
        if session.start_time and now_utc < session.start_time:
            flash(f'Session starts at {start_local.strftime("%b %d, %Y %I:%M %p")}', 'info')
            return render_template('student/join_session.html', **context)
            
        if session.end_time and now_utc > session.end_time:
            if session.recording_url:
                return redirect(session.recording_url)
            flash('This session has ended', 'info')
            return render_template('student/join_session.html', **context)

        # For active sessions, verify the teacher is present (if implemented)
        if current_app.config.get('VERIFY_TEACHER_PRESENCE', False):
            teacher_present = session.teacher_present if hasattr(session, 'teacher_present') else False
            if not teacher_present:
                flash('The teacher has not started the session yet', 'warning')
                return render_template('student/join_session.html', **context)

        # If session is active, render the joining page with auto-join parameter
        return render_template('student/join_session.html', **context)

    except Exception as e:
        current_app.logger.error(f"Error joining session: {str(e)}", exc_info=True)
        flash('Error joining session. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))


@app.route('/record_attendance', methods=['POST'])
@login_required
def record_attendance():
    """Record initial student participation during session"""
    try:
        data = request.get_json()
        if not data or 'session_id' not in data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400

        session = OnlineSession.query.with_for_update().get(data['session_id'])
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        now_utc = datetime.now(timezone.utc)
        
        # Only allow recording during active session
        if session.end_time and now_utc > session.end_time.replace(tzinfo=timezone.utc):
            return jsonify({'success': False, 'error': 'Session has ended. Attendance will be finalized shortly.'}), 400

        today_utc = now_utc.date()
        
        # Check for existing participation record
        existing = Attendance.query.filter(
            Attendance.student_id == current_user.student_profile.id,
            Attendance.session_id == session.id,
            Attendance.date == today_utc
        ).first()

        if not existing:
            # Create initial participation record
            attendance = Attendance(
                student_id=current_user.student_profile.id,
                session_id=session.id,
                joined_at=now_utc.replace(tzinfo=None),
                date=today_utc,
                duration=0,  # Will be updated after session ends
                status='participating'  # Initial status
            )
            db.session.add(attendance)
            db.session.commit()

            # Notify teacher
            teacher_id = session.creator_id
            if teacher_id:
                Notification.create_for_user(
                    user_id=teacher_id,
                    title="Student Participation Started",
                    message=f"{current_user.student_profile.full_name} joined {session.session_name}",
                    link=f"/attendance/view/{session.id}",
                    notification_type='attendance',
                    related_id=session.id
                )

                socketio.emit('new_attendance', {
                    'student_name': current_user.student_profile.full_name,
                    'session_name': session.session_name,
                    'time': now_utc.isoformat(),
                    'session_id': session.id,
                    'status': 'participating'
                }, room=f"teacher_{teacher_id}")

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Attendance error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/finalize_attendance/<int:session_id>', methods=['POST'])
@login_required
def finalize_attendance(session_id):
    """Finalize attendance records after session ends"""
    try:
        session = OnlineSession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Only allow teachers or admins to finalize attendance
        if not (current_user.is_teacher or current_user.is_admin) or \
           (current_user.is_teacher and session.creator_id != current_user.id):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        now_utc = datetime.now(timezone.utc)
        
        # Only allow finalizing after session ends
        if session.end_time and now_utc < session.end_time.replace(tzinfo=timezone.utc):
            return jsonify({'success': False, 'error': 'Session has not ended yet'}), 400

        # Get all participation records for this session
        participations = Attendance.query.filter(
            Attendance.session_id == session_id,
            Attendance.status == 'participating'
        ).all()

        # Calculate duration and finalize status for each student
        for record in participations:
            duration_minutes = 0
            if record.joined_at:
                end_time = session.end_time or now_utc
                duration_minutes = (end_time - record.joined_at).total_seconds() / 60
                
                # Consider student attended if they participated for at least 50% of session
                session_duration = (session.end_time - session.start_time).total_seconds() / 60
                status = 'present' if duration_minutes >= (session_duration * 0.5) else 'absent'
                
                record.duration = duration_minutes
                record.status = status
                
                # Notify student if they were marked present
                if status == 'present':
                    Notification.create_for_user(
                        user_id=record.student.user_id,
                        title="Attendance Recorded",
                        message=f"You attended {session.session_name} for {int(duration_minutes)} minutes",
                        link=f"/my-attendance",
                        notification_type='attendance',
                        related_id=session.id
                    )

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Attendance finalized for {len(participations)} students'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Finalize attendance error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def finalize_completed_sessions():
    """Check for completed sessions and finalize attendance"""
    with app.app_context():
        try:
            now_utc = datetime.now(timezone.utc)
            completed_sessions = OnlineSession.query.filter(
                OnlineSession.end_time < now_utc,
                OnlineSession.attendance_finalized == False
            ).all()

            for session in completed_sessions:
                try:
                    # Call our finalize endpoint
                    with app.test_client() as client:
                        client.post(
                            f'/finalize_attendance/{session.id}',
                            headers={'X-CSRFToken': 'internal-call'}
                        )
                    
                    session.attendance_finalized = True
                    db.session.commit()
                    
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error finalizing session {session.id}: {str(e)}")

        except Exception as e:
            current_app.logger.error(f"Error in finalize_completed_sessions: {str(e)}")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(finalize_completed_sessions, 'interval', minutes=5)
scheduler.start()
# Get attendance records


@app.route('/attendance/view')
@app.route('/attendance/view/<int:session_id>')
@login_required
def view_attendance(session_id=None):
    if current_user.role != 'teacher':
        abort(403)
    
    if session_id is None:
        # Get all sessions for the current teacher
        sessions = OnlineSession.query\
            .filter_by(creator_id=current_user.id)\
            .order_by(OnlineSession.start_time.desc())\
            .all()
        
        if not sessions:
            flash("No sessions found", "warning")
            return redirect(url_for('teacher_dashboard'))
        
        # Redirect to the most recent session
        return redirect(url_for('view_attendance', session_id=sessions[0].id))
    
    # Get the specific session with ownership check
    session = OnlineSession.query.filter_by(
        id=session_id,
        creator_id=current_user.id
    ).first_or_404()
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(session_id=session_id)\
        .join(Student, Attendance.student_id == Student.id)\
        .order_by(Attendance.date.desc())\
        .all()
    
    # Get all teacher sessions for the filter dropdown
    teacher_sessions = OnlineSession.query\
        .filter_by(creator_id=current_user.id)\
        .order_by(OnlineSession.start_time.desc())\
        .all()
    
    return render_template(
        'teacher/attendance/attendance_view.html',
        attendance_records=attendance_records,
        session=session,
        teacher_sessions=teacher_sessions
    )

@app.route('/attendance/filter', methods=['POST'])
@login_required
def filter_attendance():
    if current_user.role != 'teacher':
        abort(403)
    
    filters = request.form
    
    # Base query with teacher restriction
    query = Attendance.query\
        .join(OnlineSession, Attendance.session_id == OnlineSession.id)\
        .join(Student, Attendance.student_id == Student.id)\
        .filter(OnlineSession.creator_id == current_user.id)
    
    # Apply filters
    if filters.get('start_date'):
        query = query.filter(Attendance.date >= filters['start_date'])
    if filters.get('end_date'):
        query = query.filter(Attendance.date <= filters['end_date'])
    if filters.get('session_id'):
        query = query.filter(Attendance.session_id == filters['session_id'])
    if filters.get('status'):
        query = query.filter(Attendance.status == filters['status'])
    
    records = query.order_by(Attendance.date.desc()).all()
    
    formatted_data = [{
        'id': record.id,
        'student_name': record.student.full_name,
        'session_name': record.session.session_name,
        'date': record.date.strftime('%Y-%m-%d'),
        'time_in': record.joined_at.strftime('%H:%M') if record.joined_at else None,
        'duration': record.duration,
        'status': record.status
    } for record in records]
    
    return jsonify({
        'success': True,
        'data': formatted_data,
        'count': len(formatted_data)
    })

@app.route('/attendance/export/<string:format>')
@login_required
def export_attendance(format):
    if current_user.role != 'teacher':
        abort(403)
    
    records = Attendance.query\
        .join(OnlineSession, Attendance.session_id == OnlineSession.id)\
        .filter(OnlineSession.creator_id == current_user.id)\
        .order_by(Attendance.date.desc())\
        .all()
    
    filename = f"attendance_{datetime.now().strftime('%Y%m%d')}"
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student Name', 'Session', 'Date', 'Time In', 'Duration (mins)', 'Status'])
        
        for record in records:
            writer.writerow([
                record.student.full_name,
                record.session.session_name,
                record.date.strftime('%Y-%m-%d'),
                record.joined_at.strftime('%H:%M') if record.joined_at else 'N/A',
                record.duration,
                record.status.capitalize()
            ])
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}.csv'
        response.headers['Content-type'] = 'text/csv'
        return response
    
    elif format == 'excel':
        try:
            import pandas as pd
            
            data = [{
                'Student Name': record.student.full_name,
                'Session': record.session.session_name,
                'Date': record.date.strftime('%Y-%m-%d'),
                'Time In': record.joined_at.strftime('%H:%M') if record.joined_at else 'N/A',
                'Duration (mins)': record.duration,
                'Status': record.status.capitalize()
            } for record in records]
            
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Attendance')
                writer.save()
            
            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = f'attachment; filename={filename}.xlsx'
            response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            return response
            
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Excel export requires pandas library'
            }), 400
    
    return jsonify({
        'success': False,
        'error': f'Invalid export format: {format}. Supported formats: csv, excel'
    }), 400


@app.route('/notify_video_join', methods=['POST'])
@login_required
def notify_video_join():
    """Handle student join notifications from video session"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        student_name = data.get('student_name')
        session_id = data.get('session_id')
        session_name = data.get('session_name')
        
        if not all([student_id, student_name, session_id, session_name]):
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
            
        session = OnlineSession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Invalid session'}), 404
            
        # Create notification
        notification = Notification.create_for_user(
            user_id=session.teacher_id,
            title="Student Joined Video Session",
            message=f"{student_name} joined {session_name}",
            link=f"/sessions/{session_id}",
            notification_type='video_join',
            related_id=session_id
        )
        
        # Broadcast via SocketIO
        socketio.emit('video_join_notification', {
            'student_name': student_name,
            'session_name': session_name,
            'session_id': session_id,
            'notification_id': notification.id
        }, room=f"teacher_{session.teacher_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Video join notification error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------- NOTIFICATION ROUTES ----------

@app.route('/notifications', methods=['GET'])
@login_required
def notifications():
    """Render notifications HTML page with paginated notifications"""
    try:
        # Validate and parse request parameters
        page = request.args.get('page', 1, type=int)
        if page < 1:
            page = 1
            
        per_page = request.args.get('per_page', 20, type=int)
        if per_page not in [10, 20, 50, 100]:
            per_page = 20
            
        # Initialize base query
        query = Notification.query.filter_by(user_id=current_user.id)
        
        # Apply filters
        query = apply_notification_filters(query)
        
        # Apply sorting
        query = apply_notification_sorting(query)
        
        # Paginate results
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Process notifications
        processed_notifications = process_notifications(paginated.items)
        
        # Prepare context
        context = build_notification_context(
            notifications=processed_notifications,
            pagination=paginated,
            request_args=request.args
        )
        
        return render_template('teacher/notifications/notification.html', **context)
        
    except Exception as e:
        current_app.logger.error(f"Notifications error: {str(e)}", exc_info=True)
        flash('Failed to load notifications. Please try again.', 'error')
        return redirect(url_for('teacher_dashboard'))

# Helper functions
def apply_notification_filters(query):
    """Apply filters to the notification query"""
    # Type filter
    if notification_type := request.args.get('type'):
        if notification_type != 'all':
            query = query.filter_by(notification_type=notification_type)
    
    # Status filter
    if status := request.args.get('status'):
        if status == 'unread':
            query = query.filter_by(is_read=False)
        elif status == 'read':
            query = query.filter_by(is_read=True)
    
    # Time range filter
    if time_range := request.args.get('time_range'):
        now = datetime.utcnow()
        if time_range == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Notification.created_at >= start)
        elif time_range == 'week':
            query = query.filter(Notification.created_at >= (now - timedelta(days=7)))
        elif time_range == 'month':
            query = query.filter(Notification.created_at >= (now - timedelta(days=30)))
    
    return query

def apply_notification_sorting(query):
    """Apply sorting to the notification query"""
    sort_by = request.args.get('sort_by', 'newest')
    
    if sort_by == 'newest':
        return query.order_by(
            Notification.is_read,
            Notification.created_at.desc()
        )
    elif sort_by == 'oldest':
        return query.order_by(Notification.created_at.asc())
    elif sort_by == 'priority':
        return query.order_by(
            Notification.priority.desc(),
            Notification.is_read,
            Notification.created_at.desc()
        )
    return query

def process_notifications(notifications):
    """Process and format notification data"""
    processed = []
    for notification in notifications:
        try:
            note = notification.to_dict()
            
            # Ensure proper datetime format
            if isinstance(note.get('created_at'), str):
                note['created_at'] = parse_iso_datetime(note['created_at'])
            
            # Clean message content
            note['message'] = clean_notification_message(note.get('message', ''))
            
            processed.append(note)
        except Exception as e:
            current_app.logger.warning(f"Failed to process notification {notification.id}: {e}")
            continue
            
    return processed

def clean_notification_message(message):
    """Clean up notification message content"""
    if "bound method Student.full_name" in message:
        try:
            match = re.search(r"<Student (.*?) \(", message)
            if match:
                return message.replace(
                    f"<bound method Student.full_name of <Student {match.group(1)}",
                    match.group(1))
        except Exception as e:
            current_app.logger.warning(f"Message cleaning failed: {e}")
    return message

def parse_iso_datetime(dt_str):
    """Parse ISO format datetime string"""
    try:
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S')
    except (ValueError, TypeError):
        return datetime.utcnow()

def build_notification_context(**kwargs):
    """Build template context dictionary"""
    request_args = kwargs.get('request_args', {})
    
    return {
        'notifications': kwargs.get('notifications', []),
        'pagination': kwargs.get('pagination'),
        'total_count': kwargs.get('pagination').total if kwargs.get('pagination') else 0,
        'unread_count': Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count(),
        'current_page': kwargs.get('pagination').page if kwargs.get('pagination') else 1,
        'current_per_page': request_args.get('per_page', 20),
        'current_type': request_args.get('type', 'all'),
        'current_status': request_args.get('status', 'all'),
        'current_time_range': request_args.get('time_range', 'all'),
        'current_sort_by': request_args.get('sort_by', 'newest'),
        'now': datetime.utcnow()
    }

# Keep your existing API endpoint
@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    """Get all notifications for current user (API endpoint)"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Base query
        notifications_query = Notification.query.filter_by(
            user_id=current_user.id
        )
        
        # Apply filters if provided
        notification_type = request.args.get('type')
        if notification_type and notification_type != 'all':
            notifications_query = notifications_query.filter_by(
                notification_type=notification_type
            )
            
        status = request.args.get('status')
        if status == 'unread':
            notifications_query = notifications_query.filter_by(is_read=False)
        elif status == 'read':
            notifications_query = notifications_query.filter_by(is_read=True)
            
        time_range = request.args.get('time_range')
        if time_range:
            now = datetime.utcnow()
            if time_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                notifications_query = notifications_query.filter(
                    Notification.created_at >= start_date
                )
            elif time_range == 'week':
                start_date = now - timedelta(days=7)
                notifications_query = notifications_query.filter(
                    Notification.created_at >= start_date
                )
            elif time_range == 'month':
                start_date = now - timedelta(days=30)
                notifications_query = notifications_query.filter(
                    Notification.created_at >= start_date
                )
        
        # Apply sorting
        sort_by = request.args.get('sort_by', 'newest')
        if sort_by == 'newest':
            notifications_query = notifications_query.order_by(
                Notification.is_read,
                Notification.created_at.desc()
            )
        elif sort_by == 'oldest':
            notifications_query = notifications_query.order_by(
                Notification.created_at.asc()
            )
        elif sort_by == 'priority':
            notifications_query = notifications_query.order_by(
                Notification.priority.desc(),
                Notification.is_read,
                Notification.created_at.desc()
            )
        
        # Paginate results
        paginated_notifications = notifications_query.paginate(
            page=page, 
            per_page=per_page,
            error_out=False
        )
        
        # Clean up notification messages
        cleaned_notifications = []
        for notification in paginated_notifications.items:
            notification_dict = notification.to_dict()
            
            # Fix the student name format if present
            if "bound method Student.full_name" in notification_dict['message']:
                try:
                    # Extract student name using regex
                    student_match = re.search(r"<Student (.*?) \(", notification_dict['message'])
                    if student_match:
                        student_name = student_match.group(1)
                        notification_dict['message'] = notification_dict['message'].replace(
                            f"<bound method Student.full_name of <Student {student_name}",
                            student_name
                        )
                except Exception as e:
                    current_app.logger.error(f"Error cleaning notification message: {str(e)}")
                    # Keep original message if cleaning fails
                    
            cleaned_notifications.append(notification_dict)
        
        return jsonify({
            'success': True,
            'notifications': cleaned_notifications,
            'total_count': notifications_query.count(),
            'unread_count': Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count(),
            'page': paginated_notifications.page,
            'pages': paginated_notifications.pages
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching notifications: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Error fetching notifications',
            'error': str(e)
        }), 500
    

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notification_as_read():
    """Mark a notification as read"""
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({'success': False, 'message': 'Notification ID is required'}), 400
        
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if not notification:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'unread_count': Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking notification as read: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating notification'}), 500
    
@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_as_read():
    """Mark all notifications as read for current user"""
    try:
        updated_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        db.session.commit()
        
        return jsonify({
            'success': True,
            'marked_read': updated_count,
            'unread_count': 0
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking all notifications as read: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating notifications'}), 500

    

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notification_read():
    """Mark a notification as read"""
    try:
        data = request.get_json()
        notification = Notification.query.get(data.get('notification_id'))
        
        if not notification or notification.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
        notification.mark_as_read()
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error marking notification read: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating notification'}), 500


@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error marking all notifications read: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating notifications'}), 500


@app.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a specific notification"""
    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first()
        
        if not notification:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'unread_count': Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting notification: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting notification'}), 500


@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """Delete all notifications for current user"""
    try:
        deleted_count = Notification.query.filter_by(
            user_id=current_user.id
        ).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'unread_count': 0
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing all notifications: {str(e)}")
        return jsonify({'success': False, 'message': 'Error clearing notifications'}), 500


@app.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread notifications for current user"""
    try:
        count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching unread count: {str(e)}")
        return jsonify({'success': False, 'message': 'Error fetching unread count'}), 500
    
@app.route('/api/notifications/settings', methods=['GET', 'POST'])
@login_required
def notification_settings():
    """Get or update notification settings for current user"""
    try:
        if request.method == 'GET':
            # Return current settings
            settings = NotificationSettings.query.filter_by(
                user_id=current_user.id
            ).first()
            
            if not settings:
                # Return default settings if none exist
                return jsonify({
                    'success': True,
                    'settings': {
                        'email_enabled': True,
                        'push_enabled': True,
                        'desktop_enabled': True,
                        'frequency': 'immediate',
                        'types': ['assignment', 'message', 'attendance', 'system']
                    }
                })
            
            return jsonify({
                'success': True,
                'settings': settings.to_dict()
            })
            
        elif request.method == 'POST':
            # Update settings
            data = request.get_json()
            settings = NotificationSettings.query.filter_by(
                user_id=current_user.id
            ).first()
            
            if not settings:
                settings = NotificationSettings(user_id=current_user.id)
                db.session.add(settings)
            
            settings.email_enabled = data.get('email_enabled', True)
            settings.push_enabled = data.get('push_enabled', True)
            settings.desktop_enabled = data.get('desktop_enabled', True)
            settings.frequency = data.get('frequency', 'immediate')
            settings.types = data.get('types', ['assignment', 'message', 'attendance', 'system'])
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Notification settings updated'
            })
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error with notification settings: {str(e)}")
        return jsonify({'success': False, 'message': 'Error processing notification settings'}), 500


# ---------- STUDENT CLASSES ROUTES ----------
@app.route('/student/classes')
@login_required
def student_classes():
    """Display all classes the student is enrolled in"""
    if current_user.role != 'student':
        flash('Access restricted to students', 'danger')
        return redirect(url_for('stduent_dashboard'))
    
    if not current_user.student_profile:
        flash('Student profile not found', 'danger')
        return redirect(url_for('student_dashboard'))
    
    enrollments = (db.session.query(Enrollment)
        .join(Classroom)
        .filter(
            Enrollment.student_id == current_user.student_profile.id,
            Enrollment.is_dropped == False
        )
        .order_by(Classroom.class_name)
        .all())
    
    return render_template(
        'student/student_classes.html',
        enrollments=enrollments
    )


@app.route('/class/<int:class_id>/sessions')
@login_required
def class_sessions(class_id):
    # Verify enrollment
    if current_user.role == 'student':
        if not any(e.class_id == class_id for e in current_user.student_profile.enrollments):
            flash('You are not enrolled in this class', 'danger')
            return redirect(url_for('student_dashboard'))

    class_obj = Classroom.query.get_or_404(class_id)
    now = datetime.now(timezone.utc)
    
    # Get sessions with proper timezone handling
    sessions = (OnlineSession.query
        .filter_by(class_id=class_id)
        .order_by(OnlineSession.start_time.desc())
        .all())
    
    enhanced_sessions = []
    for session in sessions:
        try:
            start_local, end_local = session.get_local_times()
            status = session.get_status(now)
            
            enhanced_sessions.append({
                'id': session.id,
                'session_name': session.session_name,
                'description': session.description,
                'start_time': start_local,
                'end_time': end_local,
                'time_range': session.get_local_time_range(),
                'status': status,
                'is_valid': session.is_valid,
                'teacher': {
                    'id': session.creator.id,
                    'name': session.creator.get_full_name(),
                    'image': session.creator.profile_image_url or url_for('static', filename='img/default-profile.png')
                },
                'room_id': session.room_id,
                'recording_url': session.recording_url
            })
        except Exception as e:
            current_app.logger.error(f"Error processing session {session.id}: {e}")
            continue

    return render_template(
        'student/class_sessions.html',
        classroom=class_obj,
        sessions=enhanced_sessions,
        now_utc=now
    )


@app.route('/api/class/<int:class_id>/sessions')
@login_required
def api_class_sessions(class_id):
    """API endpoint for class sessions data"""
    if current_user.role == 'student':
        if not any(e.class_id == class_id for e in current_user.student_profile.enrollments):
            return jsonify({'error': 'Not enrolled'}), 403

    sessions = (OnlineSession.query
        .filter_by(class_id=class_id)
        .order_by(OnlineSession.start_time.desc())
        .all())

    now = datetime.now(timezone.utc)
    enhanced_sessions = []
    for session in sessions:
        enhanced_sessions.append({
            'id': session.id,
            'name': session.session_name,
            'start': session.start_time.isoformat(),
            'end': session.end_time.isoformat(),
            'status': session.get_status(now),
            'room_id': session.room_id,
            'recording_url': session.recording_url
        })

    return jsonify({'sessions': enhanced_sessions})


@app.route('/server_time')
def server_time():
    """Display server time in UTC and local time for verification"""
    utc_now = now_utc()
    local_now = to_local_time(utc_now)
    
    return jsonify({
        "Server Time (UTC)": format_datetime(utc_now, tz=pytz.utc),
        "Africa/Dar_es_Salaam Time": format_datetime(utc_now),
        "Current UTC Timestamp": utc_now.timestamp(),
        "Current Local Timestamp": local_now.timestamp(),
        "Timezone Info": {
            "Server Timezone": str(utc_now.tzinfo),
            "Local Timezone": str(local_now.tzinfo),
            "UTC Offset": local_now.utcoffset().total_seconds()/3600
        }
    })

def now_utc():
    """Get current time in UTC"""
    return datetime.now(timezone.utc)

def to_local_time(utc_dt, tz=None):
    """Convert UTC datetime to local time"""
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(tz or local_tz)

def format_datetime(dt, format_str='%B %d, %Y %H:%M:%S', tz=None):
    """Format datetime in specified timezone"""
    if not dt:
        return "Not set"
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(tz or local_tz).strftime(format_str)

# ---------- USER MANAGEMENT ROUTES ----------

@app.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    """
    Add a new student (restricted to teachers in their own department).
    Handles both displaying the form and processing student creation.
    """
    
    # ======================
    # 1. Authorization Check
    # ======================
    if current_user.role != 'teacher':
        flash('Access denied. Only teachers can add students.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    # ==============================
    # 2. Get Teacher and Department
    # ==============================
    try:
        teacher = current_user.teacher_profile
        if not teacher or not teacher.department:
            flash('Teacher department not found', 'danger')
            return redirect(url_for('teacher_dashboard'))

        department = teacher.department
    except Exception as e:
        flash('Error accessing teacher information', 'danger')
        app.logger.error(f"Teacher info error: {str(e)}")
        return redirect(url_for('teacher_dashboard'))

    # ==============================
    # 3. Prepare Data for Template
    # ==============================
    try:
        # Get students in the department with related data
        students = Student.query.filter_by(
            department_id=department.id
        ).options(
            db.joinedload(Student.user),
            db.joinedload(Student.department),
            db.joinedload(Student.enrollments)
                .joinedload(Enrollment.classroom)
                .joinedload(Classroom.subject)
        ).all()

        # Get classes for the form dropdown
        classes = Classroom.query.join(Subject).filter(
            Subject.department_id == department.id
        ).all()

    except Exception as e:
        flash('Error loading student data', 'danger')
        app.logger.error(f"Data loading error: {str(e)}")
        students = []
        classes = []

    # =====================
    # 4. Handle POST Request
    # =====================
    if request.method == 'POST':
        # 4.1 Collect Form Data
        form_data = {
            'first_name': request.form.get('first_name', '').strip(),
            'last_name': request.form.get('last_name', '').strip(),
            'username': request.form.get('username', '').strip(),
            'email': request.form.get('email', '').strip().lower(),
            'password': request.form.get('password', ''),
            'date_of_birth': request.form.get('date_of_birth'),
            'class_id': request.form.get('class_id')
        }

        # 4.2 Validate Form Data
        errors = []
        
        # Required fields check
        required_fields = [
            ('first_name', 'First name'),
            ('last_name', 'Last name'),
            ('username', 'Username'),
            ('email', 'Email'),
            ('password', 'Password'),
            ('date_of_birth', 'Date of birth'),
            ('class_id', 'Class')
        ]
        
        for field, name in required_fields:
            if not form_data.get(field):
                errors.append(f'{name} is required')

        # Additional validations
        if not errors:
            if User.query.filter_by(username=form_data['username']).first():
                errors.append('Username already exists')
            
            if User.query.filter_by(email=form_data['email']).first():
                errors.append('Email already registered')
            
            if len(form_data['password']) < 8:
                errors.append('Password must be at least 8 characters')
            
            try:
                dob = datetime.strptime(form_data['date_of_birth'], '%Y-%m-%d').date()
                if dob >= datetime.now().date():
                    errors.append('Invalid date of birth')
            except ValueError:
                errors.append('Invalid date format')

        # 4.3 Handle Validation Errors
        if errors:
            flash('; '.join(errors), 'danger')
            return render_template('teacher/add_student.html',
                               students=students,
                               classes=classes,
                               teacher_dept=department,
                               form_data=form_data,
                               today=datetime.now().date())

        # 4.4 Create New Student
        try:
            # Start transaction
            with db.session.begin_nested():
                # Create user account
                new_user = User(
                    username=form_data['username'],
                    email=form_data['email'],
                    password=generate_password_hash(form_data['password']),
                    role='student',
                    is_active=True
                )
                db.session.add(new_user)
                db.session.flush()  # Get the new user ID

                # Create student profile
                student_id = f"STU{datetime.now().year % 100:02d}{new_user.id:05d}"
                new_student = Student(
                    user_id=new_user.id,
                    first_name=form_data['first_name'],
                    last_name=form_data['last_name'],
                    student_id=student_id,
                    date_of_birth=dob,
                    department_id=department.id
                )
                db.session.add(new_student)
                db.session.flush()

                # Create enrollment
                enrollment = Enrollment(
                    class_id=form_data['class_id'],
                    student_id=new_student.id
                )
                db.session.add(enrollment)

            db.session.commit()
            flash(f'Student {student_id} added successfully!', 'success')
            return redirect(url_for('add_student'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adding student: {str(e)}', 'danger')
            app.logger.error(f"Student creation failed: {str(e)}")
            return render_template('teacher/add_student.html',
                               students=students,
                               classes=classes,
                               teacher_dept=department,
                               form_data=form_data,
                               today=datetime.now().date())

    # ====================
    # 5. Handle GET Request
    # ====================
    return render_template('teacher/add_student.html',
                         students=students,
                         classes=classes,
                         teacher_dept=department,
                         today=datetime.now().date())

@app.route('/edit_student', methods=['POST'])
@login_required
def edit_student():
    """Edit student details (admin only)."""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    user_id = request.form.get('user_id')
    department_id = request.form.get('department_id')
    class_id = request.form.get('class_id')

    student = User.query.get_or_404(user_id)
    
    if department_id:
        student.department_id = department_id
    if class_id:
        student.class_id = class_id

    db.session.commit()
    flash('Student details updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/manage_students', methods=['GET', 'POST'])
def manage_students():
    """Manage students (admin only)."""
    try:
        students = Student.query.all()
        departments = Department.query.all()
        classes = Enrollment.query.all()

        if request.method == 'POST':
            student_id = request.form.get('student_id')
            department_id = request.form.get('department_id')
            class_id = request.form.get('class_id')

            if not student_id:
                flash('Student ID is required.', 'danger')
                return redirect(url_for('manage_students'))

            student = Student.query.get(student_id)
            if student:
                department = Department.query.get(department_id)
                class_ = Enrollment.query.get(class_id)

                if department and class_:
                    student.department_id = department_id
                    student.class_id = class_id
                    db.session.commit()
                    flash('Student updated successfully!', 'success')
                else:
                    flash('Invalid department or class selection.', 'error')
            else:
                flash('Student not found.', 'error')

            return redirect(url_for('manage_students'))

        return render_template(
            'admin/manage_students.html',
            students=students,
            departments=departments,
            classes=classes
        )
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
        return redirect(url_for('admin_dashboard'))
    
@app.route('/add_teacher', methods=['GET', 'POST'])
@login_required
def add_teacher():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    departments = Department.query.all()
    subjects = Subject.query.order_by(Subject.name).all()
    form_data = {}

    if request.method == 'POST':
        form_data = {
            'username': request.form.get('username', '').strip(),
            'email': request.form.get('email', '').strip(),
            'password': request.form.get('password', '').strip(),
            'confirm_password': request.form.get('confirm_password', '').strip(),
            'teacher_name': request.form.get('teacher_name', '').strip(),  # Changed from teacher_name to teacher_name
            'specialization': request.form.get('specialization', '').strip(),
            'department_id': request.form.get('department', '').strip(),
            'subjects': request.form.getlist('subjects')
        }

        # Validation
        errors = []
        required_fields = ['username', 'email', 'password', 'confirm_password', 'teacher_name', 'department_id']
        for field in required_fields:
            if not form_data[field]:
                errors.append(f"{field.replace('_', ' ').title()} is required")

        if form_data['password'] != form_data['confirm_password']:
            errors.append("Passwords do not match")

        if User.query.filter_by(username=form_data['username']).first():
            errors.append("Username already exists")

        if User.query.filter_by(email=form_data['email']).first():
            errors.append("Email already exists")

        if not errors:
            try:
                # Create user
                new_user = User(
                    username=form_data['username'],
                    email=form_data['email'],
                    password=generate_password_hash(form_data['password'], method='pbkdf2:sha256'),
                    role='teacher'
                )
                db.session.add(new_user)
                db.session.flush()

                # Create teacher - using user's username if teacher_name doesn't exist
                new_teacher = Teacher(
                    user_id=new_user.id,
                    department_id=int(form_data['department_id']),
                    specialization=form_data['specialization'],
                    teacher_name=form_data.get('teacher_name', form_data['username'])  # Fallback to username
                )
                db.session.add(new_teacher)
                db.session.flush()

                # Add selected subjects
                for subject_id in form_data['subjects']:
                    subject = Subject.query.get(subject_id)
                    if subject:
                        new_teacher.subjects.append(subject)

                db.session.commit()
                flash('Teacher added successfully!', 'success')
                return redirect(url_for('add_teacher'))

            except Exception as e:
                db.session.rollback()
                flash(f'Error: {str(e)}', 'danger')
        else:
            for error in errors:
                flash(error, 'danger')

    teachers = Teacher.query.options(
        db.joinedload(Teacher.user),
        db.joinedload(Teacher.department),
        db.joinedload(Teacher.subjects)
    ).all()

    return render_template('admin/add_teacher.html',
                         departments=departments,
                         subjects=subjects,
                         teachers=teachers,
                         form_data=form_data)

# ---------- DEPARTMENT/CLASS/SUBJECT MANAGEMENT ----------

@app.route('/add_department', methods=['GET', 'POST'])
@login_required
def add_department():
    """Add a new department (admin only)."""
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name').strip()
        description = request.form.get('description').strip()

        if Department.query.filter_by(name=name).first():
            flash('Department already exists!', 'danger')
        else:
            new_department = Department(name=name, description=description)
            db.session.add(new_department)
            db.session.commit()
            flash('Department added successfully!', 'success')

    return render_template('admin/add_department.html')

@app.route('/departments', methods=['GET'])
@login_required
def view_departments():
    """View all departments (admin only)."""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    departments = Department.query.all()
    return render_template('admin/view_departments.html', departments=departments)

@app.route('/add_class', methods=['GET', 'POST'])
@login_required
def add_class():
    """Add a new class (admin only)."""
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    teachers = Teacher.query.options(db.joinedload(Teacher.user)).all()
    subjects = Subject.query.all()
    current_year = datetime.now().year
    academic_years = [f"{year}-{year+1}" for year in range(current_year-1, current_year+3)]
    semesters = [1, 2, 3]

    if request.method == 'POST':
        try:
            form_data = {
                'class_name': request.form.get('class_name', '').strip(),
                'subject_id': request.form.get('subject_id'),
                'teacher_id': request.form.get('teacher_id'),
                'academic_year': request.form.get('academic_year'),
                'semester': request.form.get('semester'),
                'section': request.form.get('section', '').strip(),
                'room_number': request.form.get('room_number', '').strip(),
                'description': request.form.get('description', '').strip(),
                'max_students': request.form.get('max_students', 30)
            }

            # Validate required fields
            required_fields = ['class_name', 'subject_id', 'teacher_id', 'academic_year', 'semester']
            if not all(form_data[field] for field in required_fields):
                flash('All required fields must be filled', 'danger')
                return redirect(url_for('add_class'))

            # Check if teacher and subject exist
            teacher = Teacher.query.get(form_data['teacher_id'])
            subject = Subject.query.get(form_data['subject_id'])
            if not teacher or not subject:
                flash('Invalid teacher or subject selected', 'danger')
                return redirect(url_for('add_class'))

            # Check for duplicate class
            exists = Classroom.query.filter(
                db.func.lower(Classroom.class_name) == form_data['class_name'].lower(),
                Classroom.academic_year == form_data['academic_year'],
                Classroom.semester == int(form_data['semester'])
            ).first()
            
            if exists:
                flash(f'A class with this name already exists for {form_data["academic_year"]} semester {form_data["semester"]}', 'danger')
                return redirect(url_for('add_class'))

            # Create new class
            new_class = Classroom(
                class_name=form_data['class_name'],
                subject_id=form_data['subject_id'],
                teacher_id=form_data['teacher_id'],
                academic_year=form_data['academic_year'],
                semester=int(form_data['semester']),
                section=form_data['section'],
                room_number=form_data['room_number'],
                description=form_data['description'],
                max_students=int(form_data['max_students']),
                is_active=True
            )

            db.session.add(new_class)
            db.session.flush()  # Generate ID for code
            
            try:
                # Generate class code after we have an ID
                new_class.code = new_class.generate_code()
            except Exception as e:
                app.logger.warning(f"Couldn't generate class code: {str(e)}")
                # Fallback code if generation fails
                new_class.code = f"CLS-{new_class.academic_year.replace('-', '')[:4]}-{new_class.semester}-{new_class.id:03d}"
            
            db.session.commit()
            flash(f'Class "{new_class.class_name}" added successfully! Code: {new_class.code}', 'success')
            return redirect(url_for('add_class'))

        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid data: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding class: {str(e)}", exc_info=True)
            flash('An error occurred while adding the class', 'danger')

    classrooms = Classroom.query.options(
        db.joinedload(Classroom.subject),
        db.joinedload(Classroom.teacher).joinedload(Teacher.user)
    ).order_by(
        Classroom.academic_year.desc(),
        Classroom.semester.desc(),
        Classroom.class_name
    ).all()

    return render_template('admin/add_class.html',
                         teachers=teachers,
                         subjects=subjects,
                         academic_years=academic_years,
                         semesters=semesters,
                         classrooms=classrooms)

@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    """Add a new subject (admin only)."""
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    departments = Department.query.all()

    if request.method == 'POST':
        subject_name = request.form.get('subject_name', '').strip()
        subject_description = request.form.get('subject_description', '').strip()
        department_id = request.form.get('department_id')

        if not all([subject_name, subject_description, department_id]):
            flash('All fields are required. Please fill out the form correctly.', 'danger')
        else:
            department = Department.query.get(department_id)
            if not department:
                flash('Invalid department selected.', 'danger')
            elif Subject.query.filter(Subject.name.ilike(subject_name)).first():
                flash(f'A subject with the name "{subject_name}" already exists!', 'danger')
            else:
                new_subject = Subject(
                    name=subject_name,
                    description=subject_description,
                    department_id=department_id
                )
                db.session.add(new_subject)
                db.session.commit()
                flash(f'Subject "{subject_name}" added successfully!', 'success')
                return redirect(url_for('add_subject'))

    return render_template('admin/subjects.html', departments=departments)

# TEACHER SUBJECTS ROUTES

@app.route('/teacher/subjects')
@login_required
def teacher_subjects():
    if not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    teacher = current_user.teacher_profile
    subjects = teacher.get_all_subjects()
    
    if not subjects:
        flash("You are not currently assigned to teach any subjects. Please contact your administrator.", 'info')
        return render_template('teacher/subjects.html', 
                           subjects=[], 
                           show_contact=True,
                           teacher=teacher)
    
    # Prepare subject data with statistics
    subject_data = []
    for subject in subjects:
        stats = teacher.get_subject_stats(subject.id)
        subject_data.append({
            'subject': subject,
            'stats': stats,
            'classrooms': [c for c in teacher.classrooms if c.subject_id == subject.id]
        })
    
    return render_template('teacher/subjects.html',
                         subjects=subject_data,
                         teacher=teacher)

@app.route('/subject/<int:subject_id>/assignments')
@login_required
def subject_assignments(subject_id):
    """View assignments for a specific subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify teacher has access to this subject
    if not Classroom.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first():
        flash('You are not assigned to teach this subject.', 'danger')
        return redirect(url_for('teacher_subjects'))
    
    assignments = Assignment.query.filter_by(subject_id=subject_id).all()
    return render_template('teacher/subjects.html', 
                         subject=subject,
                         assignments=assignments)

@app.route('/subject/<int:subject_id>/quizzes')
@login_required
def subject_quizzes(subject_id):
    """View quizzes for a specific subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    if not Classroom.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first():
        flash('You are not assigned to teach this subject.', 'danger')
        return redirect(url_for('teacher_subjects'))
    
    quizzes = Quiz.query.filter_by(subject_id=subject_id).all()
    return render_template('teacher/quizzes/view.html',
                         subject=subject,
                         quizzes=quizzes)

@app.route('/subject/<int:subject_id>/resources')
@login_required
def subject_resources(subject_id):
    """View resources for a specific subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    if not Classroom.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first():
        flash('You are not assigned to teach this subject.', 'danger')
        return redirect(url_for('teacher_subjects'))
    
    resources = Resource.query.filter_by(subject_id=subject_id).all()
    return render_template('teacher/resources/view_resources.html',
                         subject=subject,
                         resources=resources)

# ---------- ASSIGNMENT/QUIZ ROUTES ----------

# ---------- ASSIGNMENT ROUTES ----------

@app.route('/assignments')
@login_required
def list_assignments():
    """List all assignments for the current user."""
    # Set default timezone
    user_timezone = pytz.timezone(getattr(current_user, 'timezone', 'Africa/Dar_es_Salaam'))
    
    # Get current time (timezone-aware)
    now_utc = datetime.now(pytz.utc)
    now_user_tz = now_utc.astimezone(user_timezone)
    
    if current_user.role == 'teacher':
        assignments = Assignment.query.filter_by(author_id=current_user.id)\
                                   .options(
                                       joinedload(Assignment.submissions),
                                       joinedload(Assignment.subject),
                                       joinedload(Assignment.classroom)
                                   )\
                                   .order_by(Assignment.due_date.desc())\
                                   .all()
        
        # Make all due dates timezone-aware
        for assignment in assignments:
            if assignment.due_date:
                if assignment.due_date.tzinfo is None:
                    assignment.due_date = pytz.utc.localize(assignment.due_date)
                assignment.due_date = assignment.due_date.astimezone(user_timezone)
        
        return render_template('teacher/assignments/list.html',
                            assignments=assignments,
                            now=now_user_tz,
                            user_timezone=user_timezone.zone)
    
    # Similar handling for student view
    elif current_user.role == 'student':
        # ... [student view code] ...
        return render_template('student/assignments/list.html',
                            assignments=assignments,
                            submissions={},  # Replace with an appropriate value or query
                            now=now_user_tz,
                            user_timezone=user_timezone.zone)

@app.route('/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    """View assignment details with access control and grading."""
    try:
        # Load assignment with optimized queries
        assignment = Assignment.query.options(
            joinedload(Assignment.subject),
            joinedload(Assignment.classroom),
            joinedload(Assignment.author),
            joinedload(Assignment.submissions)
        ).get_or_404(assignment_id)

        # Parse questions safely
        questions = []
        if assignment.questions:
            try:
                questions = json.loads(assignment.questions)
            except json.JSONDecodeError:
                current_app.logger.error(f"Invalid questions JSON for assignment {assignment_id}")
                questions = []

        # Handle timezone conversion
        user_tz = pytz.timezone(getattr(current_user, 'timezone', 'UTC'))
        now = datetime.now(pytz.utc).astimezone(user_tz)
        
        if assignment.due_date:
            if assignment.due_date.tzinfo is None:
                assignment.due_date = pytz.utc.localize(assignment.due_date)
            assignment.due_date = assignment.due_date.astimezone(user_tz)

        # Initialize common template variables
        template_vars = {
            'assignment': assignment,
            'questions': questions,
            'now': now,
            'submission': None,
            'submissions': [],
            'graded_count': 0,
            'total_score': 0,
            'grade_stats': None
        }

        # Student view logic
        if current_user.role == 'student':
            if not hasattr(current_user, 'student_profile'):
                flash('Student profile not found', 'danger')
                return redirect(url_for('student_dashboard'))

            enrollment = Enrollment.query.filter_by(
                student_id=current_user.student_profile.id,
                class_id=assignment.class_id,
                is_dropped=False
            ).first()

            if not enrollment or not assignment.is_published:
                flash('Access denied', 'danger')
                return redirect(url_for('student_dashboard'))

            # Find student's submission
            submission = next(
                (s for s in assignment.submissions 
                 if s.student_id == current_user.student_profile.id),
                None
            )

            if submission and submission.submitted_at:
                if submission.submitted_at.tzinfo is None:
                    submission.submitted_at = pytz.utc.localize(submission.submitted_at)
                submission.submitted_at = submission.submitted_at.astimezone(user_tz)

            template_vars['submission'] = submission
            if submission and submission.score is not None:
                template_vars['graded_count'] = 1
                template_vars['total_score'] = submission.score

        # Teacher view logic
        elif current_user.role == 'teacher':
            if assignment.author_id != current_user.id:
                flash('You can only view your own assignments', 'danger')
                return redirect(url_for('teacher_dashboard'))

            # Get all enrolled students
            students = (db.session.query(User, Student)
                .join(Student, Student.user_id == User.id)
                .join(Enrollment, Enrollment.student_id == Student.id)
                .filter(
                    Enrollment.class_id == assignment.class_id,
                    Enrollment.is_dropped == False
                )
                .order_by(Student.last_name, Student.first_name)
                .all())

            grade_stats = {
                'a_count': 0, 'b_count': 0, 'c_count': 0, 'df_count': 0,
                'a_percent': 0, 'b_percent': 0, 'c_percent': 0, 'df_percent': 0
            }

            for user, student in students:
                submission = next(
                    (s for s in assignment.submissions 
                     if s.student_id == student.id),
                    None
                )
                
                if submission and submission.submitted_at:
                    if submission.submitted_at.tzinfo is None:
                        submission.submitted_at = pytz.utc.localize(submission.submitted_at)
                    submission.submitted_at = submission.submitted_at.astimezone(user_tz)

                # Calculate grading statistics
                if submission and submission.score is not None:
                    template_vars['graded_count'] += 1
                    template_vars['total_score'] += submission.score
                    
                    percent = (submission.score / assignment.max_score) * 100
                    if percent >= 90:
                        grade_stats['a_count'] += 1
                    elif percent >= 80:
                        grade_stats['b_count'] += 1
                    elif percent >= 70:
                        grade_stats['c_count'] += 1
                    else:
                        grade_stats['df_count'] += 1

                template_vars['submissions'].append({
                    'student': {
                        'id': user.id,
                        'name': f"{student.first_name} {student.last_name}",
                        'email': user.email
                    },
                    'submission': submission
                })

            # Calculate grade distribution percentages
            total_submissions = len([s for s in template_vars['submissions'] if s['submission']])
            if total_submissions > 0:
                for grade in ['a', 'b', 'c', 'df']:
                    grade_stats[f'{grade}_percent'] = (grade_stats[f'{grade}_count'] / total_submissions) * 100

            template_vars['grade_stats'] = grade_stats
            template_vars['total_students'] = len(students)

        else:
            flash('Access denied', 'danger')
            return redirect(url_for('teacher_dashboard'))

        return render_template('teacher/assignments/assignment_details.html', **template_vars)

    except Exception as e:
        current_app.logger.error(f"Error viewing assignment {assignment_id}: {str(e)}")
        flash('An error occurred while loading the assignment', 'danger')
        return redirect(url_for('teacher_dashboard'))

@app.route('/submission/<int:submission_id>/grade', methods=['GET', 'POST'])
@login_required
def grade_submission(submission_id):
    """Grade a student submission (teacher only)."""
    if current_user.role != 'teacher':
        flash('Only teachers can grade assignments', 'danger')
        return redirect(url_for('teacher_dashboard'))

    # Load submission with all necessary relationships
    submission = Submission.query.options(
        joinedload(Submission.assignment),
        joinedload(Submission.student).joinedload(Student.user),
        joinedload(Submission.assignment).joinedload(Assignment.classroom)
    ).get_or_404(submission_id)
    
    # Verify authorization
    if submission.assignment.author_id != current_user.id:
        flash('You can only grade assignments you created', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    # Calculate statistics
    average_score = db.session.query(
        func.avg(Submission.score)
    ).filter(
        Submission.assignment_id == submission.assignment_id,
        Submission.score.isnot(None)
    ).scalar()
    
    # Check if submission is late
    is_late = False
    if submission.submitted_at and submission.assignment.due_date:
        if submission.assignment.due_date.tzinfo is None:
            submission.assignment.due_date = pytz.utc.localize(submission.assignment.due_date)
        if submission.submitted_at.tzinfo is None:
            submission.submitted_at = pytz.utc.localize(submission.submitted_at)
        is_late = submission.submitted_at > submission.assignment.due_date
    
    if request.method == 'POST':
        try:
            score = float(request.form.get('score'))
            feedback = request.form.get('feedback', '').strip()
            
            if score < 0 or score > submission.assignment.max_score:
                flash(f'Score must be between 0 and {submission.assignment.max_score}', 'danger')
            else:
                submission.score = score
                submission.feedback = feedback
                submission.graded_at = datetime.now(timezone.utc)
                db.session.commit()
                
                flash('Grade submitted successfully!', 'success')
                return redirect(url_for('view_assignment', assignment_id=submission.assignment_id))
        except ValueError:
            flash('Please enter a valid score', 'danger')
    
    return render_template('teacher/assignments/grade.html',
                         submission=submission,
                         assignment=submission.assignment,
                         student=submission.student,
                         max_score=submission.assignment.max_score,
                         average_score=average_score,
                         is_late=is_late,
                         now=datetime.now(timezone.utc))


@app.route('/assignment/<int:assignment_id>/gradebook')
@login_required
def assignment_gradebook(assignment_id):
    """View gradebook for a specific assignment with comprehensive analytics."""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Authorization checks
    if current_user.role == 'student':
        flash('You do not have permission to view gradebooks', 'danger')
        return redirect(url_for('student_dashboard'))
    
    if current_user.role == 'teacher' and assignment.author_id != current_user.id:
        flash('You can only view gradebooks for your own assignments', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    # Get active enrollments with student and user info
    query = (db.session.query(Enrollment, Student, User)
            .join(Student, Enrollment.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .filter(Enrollment.is_dropped == False,
                    Enrollment.class_id == assignment.class_id))
    
    results = query.order_by(Student.last_name, Student.first_name).all()
    
    # Get all submissions for this assignment
    submissions = {s.student_id: s for s in 
                  Submission.query.filter_by(assignment_id=assignment_id).all()}
    
    # Calculate performance metrics
    scores = [s.score for s in submissions.values() if s and s.score is not None]
    scores_sorted = sorted(scores) if scores else []
    
    # Build comprehensive gradebook data
    gradebook = []
    performance_distribution = [0, 0, 0, 0]  # For score ranges: 0-49%, 50-69%, 70-89%, 90-100%
    late_count = 0

    for enrollment, student, user in results:
        submission = submissions.get(student.id)
        score = submission.score if submission else None
        percentile = None
        is_late = False
        
        if submission and submission.submitted_at:
            # Calculate if submission is late
            is_late = submission.submitted_at > assignment.due_date
            if is_late:
                late_count += 1
            
        if score is not None:
            # Calculate percentile
            if scores_sorted:
                rank = bisect.bisect_right(scores_sorted, score)
                percentile = round((rank / len(scores_sorted)) * 100)
            
            # Update performance distribution
            percent = (score / assignment.max_score) * 100
            if percent >= 90:
                performance_distribution[3] += 1
            elif percent >= 70:
                performance_distribution[2] += 1
            elif percent >= 50:
                performance_distribution[1] += 1
            else:
                performance_distribution[0] += 1
        
        gradebook.append({
            'student': {
                'id': user.id,
                'username': user.username,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'full_name': f"{student.first_name} {student.last_name}",
                'email': user.email if current_user.role == 'admin' else None
            },
            'enrollment': enrollment,
            'submission': submission,
            'score': score,
            'percentile': percentile,
            'submitted_at': submission.submitted_at if submission else None,
            'is_late': is_late
        })
    
    # Compile comprehensive statistics
    stats = {
        'average': sum(scores)/len(scores) if scores else 0,
        'submission_rate': (len(submissions) / len(results)) * 100 if results else 0,
        'submitted_count': len(submissions),
        'pending_count': len(results) - len(submissions),
        'late_count': late_count,
        'performance_distribution': performance_distribution,
        'high_score': max(scores) if scores else 0,
        'low_score': min(scores) if scores else 0,
        'median': scores_sorted[len(scores_sorted)//2] if scores_sorted else 0
    }
    
    return render_template('teacher/assignments/gradebook.html',
                         assignment=assignment,
                         gradebook=gradebook,
                         stats=stats,
                         now=datetime.now(pytz.utc))


@app.route('/submissions/<int:submission_id>')
@login_required
def view_submission(submission_id):
    """View a specific submission with detailed information."""
    # Load submission with related data
    submission = Submission.query.options(
        joinedload(Submission.assignment).joinedload(Assignment.author),
        joinedload(Submission.student).joinedload(Student.user),
        joinedload(Submission.assignment).joinedload(Assignment.classroom)
    ).get_or_404(submission_id)

    # Authorization checks
    if current_user.role == 'student':
        if not hasattr(current_user, 'student_profile') or submission.student.user_id != current_user.id:
            abort(403)
    elif current_user.role == 'teacher':
        if submission.assignment.author_id != current_user.id:
            abort(403)
    else:
        abort(403)

    # Handle timezone conversion
    user_tz = pytz.timezone(getattr(current_user, 'timezone', 'UTC'))
    now = datetime.now(pytz.utc).astimezone(user_tz)
    
    if submission.submitted_at:
        if submission.submitted_at.tzinfo is None:
            submission.submitted_at = pytz.utc.localize(submission.submitted_at)
        submission.submitted_at = submission.submitted_at.astimezone(user_tz)

    # Check if submission is late
    is_late = False
    if submission.submitted_at and submission.assignment.due_date:
        if submission.assignment.due_date.tzinfo is None:
            submission.assignment.due_date = pytz.utc.localize(submission.assignment.due_date)
        is_late = submission.submitted_at > submission.assignment.due_date

    # Parse questions if they exist
    questions = []
    if submission.assignment.questions:
        try:
            questions = json.loads(submission.assignment.questions)
        except json.JSONDecodeError:
            current_app.logger.error(f"Invalid questions JSON for assignment {submission.assignment.id}")
            questions = []

    return render_template('teacher/assignments/view_submission.html',
                         submission=submission,
                         assignment=submission.assignment,
                         questions=questions,
                         is_late=is_late,
                         now=now)

@app.route('/assignment/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assignment(assignment_id):
    """Edit an existing assignment."""
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.author_id != current_user.id:
        flash('You do not have permission to edit this assignment', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    form = AssignmentForm(obj=assignment)
    
    # Initialize form choices
    teacher = current_user.teacher_profile
    form.subject_id.choices = [
        (str(s.id), f"{s.name} - {s.department.name}")
        for s in teacher.get_all_subjects()
    ]
    
    form.classroom_id.choices = [
        (str(c.id), f"{c.class_name} ({c.generate_code()})")
        for c in teacher.classrooms if c.is_active
    ]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(assignment)
            assignment.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            flash('Assignment updated successfully!', 'success')
            return redirect(url_for('view_assignment', assignment_id=assignment.id))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating assignment: {str(e)}")
            flash('Error updating assignment', 'danger')
    
    return render_template('teacher/assignments/edit.html',
                         form=form,
                         assignment=assignment,
                         now=datetime.now(timezone.utc))

@app.route('/assignments/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    """Create a new assignment."""
    if current_user.role != 'teacher':
        flash('Only teachers can create assignments', 'danger')
        return redirect(url_for('index'))

    form = AssignmentForm()
    teacher = current_user.teacher_profile
    
    # Initialize form choices
    form.subject_id.choices = [
        (str(s.id), f"{s.name} - {s.department.name}")
        for s in teacher.get_all_subjects()
    ]
    
    form.classroom_id.choices = [
        (str(c.id), f"{c.class_name} ({c.generate_code()})")
        for c in teacher.classrooms if c.is_active
    ]
    
    if form.validate_on_submit():
        try:
            assignment = Assignment(
                title=form.title.data.strip(),
                description=form.description.data.strip(),
                questions=form.questions.data.strip(),
                due_date=form.due_date.data.replace(tzinfo=timezone.utc),
                max_score=form.max_score.data,
                subject_id=form.subject_id.data,
                class_id=form.classroom_id.data,
                author_id=current_user.id,
                is_published=not form.is_draft.data
            )
            
            db.session.add(assignment)
            db.session.commit()
            
            flash('Assignment created successfully!', 'success')
            return redirect(url_for('view_assignment', assignment_id=assignment.id))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating assignment: {str(e)}")
            flash('Error creating assignment', 'danger')
    
    return render_template('teacher/assignments/create.html',
                         form=form,
                         now=datetime.now(timezone.utc),
                         min_date=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """Download submitted assignment files."""
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments'),
        filename,
        as_attachment=True
    )


# ----------- TEACHER MESSAGES --------

@app.route('/messages/send', methods=['GET', 'POST'])
@login_required
def send_class_message():
    """Handle message sending with complete error handling and null checks"""
    try:
        # 1. Verify user authentication and permissions with thorough checks
        if not current_user.is_authenticated:
            raise ValueError("Authentication required")
        if not hasattr(current_user, 'is_active') or not current_user.is_active:
            raise ValueError("Account is not active")
        if not hasattr(current_user, 'role') or current_user.role != 'teacher':
            raise ValueError("Only teachers can send messages")
        if not hasattr(current_user, 'teacher_profile'):
            raise ValueError("Teacher profile not found")

        # 2. Initialize form and get classrooms with error handling
        form = MessageForm()
        try:
            classrooms = Classroom.query.filter_by(
                teacher_id=current_user.teacher_profile.id
            ).order_by(Classroom.class_name).all()
        except Exception as db_error:
            current_app.logger.error(f"Database error fetching classrooms: {str(db_error)}")
            raise ValueError("Could not load classroom data")

        # 3. Set form choices safely with validation
        form.classroom_id.choices = [(0, 'All My Classes')] + [
            (c.id, f"{c.class_name} - {c.section}") 
            for c in classrooms if c and hasattr(c, 'id') and hasattr(c, 'class_name') and hasattr(c, 'section')
        ]
        form.recipient_id.choices = [('', 'Select student')]
        form.recipient_id.coerce = lambda x: int(x) if x and x.isdigit() else None

        if form.validate_on_submit():
            try:
                # 4. Process recipient selection with robust validation
                recipient_id = None
                if (form.classroom_id.data != 0 and 
                    not form.is_announcement.data and 
                    'recipient_id' in request.form):
                    
                    try:
                        recipient_id = int(request.form['recipient_id'])
                        recipient = User.query.get(recipient_id)
                        if (not recipient or 
                            not hasattr(recipient, 'is_active') or 
                            not recipient.is_active):
                            raise ValueError("Invalid or inactive recipient selected")
                    except (ValueError, TypeError):
                        raise ValueError("Invalid recipient ID format")

                # 5. Determine recipients with comprehensive checks
                selected_classrooms = []
                if form.classroom_id.data == 0:  # All classes
                    selected_classrooms = [c for c in classrooms if c]  # Filter any None values
                    is_announcement = True
                else:
                    classroom = next((c for c in classrooms if c and c.id == form.classroom_id.data), None)
                    if not classroom:
                        raise ValueError("Classroom not found or inaccessible")
                    selected_classrooms = [classroom]
                    is_announcement = form.is_announcement.data

                # 6. Create message and collect recipients with null checks
                messages = []
                recipients = set()
                
                for classroom in selected_classrooms:
                    if not classroom or not hasattr(classroom, 'enrollments'):
                        continue  # Skip invalid classrooms

                    # Create the message with validation
                    message = Message(
                        title=form.title.data.strip(),
                        content=form.content.data.strip(),
                        sender_id=current_user.id,
                        classroom_id=classroom.id,
                        is_urgent=bool(form.is_urgent.data),
                        is_announcement=is_announcement,
                        recipient_id=recipient_id if not is_announcement else None
                    )
                    db.session.add(message)
                    messages.append(message)

                    # Collect recipients with comprehensive safety checks
                    if is_announcement:
                        for enrollment in classroom.enrollments:
                            if (enrollment and 
                                hasattr(enrollment, 'student') and 
                                enrollment.student and 
                                hasattr(enrollment.student, 'user') and 
                                enrollment.student.user and 
                                hasattr(enrollment.student.user, 'is_active') and 
                                enrollment.student.user.is_active):
                                recipients.add(enrollment.student.user)
                    elif recipient_id:
                        recipient = User.query.get(recipient_id)
                        classroom_student_ids = [
                            e.student.user_id for e in classroom.enrollments 
                            if (e and 
                                hasattr(e, 'student') and 
                                e.student and 
                                hasattr(e.student, 'user_id'))
                        ]
                        if (recipient and 
                            recipient_id in classroom_student_ids and 
                            hasattr(recipient, 'is_active') and 
                            recipient.is_active):
                            recipients.add(recipient)
                        else:
                            raise ValueError("Recipient not found in this classroom or is inactive")

                # 7. Create notifications in bulk with validation
                if recipients:
                    notifications = []
                    for user in recipients:
                        if (user and 
                            hasattr(user, 'id') and 
                            hasattr(current_user, 'full_name')):
                            notifications.append(Notification(
                                user_id=user.id,
                                title=f"New message from {current_user.full_name()}",
                                message=form.title.data.strip(),
                                action_url=url_for('view_message', message_id=messages[0].id),
                                notification_type='message'
                            ))
                    
                    if notifications:
                        db.session.bulk_save_objects(notifications)

                # 8. Final commit with error handling
                try:
                    db.session.commit()
                except Exception as commit_error:
                    db.session.rollback()
                    current_app.logger.error(f"Commit failed: {str(commit_error)}")
                    raise ValueError("Failed to save message due to database error")
                
                # 9. Return success response
                success_msg = f'Message sent to {len(recipients)} recipient(s)'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': success_msg, 
                        'redirect': url_for('message_inbox'),
                        'count': len(recipients)
                    })
                flash(success_msg, 'success')
                return redirect(url_for('message_inbox'))

            except ValueError as e:
                db.session.rollback()
                error_msg = str(e)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'error')

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Message send error: {str(e)}", exc_info=True)
                error_msg = "Failed to send message due to server error"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg}), 500
                flash(error_msg, 'error')

        # Handle form errors with validation
        if request.method == 'POST':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'Form validation failed',
                    'errors': form.errors
                }), 400
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'error')

        return render_template('teacher/messages/send_message.html',
                            form=form,
                            classrooms=[c for c in classrooms if c])  # Filter None values

    except Exception as e:
        current_app.logger.error(f"Unexpected error in send_class_message: {str(e)}", exc_info=True)
        error_msg = "An unexpected error occurred while processing your request"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 500
        flash(error_msg, 'error')
        return redirect(url_for('teacher_dashboard'))
    

@app.route('/messages/<int:message_id>')
@login_required
def view_message(message_id):
    """View a specific message with comprehensive permission checks"""
    try:
        # 1. Basic validation
        if not current_user.is_authenticated:
            abort(401)
        if not hasattr(current_user, 'role'):
            abort(403)

        # 2. Get message with error handling
        try:
            message = Message.query.get(message_id)
            if not message:
                abort(404)
        except Exception as e:
            current_app.logger.error(f"Error fetching message: {str(e)}")
            abort(500)

        # 3. Permission verification
        has_access = False
        
        if current_user.role == 'teacher':
            # Teachers can view messages they sent or messages in their classrooms
            if (hasattr(message, 'sender_id') and message.sender_id == current_user.id):
                has_access = True
            elif (hasattr(message, 'classroom') and 
                 message.classroom and 
                 hasattr(message.classroom, 'teacher_id') and 
                 message.classroom.teacher_id == current_user.id):
                has_access = True
        else:
            # Students can view messages addressed to them or to their classrooms
            if (hasattr(message, 'recipient_id') and 
                message.recipient_id == current_user.id):
                has_access = True
            elif (hasattr(message, 'classroom') and 
                  message.classroom and 
                  hasattr(current_user, 'student_profile') and 
                  current_user.student_profile):
                try:
                    # Check if student is enrolled in the classroom
                    enrollment = Enrollment.query.filter(
                        Enrollment.student_id == current_user.student_profile.id,
                        Enrollment.classroom_id == message.classroom.id,
                        Enrollment.is_dropped == False
                    ).first()
                    has_access = enrollment is not None
                except Exception as e:
                    current_app.logger.error(f"Error checking enrollment: {str(e)}")
                    has_access = False

        if not has_access:
            abort(403)

        # 4. Mark as read if recipient
        if (hasattr(message, 'recipient_id') and 
            message.recipient_id == current_user.id and 
            hasattr(message, 'is_read')):
            try:
                message.is_read = True
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error marking message as read: {str(e)}")

        return render_template('teacher/messages/view.html', message=message)

    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error in view_message: {str(e)}")
        abort(500)


@app.route('/messages/inbox')
@login_required
def message_inbox():
    """Display received messages with filtering and role-based access."""
    try:
        # 1. Ensure user is authenticated and has a valid role
        if not current_user.is_authenticated:
            abort(401)
        if not hasattr(current_user, 'role'):
            abort(403, description="Invalid user account")

        # 2. Retrieve query parameters
        message_type = request.args.get('type', 'all')
        classroom_filter = request.args.get('classroom')

        # 3. Build base query
        base_query = Message.query.order_by(Message.created_at.desc())

        # 4. Apply role-specific filtering
        if current_user.role == 'teacher':
            if not hasattr(current_user, 'id'):
                abort(403, description="Invalid teacher account")

            received_messages = base_query.filter(
                (Message.classroom.has(teacher_id=current_user.teacher_profile.id)) |
                (Message.recipient_id == current_user.id) |
                (Message.sender_id == current_user.id)
            )
            classrooms = Classroom.query.filter_by(teacher_id=current_user.teacher_profile.id).all()

        elif current_user.role == 'student':
            if not hasattr(current_user, 'student_profile') or not current_user.student_profile:
                abort(403, description="Student profile not found")

            classroom_ids = [
                e.classroom_id for e in current_user.student_profile.enrollments 
                if not e.is_dropped
            ]

            received_messages = base_query.filter(
                (Message.recipient_id == current_user.id) |
                (Message.classroom_id.in_(classroom_ids))
            )
            classrooms = [
                e.classroom for e in current_user.student_profile.enrollments 
                if not e.is_dropped
            ]

        else:
            abort(403, description="Unsupported user role")

        # 5. Apply additional filters
        if message_type == 'unread':
            received_messages = received_messages.filter_by(is_read=False)
        elif message_type == 'urgent':
            received_messages = received_messages.filter_by(is_urgent=True)

        if classroom_filter and classroom_filter != 'all':
            received_messages = received_messages.filter_by(classroom_id=int(classroom_filter))

        messages = received_messages.all()

        # 6. Prepare data for template
        unread_count = len([m for m in messages if not m.is_read])
        urgent_count = len([m for m in messages if m.is_urgent])

        return render_template(
            'teacher/messages/inbox.html',
            messages=messages,
            unread_count=unread_count,
            urgent_count=urgent_count,
            classrooms=classrooms,
            current_filter=message_type,
            current_classroom=classroom_filter
        )

    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error in message_inbox: {str(e)}", exc_info=True)
        flash('An error occurred while loading your inbox.', 'danger')
        return redirect(url_for('teacher_dashboard'))
    

# In your routes.py
@app.route('/messages/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """Handle message deletion with comprehensive error handling"""
    try:
        # 1. Get message or 404
        message = Message.query.get(message_id)
        if not message:
            flash('Message not found', 'error')
            return redirect(url_for('message_inbox'))
        
        # 2. Verify ownership
        if message.sender_id != current_user.id:
            current_app.logger.warning(
                f"Unauthorized delete attempt by {current_user.id} on message {message_id}"
            )
            abort(403)
        
        # 3. Perform deletion
        db.session.delete(message)
        db.session.commit()
        
        # 4. Handle response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': url_for('message_inbox')})
        
        flash('Message deleted successfully', 'success')
        return redirect(url_for('message_inbox'))
    
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting message {message_id}: {str(e)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Database error'}), 500
        
        flash('Failed to delete message due to database error', 'error')
        return redirect(url_for('view_message', message_id=message_id))
    
    except Exception as e:
        current_app.logger.error(f"Unexpected error deleting message {message_id}: {str(e)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Server error'}), 500
        
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('message_inbox'))
    
# ---------- QUIZ ROUTES ----------

# Helper function to calculate quiz score
def calculate_quiz_score(attempt):
    """
    Calculate the score for a quiz attempt.
    :param attempt: QuizAttempt object
    :return: Score as a percentage
    """
    total_questions = len(attempt.quiz.questions)
    correct_answers = sum(1 for answer in attempt.answers if answer.is_correct)
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0

# ---------- TEACHER QUIZ ENDPOINTS ----------

# Configure logging
logger = logging.getLogger(__name__)

@app.route('/teacher/quizzes')
@login_required
def list_quizzes():
    """Display all quizzes created by the current teacher with debug information"""
    # Verify user is a teacher with profile
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        logger.warning(f"Unauthorized access attempt by user {current_user.id}")
        abort(403, description="Teacher access required")
    
    try:
        teacher_id = current_user.teacher_profile.id
        logger.debug(f"Fetching quizzes for teacher ID: {teacher_id}")
        
        # Debug query - get ALL quizzes for this teacher including deleted ones
        all_quizzes = Quiz.query.filter_by(teacher_id=current_user.teacher_profile.id).all()
        
        logger.debug(f"All quizzes for teacher (including deleted): {[q.id for q in all_quizzes]}")
        
        # Active quizzes (published and not deleted)
        active_quizzes = Quiz.query.filter(
            Quiz.teacher_id == teacher_id,
            Quiz.is_published == True,
            Quiz.is_deleted == False
        ).order_by(Quiz.due_date.asc()).all()
        
        # Draft quizzes (not published and not deleted)
        draft_quizzes = Quiz.query.filter(
            Quiz.teacher_id == teacher_id,
            Quiz.is_published == False,
            Quiz.is_deleted == False
        ).order_by(Quiz.created_at.desc()).all()
        
        # Archived quizzes (deleted)
        archived_quizzes = Quiz.query.filter(
            Quiz.teacher_id == teacher_id,
            Quiz.is_deleted == True
        ).order_by(Quiz.updated_at.desc()).all()
        
        
        logger.debug(f"Active quizzes: {[q.id for q in active_quizzes]}")
        logger.debug(f"Draft quizzes: {[q.id for q in draft_quizzes]}")
        
        return render_template(
            'teacher/quizzes/list.html',
            archived_quizzes=archived_quizzes,
            active_quizzes=active_quizzes,
            draft_quizzes=draft_quizzes,
            all_quizzes=all_quizzes,
            now=datetime.now(local_timezone)
        )
    
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching quizzes: {str(e)}", exc_info=True)
        flash('Error loading quizzes. Please try again.', 'danger')
        return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/quiz/<int:quiz_id>')
@login_required
def view_quiz(quiz_id):
    """View details of a specific quiz"""
    try:
        # Verify user is a teacher with profile
        if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
            abort(403, description="Teacher access required")
        
        # Get quiz or return 404
        quiz = Quiz.query.get(quiz_id)
        if not quiz:
            logger.error(f"Quiz {quiz_id} not found")
            abort(404)

        # Get current time in UTC (timezone-aware)
        now_utc = datetime.now(timezone.utc)
        
        # Verify quiz ownership
        if quiz.teacher_id != current_user.teacher_profile.id:
            logger.warning(
                f"Teacher {current_user.teacher_profile.id} attempted to access quiz {quiz_id} "
                f"owned by teacher {quiz.teacher_id}"
            )
            abort(403, description="You can only view your own quizzes")
        
        # Prepare time-related variables for template
        due_date_display = None
        due_status = None
        time_remaining = None
        
        if quiz.due_date:
            # Ensure due_date is timezone-aware (convert to UTC if it isn't)
            if quiz.due_date.tzinfo is None:
                # Assume due_date is in local timezone, then convert to UTC
                due_date_local = local_timezone.localize(quiz.due_date)
                due_date_utc = due_date_local.astimezone(timezone.utc)
            else:
                # Convert to UTC if it's in another timezone
                due_date_utc = quiz.due_date.astimezone(timezone.utc)
            
            # Convert back to local time for display
            due_date_display = due_date_utc.astimezone(local_timezone)
            
            # Calculate time difference
            delta = due_date_utc - now_utc
            time_remaining = max(0, delta.total_seconds())  # in seconds
            
            # Determine due status for template
            if delta.total_seconds() > 0:
                due_status = {
                    'class': 'muted',
                    'text': f"Due in {humanize.naturaldelta(delta)}"
                }
            else:
                overdue_delta = now_utc - due_date_utc
                if overdue_delta.days < 1:
                    due_status = {
                        'class': 'danger',
                        'text': f"Due {humanize.naturaldelta(overdue_delta)} ago"
                    }
                else:
                    due_status = {
                        'class': 'danger',
                        'text': "Past due"
                    }

        return render_template(
            'teacher/quizzes/view.html',
            quiz=quiz,
            due_date_display=due_date_display,
            due_status=due_status,
            time_remaining=time_remaining,
            now=now_utc
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error viewing quiz {quiz_id}: {str(e)}", exc_info=True)
        flash('Error loading quiz details. Please try again.', 'danger')
        return redirect(url_for('list_quizzes'))

@app.route('/quizzes/restore/<int:quiz_id>', methods=['POST'])
@login_required
def restore_quiz(quiz_id):
    """Restore an archived quiz to draft status"""
    quiz = Quiz.query.filter_by(
        id=quiz_id,
        teacher_id=current_user.teacher_profile.id,
        status=QuizStatus.ARCHIVED.value
    ).first_or_404()

    try:
        quiz.status = QuizStatus.DRAFT.value
        quiz.archived_at = None
        db.session.commit()
        flash('Quiz restored to drafts successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to restore quiz', 'danger')
    
    return redirect(url_for('view_quiz', quiz_id=quiz_id))

@app.route('/teacher/quiz/<int:quiz_id>/add-questions', methods=['GET', 'POST'])
@login_required
def add_questions(quiz_id):
    """Add questions to a quiz"""
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
    
    # Your implementation here
    return render_template('teacher/quizzes/add_questions.html', quiz=quiz)


@app.route('/quizzes/create', methods=['GET', 'POST'])
@login_required
def create_quiz():
    """Create a new quiz with validation"""
    # Verify user is a teacher with profile
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        flash('Access denied. Only teachers can create quizzes.', 'danger')
        return redirect(url_for('index'))

    form = QuizCreateForm()
    teacher = current_user.teacher_profile
    
    try:
        # Initialize subject choices
        subjects = Subject.query.filter(Subject.teachers.any(id=teacher.id)).all()
        if not subjects:
            flash('You need to be assigned to at least one subject before creating quizzes', 'danger')
            return redirect(url_for('teacher_dashboard'))
        
        form.subject_id.choices = [(s.id, s.name) for s in subjects]
        
        # Dynamic classroom filtering
        selected_subject_id = request.form.get('subject_id') or request.args.get('subject_id')
        if selected_subject_id:
            # Verify the teacher actually teaches this subject
            if not any(s.id == int(selected_subject_id) for s in subjects):
                flash('Invalid subject selection', 'danger')
                return redirect(url_for('create_quiz'))
            
            classrooms = Classroom.query.filter(
                Classroom.teacher_id == teacher.id,
                Classroom.subject_id == int(selected_subject_id)
            ).all()
            
            if not classrooms:
                flash(f'No classrooms available for this subject. Please create a classroom first.', 'warning')
                return redirect(url_for('manage_classrooms'))  # Assuming you have a classroom management route
            
            form.classroom_id.choices = [(c.id, c.class_name) for c in classrooms]
        else:
            form.classroom_id.choices = []
            flash('Please select a subject first', 'info')
        
        if request.method == 'POST':
            # Process due date
            if 'due_date' in request.form:
                try:
                    form.due_date.data = datetime.strptime(
                        request.form['due_date'], 
                        '%Y-%m-%dT%H:%M'
                    )
                except ValueError:
                    form.due_date.errors.append('Invalid date format')
            
            if form.validate():
                # Verify classroom teaches selected subject
                classroom = Classroom.query.get(form.classroom_id.data)
                if not classroom or classroom.subject_id != form.subject_id.data:
                    flash('Selected classroom does not teach this subject', 'danger')
                    return render_template(
                        'teacher/quizzes/create.html',
                        form=form,
                        min_due_date=(datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
                    )
                
                # Create quiz
                quiz = Quiz(
                    title=form.title.data,
                    description=form.description.data,
                    subject_id=form.subject_id.data,
                    classroom_id=form.classroom_id.data,
                    due_date=form.due_date.data,
                    time_limit=form.time_limit.data,
                    teacher_id=teacher.id,
                    created_at=datetime.now(local_timezone)
                )
                
                # Process questions
                questions = request.form.getlist('questions')
                options_list = request.form.getlist('options')
                correct_answers = request.form.getlist('correct_option')
                points_list = request.form.getlist('points')
                
                for i, (question_text, options_str, correct_idx, points) in enumerate(zip(
                    questions, options_list, correct_answers, points_list)):
                    
                    options = [opt.strip() for opt in options_str.split(',') if opt.strip()]
                    
                    if not question_text or len(options) < 2 or not correct_idx or not points:
                        flash('All questions must have text, at least 2 options, a correct answer, and points', 'danger')
                        return render_template(
                            'teacher/quizzes/create.html',
                            form=form,
                            min_due_date=(datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
                        )
                    
                    quiz.questions.append(Question(
                        text=question_text,
                        options=options,
                        correct_option=int(correct_idx),
                        points=int(points),
                        position=i + 1,
                        time_limit=60
                    ))
                
                quiz.total_points = sum(q.points for q in quiz.questions)
                db.session.add(quiz)
                db.session.commit()
                
                flash('Quiz created successfully!', 'success')
                return redirect(url_for('view_quiz', quiz_id=quiz.id))
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Quiz creation error: {str(e)}", exc_info=True)
        flash('Error creating quiz. Please try again.', 'danger')
    
    return render_template(
        'teacher/quizzes/create.html',
        form=form,
        min_due_date=(datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
    )

@app.route('/teacher/quiz/<int:quiz_id>/preview')
@login_required
def preview_quiz(quiz_id):
    """Preview a draft quiz before publishing"""
    try:
        # Verify user is a teacher with profile
        if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
            abort(403, description="Teacher access required")
        
        quiz = Quiz.query.get_or_404(quiz_id)
        
        # Verify quiz ownership
        if quiz.teacher_id != current_user.teacher_profile.id:
            flash('You can only preview your own quizzes', 'danger')
            return redirect(url_for('list_quizzes'))
        
        # Redirect if already published
        if quiz.is_published:
            return redirect(url_for('view_quiz', quiz_id=quiz_id))
        
        # Validate quiz content
        validation_errors = []
        if not quiz.questions:
            validation_errors.append("Add at least one question")
        if not quiz.time_limit or quiz.time_limit <= 0:
            validation_errors.append("Set a valid time limit")
        
        if validation_errors:
            for error in validation_errors:
                flash(error, 'warning')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))
        
        return render_template(
            'teacher/quizzes/preview.html',
            quiz=quiz,
            now=datetime.now(local_timezone)
        )
    
    except SQLAlchemyError as e:
        logger.error(f"Error previewing quiz {quiz_id}: {str(e)}", exc_info=True)
        flash('Error loading quiz preview. Please try again.', 'danger')
        return redirect(url_for('list_quizzes'))


@app.route('/quizzes/publish/<int:quiz_id>', methods=['POST'])
@login_required
def publish_quiz(quiz_id):
    """Publish a quiz with full validation and status management"""
    try:
        # 1. Authorization Check
        if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
            flash('Only teachers can publish quizzes', 'danger')
            return redirect(url_for('list_quizzes'))

        # 2. Quiz Verification
        quiz = Quiz.query.filter(
            Quiz.id == quiz_id,
            Quiz.teacher_id == current_user.teacher_profile.id,
            Quiz.status != QuizStatus.DELETED.value
        ).first()

        if not quiz:
            current_app.logger.warning(f"Quiz not found: {quiz_id}")
            flash('Quiz not found or access denied', 'danger')
            return redirect(url_for('list_quizzes'))

        # 3. Status Check
        if quiz.is_published:
            flash('This quiz is already published', 'info')
            return redirect(url_for('view_quiz', quiz_id=quiz_id))

        # 4. Validation
        validation_errors = quiz.validate_for_publishing()
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))

        # 5. Publication Process
        try:
            quiz.publish()
            
            # Optional: Record publication event
            try:
                publication = QuizPublication(
                    quiz_id=quiz.id,
                    published_by=current_user.id,
                    timestamp=datetime.now(local_timezone)
                )
                db.session.add(publication)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to record publication: {str(e)}")

            # 6. Notifications
            try:
                # Placeholder for send_quiz_notifications function
                # Define or import this function to handle quiz notifications
                def send_quiz_notifications(quiz):
                    """Send notifications to students about the quiz."""
                    # Implement notification logic here
                    pass

                send_quiz_notifications(quiz)
            except Exception as e:
                current_app.logger.error(f"Notification failed: {str(e)}")

            flash('Quiz published successfully!', 'success')
            return redirect(url_for('view_quiz', quiz_id=quiz_id))

        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error publishing quiz {quiz_id}: {str(e)}")
        flash('A database error occurred', 'danger')
        return redirect(url_for('view_quiz', quiz_id=quiz_id))

    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        flash('An unexpected error occurred', 'danger')
        return redirect(url_for('list_quizzes'))
    

@app.route('/quizzes/unpublish/<int:quiz_id>', methods=['POST'])
@login_required
def unpublish_quiz(quiz_id):
    """Unpublish a quiz, moving it back to draft status."""
    if not (current_user.role == 'teacher' and hasattr(current_user, 'teacher_profile')):
        abort(403)
    
    quiz = Quiz.query.filter_by(
        id=quiz_id,
        teacher_id=current_user.teacher_profile.id,
        status=QuizStatus.PUBLISHED.value
    ).first_or_404()
    
    try:
        quiz.status = QuizStatus.DRAFT.value
        quiz.published_at = None
        quiz.updated_at = datetime.now(local_timezone)
        db.session.commit()
        
        flash('Quiz unpublished and moved to drafts', 'success')
        return redirect(url_for('view_quiz', quiz_id=quiz_id))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unpublishing quiz: {str(e)}")
        flash('Failed to unpublish quiz', 'danger')
        return redirect(url_for('view_quiz', quiz_id=quiz_id))

def log_publication_event(teacher, quiz):
    """Record detailed publication event in the logs"""
    student_count = len(quiz.classroom.enrollments) if quiz.classroom else 0
    log_entry = f"""
    Quiz Published Event:
    - Teacher: {teacher.id} ({teacher.full_name})
    - Quiz: {quiz.id} ({quiz.title})
    - Classroom: {quiz.classroom_id} ({quiz.classroom.class_name if quiz.classroom else 'None'})
    - Students: {student_count}
    - Questions: {len(quiz.questions)}
    - Total Points: {sum(q.points for q in quiz.questions)}
    - Due Date: {quiz.due_date}
    """
    current_app.logger.info(log_entry)
    
@app.route('/quizzes/delete/<int:quiz_id>', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    """Delete a single quiz"""
    try:
        # Verify user is a teacher with profile
        if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
            abort(403, description="Teacher access required")
        
        quiz = Quiz.query.get_or_404(quiz_id)
        
        # Verify quiz ownership
        if quiz.teacher_id != current_user.teacher_profile.id:
            abort(403, description="You can only delete your own quizzes")
        
        # Soft delete the quiz
        quiz.is_deleted = True
        quiz.deleted_at = datetime.now(local_timezone)
        db.session.commit()
        
        flash('Quiz moved to trash', 'success')
        return redirect(url_for('list_quizzes'))
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Failed to delete quiz {quiz_id}: {str(e)}", exc_info=True)
        flash('Error deleting quiz. Please try again.', 'danger')
        return redirect(url_for('view_quiz', quiz_id=quiz_id))

# ---------- EDIT QUIZ ENDPOINT (MISSING IN ORIGINAL) ----------

@app.route('/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def edit_quiz(quiz_id):
    # Authorization check
    if not (current_user.role == 'teacher' and hasattr(current_user, 'teacher_profile')):
        flash('Access denied. Only teachers can edit quizzes.', 'danger')
        return redirect(url_for('index'))

    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)

    form = QuizEditForm(obj=quiz)
    teacher = current_user.teacher_profile
    form.subject_id.choices = [(s.id, s.name) for s in teacher.subjects]
    form.classroom_id.choices = [(c.id, c.class_name) for c in teacher.classrooms]

    if request.method == 'GET':
        # Clear existing entries
        while form.questions.data:
            form.questions.pop_entry()
            
        # Populate questions
        for question in quiz.questions:
            qf = QuestionForm()
            qf.id.data = question.id
            qf.text.data = question.text
            qf.question_type.data = question.question_type
            qf.options.data = ', '.join(question.options)
            qf.correct_option.choices = [
                (i, f"{chr(65 + i)}: {opt}") 
                for i, opt in enumerate(question.options)
            ]
            qf.correct_option.data = question.correct_option
            qf.points.data = question.points
            qf.time_limit.data = question.time_limit
            form.questions.append_entry(qf)

    if request.method == 'POST' and form.validate():
        action = request.form.get('action', 'save_draft')
        form.is_published.data = (action == 'save_publish')
        
        try:
            # Update quiz metadata
            quiz.title = form.title.data
            quiz.description = form.description.data
            quiz.subject_id = form.subject_id.data
            quiz.classroom_id = form.classroom_id.data
            quiz.due_date = form.due_date.data
            quiz.time_limit = form.time_limit.data

            # Handle deleted questions
            deleted_ids = request.form.getlist('deleted_questions')
            if deleted_ids:
                Question.query.filter(
                    Question.id.in_(deleted_ids),
                    Question.quiz_id == quiz.id
                ).delete(synchronize_session=False)

            # Process questions
            for q_form in form.questions:
                if q_form.id.data:  # Existing question
                    question = Question.query.get(q_form.id.data)
                    if question:
                        question.text = q_form.text.data
                        question.question_type = q_form.question_type.data
                        question.options = [opt.strip() for opt in q_form.options.data.split(',')]
                        question.correct_option = int(q_form.correct_option.data)
                        question.points = q_form.points.data
                        question.time_limit = q_form.time_limit.data
                else:  # New question
                    options = [opt.strip() for opt in q_form.options.data.split(',')]
                    quiz.questions.append(Question(
                        text=q_form.text.data,
                        question_type=q_form.question_type.data,
                        options=options,
                        correct_option=int(q_form.correct_option.data),
                        points=q_form.points.data,
                        time_limit=q_form.time_limit.data
                    ))

            # Handle publishing
            if form.is_published.data and not quiz.is_published:
                quiz.is_published = True
                quiz.published_at = datetime.now(local_timezone)
                if form.notify_students.data:
                    pass  # Notification logic here

            quiz.total_points = sum(q.points for q in quiz.questions)
            db.session.commit()
            flash('Quiz updated successfully!', 'success')
            return redirect(url_for('view_quiz', quiz_id=quiz.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating quiz: {str(e)}', 'danger')
            app.logger.error(f"Quiz update error: {str(e)}", exc_info=True)

    return render_template('teacher/quizzes/edit.html', form=form, quiz=quiz)

@app.route('/get_new_question_form')
@login_required
def get_new_question_form():
    """Return HTML for a new question form"""
    if current_user.role != 'teacher':
        abort(403)
    
    index = request.args.get('index', 1)
    form = QuizEditForm()
    question_form = QuestionForm()
    return render_template('partials/question_form.html', 
                         question_form=question_form,
                         index=index)

@app.route('/teacher/quiz/<int:quiz_id>/results')
@login_required
def students_quiz_results(quiz_id):  # Note singular "student"
    """View results for all students who took a quiz"""
    # Verify user is a teacher with profile
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
    
    attempts = (QuizAttempt.query
               .filter_by(quiz_id=quiz_id)
               .order_by(QuizAttempt.score.desc())
               .all())
    
    return render_template('teacher/quizzes/results.html',
                         quiz=quiz,
                         attempts=attempts)


@app.route('/teacher/quiz/attempt/<int:attempt_id>')
@login_required
def view_quiz_attempt(attempt_id):
    """View detailed results of a specific quiz attempt"""
    # Verify user is a teacher
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    # Get the attempt with related data
    attempt = QuizAttempt.query.options(
        joinedload(QuizAttempt.quiz),
        joinedload(QuizAttempt.student).joinedload(Student.user),
        joinedload(QuizAttempt.answers).joinedload(QuizAnswer.question)
    ).get_or_404(attempt_id)
    
    # Verify quiz ownership
    if attempt.quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
    
    # Calculate score breakdown
    correct_count = sum(1 for answer in attempt.answers if answer.is_correct)
    total_questions = len(attempt.quiz.questions)
    percentage_score = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    return render_template('teacher/quizzes/attempt_detail.html',
                         attempt=attempt,
                         quiz=attempt.quiz,
                         student=attempt.student,
                         correct_count=correct_count,
                         total_questions=total_questions,
                         percentage_score=percentage_score)

@app.route('/teacher/analytics/quizzes')
@login_required
def teacher_quiz_analytics():
    """Display overall analytics for all quizzes"""
    # Verify user is a teacher
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    teacher_id = current_user.teacher_profile.id
    
    # Get all quizzes for this teacher
    quizzes = Quiz.query.filter_by(
        teacher_id=teacher_id,
        deleted_at=None
    ).options(
        joinedload(Quiz.attempts),
        joinedload(Quiz.classroom).joinedload(Classroom.subject)
    ).all()
    
    # Calculate overall statistics
    total_quizzes = len(quizzes)
    total_attempts = sum(len(quiz.attempts) for quiz in quizzes)
    avg_score = 0
    quiz_data = []
    
    if total_attempts > 0:
        # Calculate average score across all quizzes
        total_score = 0
        valid_attempts = 0  # Track attempts with valid scores
        
        for quiz in quizzes:
            quiz_attempts = len(quiz.attempts)
            if quiz_attempts > 0:
                # Filter out None scores and calculate average
                valid_scores = [attempt.score for attempt in quiz.attempts if attempt.score is not None]
                valid_count = len(valid_scores)
                
                if valid_count > 0:
                    quiz_avg = sum(valid_scores) / valid_count
                    quiz_highest = max(valid_scores)
                    
                    quiz_data.append({
                        'id': quiz.id,
                        'title': quiz.title,
                        'subject': quiz.classroom.subject.name,
                        'attempts': quiz_attempts,
                        'avg_score': quiz_avg,
                        'highest_score': quiz_highest
                    })
                    
                    total_score += sum(valid_scores)
                    valid_attempts += valid_count
        
        if valid_attempts > 0:
            avg_score = total_score / valid_attempts
    
    return render_template('teacher/analytics/quizzes.html',
                         quizzes=quizzes,
                         quiz_data=quiz_data,
                         total_quizzes=total_quizzes,
                         total_attempts=total_attempts,
                         avg_score=avg_score)

# ======================
# SUBJECT API
# ======================

@app.route('/api/subjects/<int:subject_id>', methods=['GET'])
@login_required
def get_subject(subject_id):
    """Get subject details"""
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        subject = Subject.query.filter(
            Subject.id == subject_id,
            Subject.teachers.any(id=current_user.teacher_profile.id)
        ).first()

        if not subject:
            return jsonify({'error': 'Subject not found'}), 404

        # Return only the fields that exist in your Subject model
        response_data = {
            'success': True,
            'subject': {
                'id': subject.id,
                'name': subject.name,
                'description': getattr(subject, 'description', 'No description available')
                # Removed 'code' since it doesn't exist in your model
            }
        }
        
        return jsonify(response_data)

    except SQLAlchemyError as e:
        logger.error(f"Error fetching subject: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'details': str(e)
        }), 500


# ======================
# CLASSROOM API
# ======================

@app.route('/api/classrooms', methods=['GET'])
@login_required
def get_classrooms():
    """Get classrooms for selected subject"""
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        return jsonify({'error': 'Unauthorized'}), 403

    subject_id = request.args.get('subject_id')
    teacher_id = request.args.get('teacher_id')
    
    if not subject_id or not teacher_id:
        return jsonify({'error': 'Subject ID and Teacher ID required'}), 400

    try:
        # Verify the teacher teaches this subject
        subject = Subject.query.filter(
            Subject.id == subject_id,
            Subject.teachers.any(id=teacher_id)
        ).first()

        if not subject:
            return jsonify({'error': 'Subject not found'}), 404

        classrooms = Classroom.query.filter(
            Classroom.teacher_id == teacher_id,
            Classroom.subject_id == subject_id
        ).all()

        # Build response with only existing attributes
        classrooms_data = []
        for c in classrooms:
            classroom_data = {
                'id': c.id,
                'class_name': c.class_name,
                # Only include attributes that exist in your model
                'subject_id': c.subject_id,
                'teacher_id': c.teacher_id
            }
            
            # Add optional fields if they exist
            if hasattr(c, 'code'):
                classroom_data['code'] = c.code
            if hasattr(c, 'max_students'):
                classroom_data['max_students'] = c.max_students
            if hasattr(c, 'schedule_days'):
                classroom_data['schedule_days'] = c.schedule_days
            if hasattr(c, 'schedule_time'):
                classroom_data['schedule_time'] = c.schedule_time
            if hasattr(c, 'location'):
                classroom_data['location'] = c.location
                
            classrooms_data.append(classroom_data)

        return jsonify({
            'success': True,
            'classrooms': classrooms_data
        })

    except SQLAlchemyError as e:
        logger.error(f"Error fetching classrooms: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'details': str(e)
        }), 500


@app.route('/api/classrooms/<int:classroom_id>', methods=['GET'])
@login_required
def get_classroom_details(classroom_id):
    """Get detailed information about a specific classroom"""
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        classroom = Classroom.query.filter(
            Classroom.id == classroom_id,
            Classroom.teacher_id == current_user.teacher_profile.id
        ).first()

        if not classroom:
            return jsonify({'error': 'Classroom not found'}), 404

        # Build response with only existing attributes
        response_data = {
            'id': classroom.id,
            'class_name': classroom.class_name,
            'subject_id': classroom.subject_id,
            'teacher_id': classroom.teacher_id
        }
        
        # Add optional fields if they exist
        if hasattr(classroom, 'code'):
            response_data['code'] = classroom.code
        if hasattr(classroom, 'max_students'):
            response_data['max_students'] = classroom.max_students
        if hasattr(classroom, 'schedule_days'):
            response_data['schedule_days'] = classroom.schedule_days
        if hasattr(classroom, 'schedule_time'):
            response_data['schedule_time'] = classroom.schedule_time
        if hasattr(classroom, 'location'):
            response_data['location'] = classroom.location
            
        # Handle student count if the relationship exists
        if hasattr(classroom, 'enrollments'):
            active_students = [e for e in classroom.enrollments if getattr(e, 'is_active', True)]
            response_data['current_student_count'] = len(active_students)
        elif hasattr(classroom, 'students'):
            active_students = [s for s in classroom.students if getattr(s, 'is_active', True)]
            response_data['current_student_count'] = len(active_students)
        else:
            response_data['current_student_count'] = 0

        return jsonify({
            'success': True,
            'classroom': response_data
        })

    except SQLAlchemyError as e:
        logger.error(f"Error fetching classroom details: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'details': str(e)
        }), 500


@app.route('/api/classrooms/<int:classroom_id>/students')
@login_required
def get_classroom_students(classroom_id):
    if current_user.role != 'teacher':
        return jsonify([])
    
    classroom = Classroom.query.filter_by(
        id=classroom_id,
        teacher_id=current_user.teacher_profile.id
    ).first()
    
    if not classroom:
        return jsonify([])
    
    search_term = request.args.get('search', '').lower()
    
    students = []
    for enrollment in classroom.enrollments:
        # Skip if enrollment doesn't have a student or user
        if not enrollment.student or not enrollment.student.user:
            continue
            
        student_user = enrollment.student.user
        
        # Safely get full name (handle potential None values)
        full_name = student_user.full_name() if hasattr(student_user, 'full_name') else ""
        username = student_user.username or ""
        student_id = str(student_user.id) if student_user.id else ""
        
        # Check if student matches search term
        if (search_term in full_name.lower() or 
            search_term in username.lower() or
            search_term in student_id):
            students.append({
                'id': student_user.id,
                'name': full_name,
                'username': username,
                'student_id': username  # or actual student ID field if different
            })
    
    return jsonify(students)

# ---------- RESOURCES MANAGEMENT ROUTES ----------

def allowed_file(filename, resource_type):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(resource_type, [])

def get_resource_folder(resource_type):
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'])
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Create resource type subfolder if it doesn't exist
    resource_dir = os.path.join(upload_dir, f"{resource_type}s")
    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir)
    
    return resource_dir

@app.route('/resources/upload', methods=['GET', 'POST'])
@login_required
def upload_resource():
    """Upload resources (teacher only)."""
    if current_user.role != 'teacher':
        abort(403)
    
    if request.method == 'POST':
        # Validate form data
        required_fields = ['resource_type', 'subject', 'title', 'classroom']
        if not all(field in request.form for field in required_fields):
            flash('Please fill in all required fields', 'error')
            return redirect(request.url)
            
        resource_type = request.form['resource_type']
        subject_id = request.form['subject']
        title = request.form['title']
        description = request.form.get('description', '')
        classroom_id = request.form['classroom']
        
        # Validate file
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
            
        if not (file and allowed_file(file.filename, resource_type)):
            allowed = ', '.join(ALLOWED_EXTENSIONS.get(resource_type, []))
            flash(f'Invalid file type for {resource_type}. Allowed types: {allowed}', 'error')
            return redirect(request.url)
            
        try:
            # Check file size (max 50MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            file.seek(0)
            
            if file_length > 50 * 1024 * 1024:  # 50MB
                flash('File size exceeds maximum limit of 50MB', 'error')
                return redirect(request.url)
            
            # Save file to appropriate subfolder
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().timestamp()}_{filename}"
            save_folder = get_resource_folder(resource_type)
            save_path = os.path.join(save_folder, unique_filename)
            file.save(save_path)
            
            # Create resource record
            new_resource = Resource(
                title=title,
                description=description,
                file_path=os.path.join(f"{resource_type}s", unique_filename),
                file_name=filename,
                file_size=file_length,
                file_type=filename.rsplit('.', 1)[1].lower(),
                resource_type=resource_type,
                subject_id=subject_id,
                classroom_id=classroom_id,
                teacher_id=current_user.id,
                upload_date=datetime.now(local_timezone),
                download_count=0
            )
            
            db.session.add(new_resource)
            db.session.commit()
            flash(f'{resource_type.capitalize()} uploaded successfully!', 'success')
            return redirect(url_for('upload_resource'))
        except Exception as e:
            db.session.rollback()
            if 'save_path' in locals() and os.path.exists(save_path):
                os.remove(save_path)
            current_app.logger.error(f"Error uploading resource: {str(e)}")
            flash(f'Error uploading resource: {str(e)}', 'error')
            return redirect(request.url)
    
    # GET request - show form
    subjects = Subject.query.order_by(Subject.name).all()
    # Change this in your upload_resource route:
    # First get the teacher associated with current user
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()

    if not teacher:
        classrooms = []
        flash("No teacher profile found for your account", "error")
    else:
        classrooms = Classroom.query.join(Subject)\
                            .options(joinedload(Classroom.subject))\
                            .filter(Classroom.teacher_id == teacher.id)\
                            .order_by(Classroom.class_name)\
                            .all()
    recent_resources = Resource.query.filter_by(teacher_id=current_user.id)\
                                  .order_by(Resource.upload_date.desc())\
                                  .limit(10)\
                                  .all()
    
    return render_template('teacher/resources/upload_resources.html',
                         subjects=subjects,
                         classrooms=classrooms,
                         resources=recent_resources)


@app.route('/resources/download/<int:resource_id>')
@login_required
def download_resource(resource_id):
    """Download a resource file."""
    resource = Resource.query.options(
        joinedload(Resource.classroom),
        joinedload(Resource.subject)
    ).get_or_404(resource_id)
    
    # Check if user has permission
    has_access = False
    if current_user.role == 'teacher' and resource.teacher_id == current_user.id:
        has_access = True
    elif current_user.role == 'student':
        # Check if student is in the classroom
        classroom = resource.classroom
        if classroom and current_user in classroom.students:
            has_access = True
    
    if not has_access:
        abort(403)
    
    # Update download count
    resource.download_count += 1
    db.session.commit()
    
    # Build full file path
    file_path = os.path.join(
        current_app.root_path, 
        current_app.config['UPLOAD_FOLDER'], 
        resource.file_path
    )
    
    if not os.path.exists(file_path):
        abort(404)
    
    return send_file(file_path, as_attachment=True, download_name=resource.file_name)

@app.route('/resources/view/<int:resource_id>')
@login_required
def view_resource(resource_id):
    """View resource details with appropriate preview."""
    resource = Resource.query.options(
        joinedload(Resource.classroom).joinedload(Classroom.subject),
        joinedload(Resource.teacher)
    ).get_or_404(resource_id)
    
    # Check permissions
    has_access = False
    if current_user.role == 'teacher' and resource.teacher_id == current_user.id:
        has_access = True
    elif current_user.role == 'student':
        # Check if student is enrolled in the classroom
        classroom = resource.classroom
        if classroom and current_user in classroom.students:
            has_access = True
    
    if not has_access:
        abort(403)
    
    # Update view count
    resource.views_count = Resource.views_count + 1
    db.session.commit()
    
    return render_template('teacher/resources/view_resource.html', resource=resource)

@app.route('/resources/approve/<int:resource_id>', methods=['POST'])
@login_required
def approve_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    # Check if current user is the resource owner (teacher) or admin
    if not (current_user.role == 'admin' or 
           (current_user.role == 'teacher' and resource.teacher_id == current_user.id)):
        abort(403)
    
    resource.is_approved = True
    db.session.commit()
    
    flash('Resource has been approved and is now public', 'success')
    return redirect(url_for('view_resource', resource_id=resource_id))

@app.route('/resources/unapprove/<int:resource_id>', methods=['POST'])
@login_required
def unapprove_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    # Check if current user is the resource owner (teacher) or admin
    if not (current_user.role == 'admin' or 
           (current_user.role == 'teacher' and resource.teacher_id == current_user.id)):
        abort(403)
    
    resource.is_approved = False
    db.session.commit()
    
    flash('Resource has been unapproved and is no longer public', 'warning')
    return redirect(url_for('view_resource', resource_id=resource_id))

@app.route('/resources/<int:resource_id>/comments', methods=['POST'])
@login_required
def add_comment(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    
    # Check if user has access to this resource
    if not resource.is_approved and not (current_user.role == 'teacher' and resource.teacher_id == current_user.id):
        abort(403)
    
    comment_content = request.form.get('comment')
    if not comment_content:
        flash('Comment cannot be empty', 'error')
        return redirect(url_for('view_resource', resource_id=resource_id))
    
    new_comment = ResourceComment(
        content=comment_content,
        user_id=current_user.id,
        resource_id=resource_id
    )
    
    db.session.add(new_comment)
    db.session.commit()
    
    flash('Comment added successfully', 'success')
    return redirect(url_for('view_resource', resource_id=resource_id))


@app.route('/teacher/resources/pending')
@login_required
def teacher_pending_resources():
    if current_user.role != 'teacher':
        abort(403)
    
    pending = Resource.query.filter_by(
        is_approved=False,
        teacher_id=current_user.id
    ).all()
    
    return render_template('teacher/resources/pending_resources.html', resources=pending)


@app.route('/resources/delete/<int:resource_id>', methods=['POST'])
@login_required
def delete_resource(resource_id):
    """Delete a resource."""
    resource = Resource.query.get_or_404(resource_id)
    
    if current_user.role != 'teacher' or resource.teacher_id != current_user.id:
        abort(403)
    
    try:
        # Delete file from filesystem
        file_path = os.path.join(
            current_app.root_path,
            current_app.config['UPLOAD_FOLDER'],
            resource.file_path
        )
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete record from database
        db.session.delete(resource)
        db.session.commit()
        flash('Resource deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting resource: {str(e)}")
        flash('Error deleting resource', 'error')
    
    return redirect(url_for('upload_resource'))

@app.route('/resources/<int:resource_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_resource(resource_id):
    """Edit a resource with proper authorization and file handling"""
    # Get resource with relationships
    resource = Resource.query.options(
        joinedload(Resource.classroom),
        joinedload(Resource.subject)
    ).get_or_404(resource_id)
    
    # Verify teacher ownership
    if current_user.role != 'teacher' or resource.teacher_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        try:
            # Update basic info
            resource.title = request.form['title']
            resource.description = request.form.get('description', '')
            resource.subject_id = request.form['subject']
            resource.classroom_id = request.form['classroom']
            
            # Handle file update if provided
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                
                # Validate file
                if not allowed_file(file.filename, resource.resource_type):
                    allowed = ', '.join(ALLOWED_EXTENSIONS.get(resource.resource_type, []))
                    flash(f'Invalid file type. Allowed types: {allowed}', 'error')
                    return redirect(request.url)
                
                # Check file size
                if file.content_length > current_app.config['MAX_CONTENT_LENGTH']:
                    flash('File size exceeds maximum allowed (50MB)', 'error')
                    return redirect(request.url)
                
                # Delete old file if exists
                if resource.file_path:
                    old_file_path = os.path.join(
                        current_app.config['UPLOAD_FOLDER'],
                        resource.file_path
                    )
                    try:
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    except Exception as e:
                        current_app.logger.error(f"Error deleting old file: {str(e)}")
                
                # Generate secure filename
                filename = secure_filename(file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
                save_folder = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    f"{resource.resource_type}s"
                )
                os.makedirs(save_folder, exist_ok=True)
                save_path = os.path.join(save_folder, unique_filename)
                
                # Save new file
                file.save(save_path)
                
                # Update resource file info
                resource.file_path = os.path.join(f"{resource.resource_type}s", unique_filename)
                resource.file_name = filename
                resource.file_size = os.path.getsize(save_path)
                resource.file_type = file_ext
                resource.modified_at = datetime.utcnow()
            
            db.session.commit()
            flash('Resource updated successfully!', 'success')
            return redirect(url_for('view_resource', resource_id=resource.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating resource {resource_id}: {str(e)}")
            flash(f'Error updating resource: {str(e)}', 'error')
            return redirect(request.url)
    
    # GET request - show edit form
    subjects = Subject.query.order_by(Subject.name).all()
    teacher = current_user.teacher_profile
    
    if not teacher:
        classrooms = []
        flash("No teacher profile found", "error")
    else:
        classrooms = Classroom.query.join(Subject)\
                            .options(joinedload(Classroom.subject))\
                            .filter(Classroom.teacher_id == teacher.id)\
                            .order_by(Classroom.class_name)\
                            .all()
    
    return render_template('teacher/resources/edit_resource.html',
                         resource=resource,
                         subjects=subjects,
                         classrooms=classrooms)
