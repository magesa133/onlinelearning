import base64
import os
from datetime import datetime, timedelta, timezone
import uuid
from io import BytesIO
import pytz as pytz_timezone
from pytz.exceptions import UnknownTimeZoneError
import humanize
from flask import render_template, session, send_file
from flask_wtf import FlaskForm
from wtforms import RadioField
from wtforms.validators import DataRequired, ValidationError
from zoneinfo import ZoneInfo  # Python 3.9+ (preferred) or use pytz as fallback
from forms import AssignmentForm, SubmissionForm, QuizEditForm  # Import the forms
from forms import QuizCreateForm, QuestionForm  # Ensure this import is added at the top of the file
import pandas as pd
from markdown import markdown
from bleach import clean  # Add this import at the top of the file if not already present
from sqlalchemy.exc import SQLAlchemyError
import logging
import traceback
import json
from flask import abort, flash, jsonify, redirect, render_template, request, \
                   send_from_directory, url_for, current_app
import traceback
from flask_login import current_user, login_required, login_user, logout_user
from PIL import Image
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload, load_only
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app import app, db
from models import (Activity, Assignment, Attendance, Classroom, Department,
                    Grade, Resource, OnlineSession, Question, Quiz, Student,
                    Submission, Subject, Teacher, User, Enrollment, QuizAttempt, QuizAnswer, Message, ClassAnnouncement, ClassroomActivity)
from zoneinfo import ZoneInfo
from pytz import timezone as pytz_timezone
local_timezone = pytz_timezone('Africa/Dar_es_Salaam')
import pytz  # Add this import

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {
    'document': {'pdf', 'docx', 'txt', 'zip'},
    'image': {'png', 'jpg', 'jpeg'},
    'audio': {'mp3', 'wav'},
    'video': {'mp4', 'mov'}
}

@app.template_filter('safe_divide')
def safe_divide(numerator, denominator, default=0):
    return numerator / denominator if denominator else default

# Set configuration in app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

def allowed_file(filename, resource_type):
    """Check if the file has an allowed extension for the given resource type."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(resource_type, set())

def get_resource_folder(resource_type):
    """Ensure the correct upload directory for the resource type exists and return its path."""
    resource_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"{resource_type}s")
    os.makedirs(resource_dir, exist_ok=True)
    return resource_dir

# ---------- AUTHENTICATION ROUTES ----------

@app.route('/')
def index():
    """Home page route."""
    return render_template('index.html')

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
                # Add your code logic here
                pass
            except Exception as e:
                current_app.logger.error(f"An error occurred: {str(e)}")
                flash("An error occurred while processing your request.", "danger")
                # Add your code here
                pass
            except Exception as e:
                current_app.logger.error(f"An error occurred: {str(e)}")
                flash("An error occurred while processing your request.", "danger")
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
        return Submission.query.filter_by(student_id=student.id).order_by(Submission.submitted_at.desc()).limit(limit).all()
    except Exception as e:
        current_app.logger.error(f"Error fetching recent submissions: {str(e)}")
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

@unique
class QuizStatus(Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'
    DELETED = 'deleted'

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    """Student dashboard showing all academic activities with proper timezone handling"""
    try:
        # Authentication check
        if current_user.role != 'student' or not current_user.student_profile:
            current_app.logger.warning(f"Unauthorized dashboard access by {current_user.id}")
            abort(403)
        
        student = current_user.student_profile
        tz = pytz.timezone('Africa/Dar_es_Salaam')
        now = datetime.now(tz)
        current_app.logger.debug(f"Building dashboard for student {student.id} at {now}")

        # Get enrolled classrooms with subjects
        enrollments = Enrollment.query.filter_by(student_id=student.id).options(
            joinedload(Enrollment.classroom).joinedload(Classroom.subject),
            joinedload(Enrollment.classroom).joinedload(Classroom.teacher)
        ).all()
        
        if not enrollments:
            return render_template('student_dashboard.html',
                               warning="You are not enrolled in any classes",
                               now=now,
                               local_timezone=tz)

        class_ids = [e.classroom.id for e in enrollments]

        # Get published quizzes with all necessary relationships
        quizzes = Quiz.query.filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == QuizStatus.PUBLISHED.value
        ).options(
            joinedload(Quiz.classroom).joinedload(Classroom.subject),
            joinedload(Quiz.teacher).joinedload(Teacher.user),
            joinedload(Quiz.questions)
        ).all()

        # Process quizzes with timezone awareness
        upcoming_quizzes = []
        for quiz in quizzes:
            if quiz.due_date:
                # Ensure timezone handling
                quiz_due_date = quiz.due_date
                if quiz_due_date.tzinfo is None:
                    quiz_due_date = local_timezone.localize(quiz_due_date)
                quiz_due_date = quiz_due_date.astimezone(tz)
                
                if quiz_due_date > now:
                    time_remaining = quiz_due_date - now
                    upcoming_quizzes.append({
                        'quiz': quiz,
                        'due_date_local': quiz_due_date,
                        'time_remaining': time_remaining,
                        'status': quiz.status,
                        'question_count': len(quiz.questions),
                        'total_points': sum(q.points for q in quiz.questions)
                    })

        # Sort by due date (soonest first)
        upcoming_quizzes.sort(key=lambda x: x['due_date_local'])

        # Get other dashboard data
        assignments = get_student_assignments(student, class_ids, now)
        activities = get_recent_classroom_activities(class_ids)
        announcements = get_recent_announcements(class_ids)
        recent_attempts = get_recent_quiz_attempts(student.id)
        resources = Resource.query.filter(Resource.classroom_id.in_(class_ids)).all()

        return render_template('student_dashboard.html',
            student=student,
            assignments=assignments,
            quizzes=upcoming_quizzes,
            activities=activities,
            announcements=announcements,
            now=now,
            local_timezone=tz,
            recent_quiz_attempts=recent_attempts,
            QuizStatus=QuizStatus,
            humanize=humanize,
            resources=resources  # ← this line added
        )

    except Exception as e:
        current_app.logger.error(f"Error loading student dashboard: {str(e)}", exc_info=True)
        flash("An error occurred while loading your dashboard", "danger")
        return redirect(url_for('index'))

# Helper functions with timezone support
def get_student_quizzes(student, class_ids, now):
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
        
        return {
            'upcoming': [q for q in quizzes 
                        if q.due_date and q.due_date.astimezone(local_timezone) > now
                        and q.id not in attempts],
            'past': [q for q in quizzes 
                    if q.due_date and q.due_date.astimezone(local_timezone) <= now
                    and q.id not in attempts],
            'attempted': [q for q in quizzes 
                         if q.id in attempts]
        }
    except Exception as e:
        current_app.logger.error(f"Error fetching quizzes: {str(e)}")
        return {}


def format_datetime(dt, format_str='%B %d, %Y at %H:%M'):
    """Safe datetime formatting with timezone conversion"""
    if not dt:
        return "Not set"
    if not dt.tzinfo:
        dt = local_timezone.localize(dt)
    return dt.astimezone(local_timezone).strftime(format_str)
def get_student_quizzes(student, class_ids, now):
    """Retrieve and organize quizzes with proper filtering"""
    try:
        # Base query
        quizzes = Quiz.query.filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == QuizStatus.PUBLISHED.value,
            Quiz.is_deleted == False,
            Quiz.due_date > now  # Only future quizzes
        ).options(
            joinedload(Quiz.subject),
            joinedload(Quiz.classroom),
            joinedload(Quiz.teacher)
        ).order_by(Quiz.due_date.asc()).all()

        # Debug output
        current_app.logger.debug(f"Found {len(quizzes)} quizzes for student {student.id}")
        for q in quizzes:
            current_app.logger.debug(f"Quiz {q.id}: {q.title} (Class {q.classroom_id}, Due {q.due_date})")

        # Get attempts
        attempts = {a.quiz_id: a for a in student.quiz_attempts}
        
        return {
            'upcoming': [q for q in quizzes if q.id not in attempts],
            'past': [],
            'attempted': []
        }
        
    except Exception as e:
        current_app.logger.error(f"Quiz query error: {str(e)}", exc_info=True)
        return {'upcoming': [], 'past': [], 'attempted': []}

def get_student_assignments(student_id, class_ids, now):
    return Assignment.query.filter(
        Assignment.class_id.in_(class_ids),
        Assignment.due_date > now
    ).options(
        joinedload(Assignment.classroom),
        joinedload(Assignment.author)
    ).order_by(Assignment.due_date).limit(5).all()

def get_recent_classroom_activities(class_ids):
    return ClassroomActivity.query.filter(
        ClassroomActivity.classroom_id.in_(class_ids)
    ).options(
        joinedload(ClassroomActivity.classroom),
        joinedload(ClassroomActivity.author)
    ).order_by(ClassroomActivity.created_at.desc()).limit(10).all()

def get_recent_announcements(class_ids):
    return ClassAnnouncement.query.filter(
        ClassAnnouncement.classroom_id.in_(class_ids)
    ).options(
        joinedload(ClassAnnouncement.classroom),
        joinedload(ClassAnnouncement.author)
    ).order_by(ClassAnnouncement.created_at.desc()).limit(5).all()

def get_recent_quiz_attempts(student_id):
    attempts = QuizAttempt.query.filter_by(student_id=student_id)\
        .order_by(QuizAttempt.completed_at.desc())\
        .limit(5)\
        .options(joinedload(QuizAttempt.quiz))\
        .all()
    
    tz = pytz.timezone('Africa/Dar_es_Salaam')
    
    for attempt in attempts:
        if attempt.completed_at and attempt.completed_at.tzinfo is None:
            attempt.completed_at = tz.localize(attempt.completed_at)
    
    return attempts

def get_student_sessions(class_ids, now):
    """Retrieve online sessions grouped by status"""
    try:
        return {
            'active': OnlineSession.query.filter(
                OnlineSession.class_id.in_(class_ids),
                OnlineSession.end_time >= now
            ).options(
                joinedload(OnlineSession.classroom)
            ).order_by(OnlineSession.start_time.asc()).all(),
            'past': OnlineSession.query.filter(
                OnlineSession.class_id.in_(class_ids),
                OnlineSession.end_time < now
            ).options(
                joinedload(OnlineSession.classroom)
            ).order_by(OnlineSession.start_time.desc()).limit(5).all()
        }
    except Exception as e:
        current_app.logger.error(f"Error fetching sessions: {str(e)}")
        return {}



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

# ---------- STUDENT RESOURCES ROUTES ----------
# Resources Section

@app.route('/study-resources')
@login_required
def student_resources():
    try:
        if current_user.role != 'student':
            abort(403)

        student = current_user.student_profile
        class_ids = [e.class_id for e in student.enrollments]
        
        if not class_ids:
            return render_template('student/study_resources.html',
                               subjects=[],
                               resources=None,  # Changed from notes to resources
                               message="No classes found")

        page = request.args.get('page', 1, type=int)
        resource_type = request.args.get('type', 'all')
        subject_id = request.args.get('subject_id', type=int)

        query = Resource.query.filter(
            Resource.classroom_id.in_(class_ids),
            Resource.is_approved == True
        )

        if resource_type != 'all':
            query = query.filter(Resource.resource_type == resource_type)
        if subject_id:
            query = query.filter(Resource.subject_id == subject_id)

        resources = query.options(
            joinedload(Resource.classroom),
            joinedload(Resource.subject),
            joinedload(Resource.teacher).joinedload(Teacher.user)
        ).order_by(Resource.upload_date.desc()).paginate(
            page=page, 
            per_page=10,
            error_out=False
        )

        subjects = Subject.query.join(Classroom).filter(
            Classroom.id.in_(class_ids)
        ).distinct().all()

        return render_template('student/study_resources.html',
            resources=resources,  # Changed from notes to resources
            subjects=subjects,
            current_type=resource_type,
            selected_subject=subject_id
        )

    except Exception as e:
        current_app.logger.error(f"Error in study_resources: {str(e)}")
        flash("Error loading study resources", "danger")
        return redirect(url_for('student_dashboard'))

@app.route('/student/resources/<int:resource_id>')
@login_required
def student_view_resource(resource_id):
    """View details of a specific resource"""
    try:
        if current_user.role != 'student':
            abort(403)

        student = current_user.student_profile
        resource = Resource.query.options(
            joinedload(Resource.classroom),
            joinedload(Resource.subject),
            joinedload(Resource.teacher).joinedload(Teacher.user)
        ).get_or_404(resource_id)

        # Verify access
        if resource.classroom_id not in [e.class_id for e in student.enrollments]:
            abort(403)

        # Track view
        resource.views_count = Resource.views_count + 1
        db.session.commit()

        return render_template('student/resources/view.html',
            resource=resource
        )

    except Exception as e:
        current_app.logger.error(f"Error viewing resource {resource_id}: {str(e)}")
        flash("Error loading resource", "danger")
        return redirect(url_for('student_resources'))

@app.route('/student/resources/<int:resource_id>/download')
@login_required
def student_download_resource(resource_id):
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
        return redirect(url_for('student_view_resource', resource_id=resource_id))
        
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

    # Base query
    query = Assignment.query.filter(
        Assignment.class_id.in_(class_ids),
        Assignment.is_published == True
    ).options(
        joinedload(Assignment.classroom),
        joinedload(Assignment.subject)
    )

    # Apply status filter
    submitted_ids = [s.assignment_id for s in student.submissions]
    if status_filter == 'submitted':
        query = query.filter(Assignment.id.in_(submitted_ids))
    elif status_filter == 'pending':
        query = query.filter(
            Assignment.id.notin_(submitted_ids),
            Assignment.due_date >= datetime.now(local_timezone)

        )
    elif status_filter == 'overdue':
        query = query.filter(
            Assignment.id.notin_(submitted_ids),
            Assignment.due_date < datetime.now(local_timezone)
        )

    # Apply subject filter
    if subject_id:
        query = query.filter(Assignment.subject_id == subject_id)

    assignments = query.order_by(Assignment.due_date.asc()).all()

    # Get subjects for filter dropdown
    subjects = Subject.query.join(Classroom).filter(
        Classroom.id.in_(class_ids)
    ).distinct().all()

    # Get submissions for display
    submissions = {s.assignment_id: s for s in student.submissions}

    return render_template('student/assignments/list.html',
        assignments=assignments,
        submissions=submissions,
        status_filter=status_filter,
        subjects=subjects,
        selected_subject=subject_id,
        now=datetime.now(local_timezone)
    )

@app.route('/student/assignments/<int:assignment_id>')
@login_required
def student_view_assignment(assignment_id):
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    assignment = Assignment.query.options(
        joinedload(Assignment.classroom),
        joinedload(Assignment.subject),
        joinedload(Assignment.author).joinedload(Teacher.user)
    ).get_or_404(assignment_id)

    # Check if student is enrolled in the class
    enrollment = Enrollment.query.filter_by(
        student_id=student.id,
        class_id=assignment.class_id
    ).first()
    if not enrollment:
        abort(403)

    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student.id
    ).first()

    return render_template('student/assignments/view.html',
        assignment=assignment,
        submission=submission,
        now=datetime.now(local_timezone)
    )

@app.route('/student/assignments/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
def student_submit_assignment(assignment_id):
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    assignment = Assignment.query.options(
        joinedload(Assignment.classroom)
    ).get_or_404(assignment_id)

    # Check enrollment and deadline
    enrollment = Enrollment.query.filter_by(
        student_id=student.id,
        class_id=assignment.class_id
    ).first()
    if not enrollment:
        abort(403)

    if assignment.due_date < datetime.now(local_timezone):
        flash('The due date for this assignment has passed', 'danger')
        return redirect(url_for('student_view_assignment', assignment_id=assignment_id))

    # Check for existing submission
    existing_submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student.id
    ).first()
    if existing_submission:
        flash('You have already submitted this assignment', 'warning')
        return redirect(url_for('student_view_assignment', assignment_id=assignment_id))

    form = SubmissionForm()
    if form.validate_on_submit():
        try:
            # Handle file upload
            file_path = None
            if form.file.data:
                filename = secure_filename(f"{student.id}_{assignment_id}_{form.file.data.filename}")
                upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'submissions')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                form.file.data.save(file_path)

            # Create submission
            submission = Submission(
                content=form.content.data,
                file_path=file_path,
                assignment_id=assignment_id,
                student_id=student.id,
                submitted_at=datetime.now(local_timezone)
            )
            db.session.add(submission)
            db.session.commit()

            flash('Assignment submitted successfully!', 'success')
            return redirect(url_for('student_view_assignment', assignment_id=assignment_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting assignment: {str(e)}")
            flash('An error occurred while submitting your assignment', 'danger')

    return render_template('student/assignments/submit.html',
        form=form,
        assignment=assignment
    )

# STUDENT QUIZ AREA - IMPROVED VERSION

# Enhanced utility functions
def get_student_quiz_data(student_id):
    """Get all classes and subjects a student is enrolled in"""
    return Enrollment.query.filter_by(
        student_id=student_id
    ).options(
        joinedload(Enrollment.Classroom).joinedload(Classroom.Subject),
        joinedload(Enrollment.Classroom).joinedload(Classroom.quizzes)
    ).all()

# Flask routes (app.py)
# ======================
# QUIZ LISTING & DETAILS
# ======================

@app.route('/student/quizzes')
@login_required
def student_quizzes():
    """Display all quizzes available to the student with filtering options"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    try:
        # Get filter parameters with defaults
        status_filter = request.args.get('status', 'upcoming')
        subject_filter = request.args.get('subject_id', type=int)
        
        # Get student's enrolled classrooms with subjects
        enrollments = Enrollment.query.filter_by(
            student_id=current_user.student_profile.id
        ).options(
            joinedload(Enrollment.classroom).joinedload(Classroom.subject)
        ).all()  # Added missing parenthesis and .all()
        
        if not enrollments:
            return render_template('student/quizzes/list.html',
                warning="You are not enrolled in any classes",
                subjects=[],
                status_filter=status_filter
            )

        # Build base quiz query
        class_ids = [e.classroom.id for e in enrollments]
        quiz_query = Quiz.query.filter(
            Quiz.classroom_id.in_(class_ids),
            Quiz.status == 'published',
            Quiz.is_deleted == False
        )
        
        # Apply time-based filters with proper timezone handling
        now = datetime.now(local_timezone)
        now_naive = now.replace(tzinfo=None)
        
        if status_filter == 'upcoming':
            quiz_query = quiz_query.filter(
                or_(
                    and_(Quiz.due_date.isnot(None), 
                         func.coalesce(Quiz.due_date > now, Quiz.due_date > now_naive)),
                    Quiz.due_date.is_(None)
                )  # Fixed missing parenthesis
            )
        elif status_filter == 'past':
            quiz_query = quiz_query.filter(
                and_(Quiz.due_date.isnot(None), 
                     func.coalesce(Quiz.due_date <= now, Quiz.due_date <= now_naive))
            )
        
        # Apply subject filter if provided
        if subject_filter:
            quiz_query = quiz_query.join(Classroom).filter(
                Classroom.subject_id == subject_filter)
        
        quizzes = quiz_query.order_by(Quiz.due_date.asc()).all()
        
        # Get unique subjects for filter dropdown
        subjects = {e.classroom.subject.id: e.classroom.subject for e in enrollments}
        
        return render_template('student/quizzes/list.html',
            quizzes=quizzes,
            subjects=subjects.values(),  # Convert to list for template
            status_filter=status_filter,
            selected_subject=subject_filter,
            now=now,
            status_options=[
                ('upcoming', 'Upcoming Quizzes'),
                ('past', 'Past Quizzes')
            ]  # Added status options for template
        )

    except Exception as e:
        current_app.logger.error(f"Error loading student quizzes: {str(e)}", exc_info=True)
        flash("An error occurred while loading quizzes. Please try again later.", "error")
        return redirect(url_for('student_dashboard'))
    

@app.route('/student/quizzes/<int:quiz_id>')
@login_required
def student_view_quiz(quiz_id):
    """Display quiz details and attempt history"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    try:
        # Get quiz with optimized loading
        quiz = Quiz.query.options(
            joinedload(Quiz.classroom).joinedload(Classroom.subject),
            joinedload(Quiz.questions),
            joinedload(Quiz.attempts)
        ).get_or_404(quiz_id)
        
        # Verify enrollment
        if not Enrollment.query.filter_by(
            student_id=current_user.id,
            class_id=quiz.classroom_id
        ).first():
            abort(403, description="Not enrolled in this class")
        
        # Get attempts ordered by most recent
        attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            student_id=current_user.id
        ).order_by(QuizAttempt.started_at.desc()).all()
        
        # Ensure total points is calculated
        if not quiz.total_points:
            quiz.total_points = quiz.calculate_total_points()
            db.session.commit()
        
        # Normalize timezone for due date
        if quiz.due_date and quiz.due_date.tzinfo is None:
            quiz.due_date = quiz.due_date.replace(tzinfo=timezone.utc)
        
        return render_template(
            'student/quizzes/take_quiz.html',
            quiz=quiz,
            attempts=attempts,
            now_utc=datetime.now(timezone.utc),
            can_take_quiz=can_take_quiz(current_user.id, quiz_id)
        )

    except Exception as e:
        current_app.logger.error(f"Error viewing quiz {quiz_id}: {str(e)}")
        flash("An error occurred while loading the quiz", "error")
        return redirect(url_for('student_quizzes'))


# ======================
# QUIZ ATTEMPT MANAGEMENT
# ======================

@app.route('/student/quizzes/<int:quiz_id>/start', methods=['GET', 'POST'])
@login_required
def student_start_quiz(quiz_id):
    """Handle quiz attempt initialization"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    quiz = Quiz.query.options(
        joinedload(Quiz.questions)
    ).get_or_404(quiz_id)
    
    # Verify enrollment
    if not Enrollment.query.filter_by(
        student_id=current_user.id,
        class_id=quiz.classroom_id
    ).first():
        abort(403, description="Not enrolled in this class")
    
    # Check if student can take the quiz
    if not can_take_quiz(current_user.id, quiz_id):
        flash("You cannot start this quiz at this time", "warning")
        return redirect(url_for('student_view_quiz', quiz_id=quiz_id))
    
    # Check for existing incomplete attempt
    existing_attempt = QuizAttempt.query.filter_by(
        quiz_id=quiz_id,
        student_id=current_user.id,
        completed_at=None
    ).first()
    
    if existing_attempt:
        return redirect(url_for('student_take_quiz', attempt_id=existing_attempt.id))
    
    if request.method == 'POST':
        try:
            # Create new attempt
            new_attempt = QuizAttempt(
                quiz_id=quiz_id,
                user_id=current_user.id,
                student_id=current_user.id,
                started_at=datetime.now(timezone.utc),
                ip_address=request.remote_addr
            )
            
            # Initialize empty answers
            for question in quiz.questions:
                answer = QuizAnswer(
                    attempt=new_attempt,
                    question_id=question.id,
                    student_id=current_user.id
                )
                db.session.add(answer)
            
            db.session.add(new_attempt)
            db.session.commit()
            
            return redirect(url_for('student_take_quiz', attempt_id=new_attempt.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Quiz start error: {str(e)}", exc_info=True)
            flash('Failed to start quiz. Please try again.', 'error')
    
    # For GET requests or if POST fails, show confirmation page
    return render_template('student/quizzes/start_confirmation.html',
        quiz=quiz,
        attempts_count=QuizAttempt.query.filter_by(
            quiz_id=quiz_id,
            student_id=current_user.id
        ).count(),
        max_attempts=quiz.max_attempts or 1
    )


@app.route('/student/quizzes/attempt/<int:attempt_id>', methods=['GET', 'POST'])
@login_required
def student_take_quiz(attempt_id):
    """Handle the quiz-taking process"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    try:
        # Fetch attempt with related data
        attempt = QuizAttempt.query.options(
            joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
            joinedload(QuizAttempt.quiz).joinedload(Quiz.classroom),
            joinedload(QuizAttempt.answers)
        ).get_or_404(attempt_id)
        
        # Authorization check
        if attempt.student_id != current_user.student_profile.id:
            abort(403, description="Not your quiz attempt")
        
        if attempt.completed_at:
            return redirect(url_for('student_quiz_results', attempt_id=attempt_id))
        
        # Handle POST request (answer submission)
        if request.method == 'POST':
            return _handle_quiz_answer_submission(attempt)
        
        # Handle GET request (display quiz)
        return _display_quiz_questions(attempt)
        
    except Exception as e:
        current_app.logger.error(f"Quiz attempt error: {str(e)}")
        flash("An error occurred during the quiz attempt", "error")
        return redirect(url_for('student_quizzes'))


def _handle_quiz_answer_submission(attempt):
    """Process answer submission during quiz attempt"""
    question_id = request.form.get('question_id')
    selected_answer = request.form.get('answer')
    
    if not question_id or selected_answer is None:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        abort(400, description="Missing question data")
    
    try:
        # Find or create answer record
        answer = QuizAnswer.query.filter_by(
            attempt_id=attempt.id,
            question_id=question_id
        ).first()
        
        if not answer:
            answer = QuizAnswer(
                attempt_id=attempt.id,
                question_id=question_id,
                student_id=current_user.id,
                selected_answer=str(selected_answer)
            )
            db.session.add(answer)
        else:
            answer.selected_answer = str(selected_answer)
        
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True})
        
        # For form submissions, redirect to next question
        next_index = request.args.get('next', type=int)
        return redirect(url_for('student_take_quiz', 
                            attempt_id=attempt.id, 
                            q=next_index) if next_index else 
                        url_for('student_take_quiz', 
                            attempt_id=attempt.id))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Answer submission error: {str(e)}")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash("Failed to save your answer", "error")
        return redirect(url_for('student_take_quiz', attempt_id=attempt.id))


def _display_quiz_questions(attempt):
    """Prepare and display quiz questions"""
    questions = attempt.quiz.questions.order_by(Question.position).all()
    
    if not questions:
        flash('This quiz has no questions yet', 'warning')
        return redirect(url_for('student_dashboard'))
    
    # Get current question index with validation
    try:
        current_index = max(0, min(
            int(request.args.get('q', 0)),
            len(questions) - 1
        ))
    except ValueError:
        current_index = 0
    
    progress = round(((current_index + 1) / len(questions)) * 100, 1)
    
    return render_template('student/quizzes/take_quiz.html',
        attempt=attempt,
        quiz=attempt.quiz,
        questions=questions,
        current_index=current_index,
        progress=progress,
        time_remaining=_calculate_time_remaining(attempt)
    )


def _calculate_time_remaining(attempt):
    """Calculate remaining time for timed quizzes"""
    if not attempt.quiz.time_limit:
        return None
    
    time_elapsed = datetime.now(timezone.utc) - attempt.started_at
    time_remaining = attempt.quiz.time_limit * 60 - time_elapsed.total_seconds()
    return max(0, time_remaining)


# ======================
# QUIZ SUBMISSION & RESULTS
# ======================

@app.route('/student/quizzes/attempt/<int:attempt_id>/submit', methods=['POST'])
@login_required
def submit_quiz(attempt_id):
    """Finalize and grade a quiz attempt"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    try:
        attempt = QuizAttempt.query.options(
            joinedload(QuizAttempt.answers).joinedload(QuizAnswer.question)
        ).get_or_404(attempt_id)
        
        if attempt.student_id != current_user.student_profile.id:
            abort(403, description="Not your quiz attempt")
        
        if attempt.completed_at:
            return redirect(url_for('student_quiz_results', attempt_id=attempt_id))
        
        # Grade the attempt
        attempt.completed_at = datetime.now(timezone.utc)
        correct_answers = 0
        
        for answer in attempt.answers:
            if answer.selected_answer == answer.question.correct_answer:
                answer.is_correct = True
                correct_answers += 1
            else:
                answer.is_correct = False
        
        attempt.score = correct_answers
        attempt.points_earned = (correct_answers / len(attempt.answers)) * attempt.quiz.total_points if attempt.answers else 0
        db.session.commit()
        
        return redirect(url_for('student_quiz_results', attempt_id=attempt_id))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Quiz submission error: {str(e)}")
        flash("Failed to submit quiz. Please try again.", "error")
        return redirect(url_for('student_take_quiz', attempt_id=attempt_id))


@app.route('/student/quizzes/attempt/<int:attempt_id>/results')
@login_required
def student_quiz_results(attempt_id):
    """Display quiz results and review"""
    if not current_user.is_student:
        abort(403, description="Access restricted to students only")

    try:
        # Get attempt with all related data
        attempt = QuizAttempt.query.options(
            joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
            joinedload(QuizAttempt.answers)
        ).get_or_404(attempt_id)
        
        if attempt.student_id != current_user.student_profile.id:
            abort(403, description="Not your quiz attempt")
        
        if not attempt.completed_at:
            flash("This quiz attempt is not yet completed", "warning")
            return redirect(url_for('student_take_quiz', attempt_id=attempt_id))
        
        # Calculate results
        correct_count = sum(1 for answer in attempt.answers if answer.is_correct)
        total_questions = len(attempt.quiz.questions)
        percentage_score = round((correct_count / total_questions) * 100, 2) if total_questions > 0 else 0
        
        return render_template('student/quizzes/results.html',
            attempt=attempt,
            quiz=attempt.quiz,
            correct_count=correct_count,
            total_questions=total_questions,
            percentage_score=percentage_score,
            class_average=_get_class_average(attempt.quiz_id)
        )
    
    except Exception as e:
        current_app.logger.error(f"Results loading error: {str(e)}")
        flash("An error occurred while loading results", "error")
        return redirect(url_for('student_quizzes'))


def _get_class_average(quiz_id):
    """Calculate class average for a quiz"""
    attempts = QuizAttempt.query.filter_by(
        quiz_id=quiz_id
    ).filter(
        QuizAttempt.completed_at.isnot(None)
    ).all()
    
    if not attempts:
        return None
    
    total_percentage = sum(
        (attempt.score / len(attempt.quiz.questions)) * 100 
        for attempt in attempts 
        if attempt.quiz.questions
    )
    return round(total_percentage / len(attempts), 2)


# ======================
# HELPER FUNCTIONS
# ======================

def can_take_quiz(student_id, quiz_id):
    """Check if student can take the quiz with current constraints"""
    quiz = Quiz.query.options(joinedload(Quiz.classroom)).get(quiz_id)
    if not quiz:
        return False
    
    # Check enrollment
    if not Enrollment.query.filter_by(
        student_id=student_id,
        class_id=quiz.classroom_id
    ).first():
        return False
    
    # Check quiz status
    if quiz.status != 'published' or quiz.is_deleted:
        return False
    
    # Check due date with timezone handling
    now = datetime.now(local_timezone)
    if quiz.due_date:
        due_date = quiz.due_date if quiz.due_date.tzinfo else quiz.due_date.replace(tzinfo=timezone.utc)
        if due_date.astimezone(local_timezone) < now:
            return False
    
    # Check attempt limit
    max_attempts = quiz.max_attempts or 1
    current_attempts = QuizAttempt.query.filter_by(
        student_id=student_id,
        quiz_id=quiz_id
    ).count()
    
    return current_attempts < max_attempts


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

@app.route('/student/messages/<int:message_id>')
@login_required
def student_view_message(message_id):
    if current_user.role != 'student' or not current_user.student_profile:
        abort(403)

    student = current_user.student_profile
    message = Message.query.options(
        joinedload(Message.sender_user),
        joinedload(Message.classroom),
        joinedload(Message.replies).joinedload(Message.sender_user)
    ).get_or_404(message_id)
    
    # Verify access
    if (message.recipient_id and message.recipient_id != student.id) or \
       (message.class_id and message.class_id not in [e.class_id for e in student.enrollments]):
        abort(403)
    
    # Mark as read when viewed
    if not message.is_read and message.recipient_id == student.id:
        message.is_read = True
        db.session.commit()
    
    thread = message.get_thread()
    
    return render_template('student/messages/view.html',
        message=message,
        thread=thread
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
        joinedload(Classroom.teacher).joinedload(Teacher.user)
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
        'quizzes': Quiz.query.filter_by(class_id=classroom.id).all()  # Add this line if you have quizzes
    } for classroom in classrooms]

    return render_template(
        'teacher_dashboard.html',
        username=current_user.username,
        email=current_user.email,
        classes=classes
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
    """Video conference route."""
    classes = Classroom.query.all()
    return render_template('video_conference.html', classes=classes, csrf_token=session.get('_csrf_token'))

@app.route('/start_session', methods=['POST'])
@login_required
def start_session():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Only teachers can create sessions'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Extract and validate inputs
        class_id = data.get('class_id')
        session_name = sanitize_input(data.get('session_name', '').strip())
        duration_hours = float(data.get('duration', 0))
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        user_timezone = data.get('timezone', current_user.timezone or 'UTC')

        # Validate class exists
        classroom = Classroom.query.get(class_id)
        if not classroom:
            return jsonify({'success': False, 'error': 'Class not found'}), 404

        # Validate session name
        if not session_name or len(session_name) > 100:
            return jsonify({'success': False, 'error': 'Session name must be 1-100 characters'}), 400

        # Parse and validate times
        try:
            timezone_obj = ZoneInfo(user_timezone)
            
            # Parse start and end times
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            
            # Ensure times are timezone-aware
            if start_time.tzinfo is None:
                start_time = timezone_obj.localize(start_time)
            if end_time.tzinfo is None:
                end_time = timezone_obj.localize(end_time)
                
            # Convert to UTC for storage
            start_time_utc = start_time.astimezone(ZoneInfo('UTC'))
            end_time_utc = end_time.astimezone(ZoneInfo('UTC'))
            
            # Validate time range
            if end_time_utc <= start_time_utc:
                return jsonify({'success': False, 'error': 'End time must be after start time'}), 400
                
            # Calculate duration from times
            calculated_duration = (end_time_utc - start_time_utc).total_seconds() / 3600
            if abs(calculated_duration - duration_hours) > 0.1:
                return jsonify({'success': False, 'error': 'Duration does not match time range'}), 400

            if calculated_duration > 8:
                return jsonify({'success': False, 'error': 'Session cannot exceed 8 hours'}), 400

        except Exception as e:
            current_app.logger.error(f"Error occurred: {str(e)}", exc_info=True)
            flash('An error occurred while processing your request.', 'danger')
            return jsonify({'success': False, 'error': 'Internal server error'}), 500
            current_app.logger.error(f"Error occurred: {str(e)}", exc_info=True)
            flash('An error occurred while processing your request.', 'danger')
            return jsonify({
                'success': False, 
                'error': f'Invalid time data: {str(e)}'
            }), 400

        # Generate room ID and links
        room_id = f"class-{class_id}-{uuid.uuid4().hex[:6]}"
        session_link = f"{request.host_url.rstrip('/')}/join/{room_id}"
        
        # Create session in database
        session = OnlineSession(
            room_id=room_id,
            session_name=session_name,
            session_link=session_link,
            class_id=class_id,
            creator_id=current_user.id,
            start_time=start_time_utc,
            end_time=end_time_utc,
            original_timezone=user_timezone,
            timezone=user_timezone,
            duration_minutes=int(calculated_duration * 60),
            status='scheduled',
            video_url=session_link
        )

        db.session.add(session)
        db.session.commit()

        # Prepare response data
        def format_datetime(dt, tz):
            return dt.astimezone(ZoneInfo(tz)).strftime('%Y-%m-%d %H:%M:%S')

        creator_time = f"{format_datetime(start_time_utc, user_timezone)} to {format_datetime(end_time_utc, user_timezone)}"
        utc_time = f"{start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} to {end_time_utc.strftime('%Y-%m-%d %H:%M:%S')}"

        return jsonify({
            'success': True,
            'session': {
                'room_id': room_id,
                'name': session_name,
                'link': session_link,
                'video_url': session_link,
                'original_timezone': user_timezone,
                'start_utc': start_time_utc.isoformat(),
                'end_utc': end_time_utc.isoformat(),
                'duration': calculated_duration,
                'class_id': class_id,
                'time_info': {
                    'creator': creator_time + f" ({user_timezone})",
                    'utc': utc_time + " (UTC)"
                }
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Session creation failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': 'Internal server error'
        }), 500
    
# Join Session Page
@app.route('/join')
@login_required
def join():
    """Redirect to student dashboard if no specific session is specified"""
    flash('Please select a session to join', 'info')
    return redirect(url_for('student_dashboard'))

@app.route('/student_sessions')
@login_required
def student_sessions():
    if current_user.role != 'student':
        abort(403)
    
    # Get all sessions for classes the student is enrolled in
    enrolled_class_ids = [e.class_id for e in current_user.student_profile.enrollments]
    active_sessions = OnlineSession.query.filter(
        OnlineSession.class_id.in_(enrolled_class_ids),
        OnlineSession.end_time > datetime.now(timezone.utc)  # Only future/current sessions
    ).join(Classroom).join(User, OnlineSession.creator_id == User.id).add_columns(
        OnlineSession,
        Classroom.class_name,
        User.username.label('instructor')
    ).order_by(OnlineSession.start_time.asc()).all()

    return render_template('student_sessions.html',
                         active_sessions=active_sessions,
                         current_time=datetime.now(timezone.utc))

# Join Session Route for Student
@app.route('/join_session/<room_id>')
@login_required
def join_session(room_id):
    session = OnlineSession.query.filter_by(room_id=room_id).first_or_404()
    
    # Verify student is enrolled in the class
    if current_user.role == 'student':
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.student_profile.id,
            class_id=session.class_id
        ).first()
        if not enrollment:
            abort(403, description="You're not enrolled in this class session")
    
    # Verify session is active
    now = datetime.now(timezone.utc)
    if now < session.start_time:
        return render_template('session_not_started.html', 
                            session=session,
                            time_until=(session.start_time - now))
    
    if now > session.end_time:
        return render_template('session_ended.html', 
                            session=session,
                            recording_url=session.recording_url)
    
    # For teachers - verify ownership
    if current_user.role == 'teacher' and session.creator_id != current_user.id:
        abort(403)
    
    return render_template('video_session.html',
                         room_id=room_id,
                         user_name=current_user.username,
                         user_role=current_user.role)

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
        return redirect(url_for('dashboard'))

    # ==============================
    # 2. Get Teacher and Department
    # ==============================
    try:
        teacher = current_user.teacher_profile
        if not teacher or not teacher.department:
            flash('Teacher department not found', 'danger')
            return redirect(url_for('dashboard'))

        department = teacher.department
    except Exception as e:
        flash('Error accessing teacher information', 'danger')
        app.logger.error(f"Teacher info error: {str(e)}")
        return redirect(url_for('dashboard'))

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
    submissions = None
    if current_user.role == 'teacher':
        assignments = Assignment.query.filter_by(author_id=current_user.id)\
                                   .options(
                                       joinedload(Assignment.submissions),
                                       joinedload(Assignment.subject),
                                       joinedload(Assignment.classroom)
                                   )\
                                   .order_by(Assignment.due_date.desc())\
                                   .all()
    else:
        enrolled_class_ids = [e.class_id for e in current_user.student_profile.enrollments]
        assignments = Assignment.query.filter(Assignment.class_id.in_(enrolled_class_ids))\
                                   .options(
                                       joinedload(Assignment.subject),
                                       joinedload(Assignment.classroom)
                                   )\
                                   .order_by(Assignment.due_date.desc())\
                                   .all()
        
        submissions = {s.assignment_id: s for s in Submission.query.filter_by(
            student_id=current_user.id
        ).all()}
    
    return render_template('teacher/assignments/list.html',
                        assignments=assignments,
                        student_submissions=submissions if current_user.role == 'student' else None,
                        now=datetime.now(local_timezone))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """Download submitted assignment files."""
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments'),
        filename,
        as_attachment=True
    )

@app.route('/assignments/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    """Create a new assignment with comprehensive validation"""
    if current_user.role != 'teacher':
        flash('Only teachers can create assignments', 'danger')
        return redirect(url_for('index'))

    form = AssignmentForm()
    teacher = current_user.teacher_profile
    
    try:
        # Initialize subject choices
        subjects = teacher.get_all_subjects()
        
        if not subjects:
            flash('You need to be assigned to at least one subject before creating assignments', 'danger')
            return redirect(url_for('teacher_dashboard'))

        # Format subjects with department info
        form.subject_id.choices = [
            (str(s.id), f"{s.name} - {s.department.name}")  # Ensure ID is string
            for s in sorted(subjects, key=lambda x: x.name)
        ]
        form.subject_id.choices.insert(0, ('', '-- Select Subject --'))

        # Get all active classrooms the teacher teaches with comprehensive info
        form.classroom_id.choices = [
            (str(c.id), f"{c.class_name} ({c.generate_code()}) - {c.subject.name} - {c.academic_year} S{c.semester}")
            for c in sorted(
                [cls for cls in teacher.classrooms if cls.is_active],
                key=lambda x: (x.academic_year, x.semester, x.class_name)
            )
        ]
        form.classroom_id.choices.insert(0, ('', '-- Select Class --'))

    except Exception as e:
        current_app.logger.error(f"Error loading form data: {str(e)}", exc_info=True)
        flash('Error loading assignment form. Please try again.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    if form.validate_on_submit():
        try:
            # Basic validation
            if not form.questions.data.strip():
                raise ValueError("Assignment questions cannot be empty")

            # Check for empty selections
            if not form.classroom_id.data:
                raise ValueError("Please select a class")
            if not form.subject_id.data:
                raise ValueError("Please select a subject")

            # Verify classroom belongs to teacher and is active
            classroom = Classroom.query.filter(
                Classroom.id == int(form.classroom_id.data),  # Convert to int here
                Classroom.teacher_id == teacher.id,
                Classroom.is_active == True
            ).first()

            if not classroom:
                raise ValueError("Invalid classroom selection or classroom is not active")

            # Verify subject matches classroom's subject if needed
            if int(form.subject_id.data) != classroom.subject_id:  # Convert to int here
                raise ValueError("Selected subject doesn't match the classroom's subject")

            # Create and save assignment
            assignment = Assignment(
                title=form.title.data.strip(),
                description=form.description.data.strip(),
                questions=form.questions.data.strip(),
                due_date=form.due_date.data,
                max_score=form.max_score.data,
                subject_id=classroom.subject_id,  # Use classroom's subject to ensure consistency
                class_id=classroom.id,
                author_id=current_user.id,
                is_published=True
            )

            db.session.add(assignment)
            db.session.commit()

            # Create activity log
            log_activity(
                user_id=current_user.id,
                action="Created Assignment",
                details=f"Assignment '{assignment.title}' for {classroom.class_name} ({classroom.generate_code()})",
                icon="fa-tasks"
            )

            flash('Assignment created successfully!', 'success')
            return redirect(url_for('view_assignment', assignment_id=assignment.id))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Assignment creation failed: {str(e)}", exc_info=True)
            flash('An error occurred while creating the assignment. Please try again.', 'danger')

    elif form.errors:
        current_app.logger.warning(f"Form validation errors: {form.errors}")
        flash('Please correct the errors in the form.', 'danger')

    return render_template(
        'teacher/assignments/create.html',
        form=form,
        now=datetime.now(local_timezone),
        min_date=(datetime.now(local_timezone) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
    )

@app.route('/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    """View assignment details with access control and grading."""
    # Fetch assignment with optimized queries
    assignment = Assignment.query.options(
        joinedload(Assignment.subject),
        joinedload(Assignment.classroom),
        joinedload(Assignment.author)
    ).options(
        load_only(Assignment.title, Assignment.description, Assignment.due_date,
                 Assignment.created_at, Assignment.max_score, Assignment.is_published,
                 Assignment.class_id, Assignment.author_id, Assignment.subject_id)
    ).get_or_404(assignment_id)
    
    # Convert description from Markdown to HTML (with sanitization)
    assignment.description_html = clean(
        markdown(assignment.description),
        tags=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 
              'a', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote'],
        attributes={'a': ['href', 'title']}
    )
    
    # Student access control
    if current_user.role == 'student':
        # Check enrollment and assignment visibility
        is_enrolled = Enrollment.query.filter_by(
            student_id=current_user.id,
            class_id=assignment.class_id
        ).first()
        
        if not is_enrolled or not assignment.is_published:
            flash('You do not have access to this assignment', 'danger')
            return redirect(url_for('dashboard'))
    
    # Get student submission and grade if exists
    student_submission = None
    student_grade = None
    
    if current_user.role == 'student':
        # Get submission without grade field
        student_submission = Submission.query.filter_by(
            assignment_id=assignment_id,
            student_id=current_user.id
        ).options(
            load_only(Submission.id, Submission.content, Submission.submitted_at)
        ).first()
        
        # Get grade information from Grades table
        student_grade = Grade.query.filter_by(
            student_id=current_user.id,
            subject_id=assignment.subject_id
        ).first()
        
        # Convert submission content to HTML if exists
        if student_submission and student_submission.content:
            student_submission.content_html = clean(
                markdown(student_submission.content),
                tags=['p', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'code'],
                attributes={'a': ['href']}
            )
    
    # Teacher view with submissions and grades
    submissions_with_grades = []
    if current_user.role == 'teacher' and assignment.author_id == current_user.id:
        # Get all submissions for this assignment
        submissions = db.session.query(Submission, User)\
            .join(User, Submission.student_id == User.id)\
            .filter(Submission.assignment_id == assignment_id)\
            .options(
                load_only(Submission.id, Submission.content, Submission.submitted_at),
                load_only(User.id, User.username)
            )\
            .order_by(Submission.submitted_at.desc())\
            .all()
        
        # Get all grades for students in this subject at once (more efficient)
        student_ids = [submission.student_id for submission, _ in submissions]
        grades = {g.student_id: g for g in Grade.query.filter(
            Grade.student_id.in_(student_ids),
            Grade.subject_id == assignment.subject_id
        ).all()}
        
        # Combine submissions with grade information
        submissions_with_grades = [{
            'submission': submission,
            'user': user,
            'grade': grades.get(submission.student_id)
        } for submission, user in submissions]
    
    return render_template('teacher/assignments/view.html', 
                         assignment=assignment,
                         submissions=submissions_with_grades,
                         student_submission=student_submission,
                         student_grade=student_grade,
                         now=datetime.now(local_timezone))

@app.route('/assignment/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
def submit_assignment(assignment_id):
    """Submit an assignment (student only)."""
    if current_user.role != 'student':
        flash('Only students can submit assignments', 'danger')
        return redirect(url_for('index'))

    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check enrollment
    is_enrolled = Enrollment.query.filter_by(
        student_id=current_user.student_profile.id,
        class_id=assignment.class_id
    ).first()
    if not is_enrolled:
        flash('You are not enrolled in this class', 'danger')
        return redirect(url_for('index'))
    
    # Check for existing submission
    existing_submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.student_profile.id
    ).first()
    if existing_submission:
        flash('You already submitted this assignment', 'warning')
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    form = SubmissionForm()
    if form.validate_on_submit():
        file_path = None
        if form.file.data:
            filename = secure_filename(f"{current_user.id}_{form.file.data.filename}")
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            form.file.data.save(file_path)
        
        submission = Submission(
            content=form.content.data,
            file_path=file_path,
            assignment_id=assignment_id,
            student_id=current_user.student_profile.id
        )
        db.session.add(submission)
        db.session.commit()
        flash('Assignment submitted successfully!', 'success')
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    return render_template('assignments/submit.html', form=form, assignment=assignment)

@app.route('/submission/<int:submission_id>/grade', methods=['GET', 'POST'])
@login_required
def grade_submission(submission_id):
    """Grade a student submission (teacher only)."""
    if current_user.role != 'teacher':
        flash('Only teachers can grade assignments', 'danger')
        return redirect(url_for('index'))

    submission = Submission.query.get_or_404(submission_id)
    assignment = submission.assignment
    
    if assignment.author_id != current_user.id:
        flash('You can only grade assignments you created', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            score = float(request.form.get('score'))
            feedback = request.form.get('feedback', '')
            
            if score < 0 or score > assignment.max_score:
                flash(f'Score must be between 0 and {assignment.max_score}', 'danger')
            else:
                submission.score = score
                submission.feedback = feedback
                db.session.commit()
                flash('Grade submitted successfully!', 'success')
                return redirect(url_for('view_assignment', assignment_id=assignment.id))
        except ValueError:
            flash('Please enter a valid score', 'danger')
    
    return render_template('teacher/assignments/grade.html', 
                         submission=submission,
                         assignment=assignment,
                         max_score=assignment.max_score)

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

@app.route('/teacher/quiz/<int:quiz_id>/analytics')
@login_required
def quiz_analytics(quiz_id):
    """Display analytics for a quiz"""
    # Verify user is a teacher
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    # Get the quiz
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Verify quiz ownership
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
    
    # Calculate analytics data
    attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id).all()
    # Add your analytics calculations here
    
    return render_template('teacher/quizzes/analytics.html',
                         quiz=quiz,
                         attempts=attempts)

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


@app.route('/teacher/quiz/<int:quiz_id>/results')
@login_required
def students_quiz_results(quiz_id):
    """View quiz attempts/results for students"""
    if current_user.role != 'teacher' or not hasattr(current_user, 'teacher_profile'):
        abort(403)
    
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
    
    # Get all attempts for this quiz
    attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id).order_by(QuizAttempt.completed_at.desc()).all()
    
    return render_template(
        'teacher/quizzes/results.html',
        quiz=quiz,
        attempts=attempts,
        now=datetime.now(local_timezone)
    )


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
    """Edit an existing quiz"""
    if current_user.role != 'teacher':
        flash('Access denied. Only teachers can edit quizzes.', 'danger')
        return redirect(url_for('index'))

    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)

    form = QuizEditForm(obj=quiz)
    teacher = current_user.teacher_profile
    
    # Set choices for dropdowns
    form.subject_id.choices = [(s.id, s.name) for s in teacher.subjects]
    form.classroom_id.choices = [(c.id, c.class_name) for c in teacher.classrooms]
    
    # Initialize questions
    if request.method == 'GET':
        for question in quiz.questions:
            question_form = QuestionForm()
            question_form.id.data = question.id
            question_form.text.data = question.text
            question_form.options.data = ', '.join(question.options)
            question_form.correct_option.choices = [(i, f"{chr(65 + i)}: {opt}") 
                                                 for i, opt in enumerate(question.options)]
            question_form.correct_option.data = question.correct_option
            question_form.points.data = question.points
            question_form.time_limit.data = question.time_limit
            form.questions.append_entry(question_form)

    if request.method == 'POST':
        action = request.form.get('action', 'save_draft')
        form.is_published.data = (action == 'save_publish')
        
        if form.validate():
            try:
                # Update quiz basic info
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
                
                # Update or add questions
                for q_form in form.questions:
                    if q_form.id.data:  # Existing question
                        question = Question.query.get(q_form.id.data)
                        if question and question.quiz_id == quiz.id:
                            question.text = q_form.text.data
                            question.options = [opt.strip() for opt in q_form.options.data.split(',')]
                            question.correct_option = int(q_form.correct_option.data)
                            question.points = q_form.points.data
                            question.time_limit = q_form.time_limit.data
                    else:  # New question
                        options = [opt.strip() for opt in q_form.options.data.split(',')]
                        quiz.questions.append(Question(
                            text=q_form.text.data,
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
                        pass  # Add notification logic here
                
                # Recalculate total points
                quiz.total_points = sum(q.points for q in quiz.questions)
                
                db.session.commit()
                
                flash('Quiz updated successfully!', 'success')
                return redirect(url_for('view_quiz', quiz_id=quiz.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating quiz: {str(e)}', 'danger')
                app.logger.error(f"Quiz update error: {str(e)}", exc_info=True)
    
    return render_template('teacher/quizzes/edit.html',
                         form=form,
                         quiz=quiz)

@app.route('/get_new_question_form')
@login_required
def get_new_question_form():
    """Endpoint to fetch a new empty question form (AJAX)"""
    if current_user.role != 'teacher':
        abort(403)
        
    index = request.args.get('index', 1)
    form = QuizEditForm()
    question_form = QuestionForm()
    
    return render_template('partials/question_form.html',
                         question=question_form,
                         index=index)

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
    resource = Resource.query.options(
        joinedload(Resource.classroom),
        joinedload(Resource.subject)
    ).get_or_404(resource_id)
    
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
                
                if not allowed_file(file.filename, resource.resource_type):
                    allowed = ', '.join(ALLOWED_EXTENSIONS.get(resource.resource_type, []))
                    flash(f'Invalid file type. Allowed types: {allowed}', 'error')
                    return redirect(request.url)
                
                # Delete old file
                old_file_path = os.path.join(
                    current_app.root_path,
                    current_app.config['UPLOAD_FOLDER'],
                    resource.file_path
                )
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                
                # Save new file
                filename = secure_filename(file.filename)
                unique_filename = f"{datetime.now().timestamp()}_{filename}"
                save_folder = get_resource_folder(resource.resource_type)
                save_path = os.path.join(save_folder, unique_filename)
                file.save(save_path)
                
                # Update file info
                resource.file_path = os.path.join(f"{resource.resource_type}s", unique_filename)
                resource.file_name = filename
                resource.file_size = os.path.getsize(save_path)
                resource.file_type = filename.rsplit('.', 1)[1].lower()
            
            db.session.commit()
            flash('Resource updated successfully!', 'success')
            return redirect(url_for('view_resource', resource_id=resource.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating resource: {str(e)}', 'error')
            return redirect(request.url)
    
    # GET request - show form
    subjects = Subject.query.order_by(Subject.name).all()
    # Get the teacher profile first
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

# ---------- MISCELLANEOUS ROUTES ----------

@app.route('/grades')
def grades():
    """View grades."""
    grades = Grade.query.all()
    if not grades:
        flash('No grades available at the moment.', 'info')
    return render_template('grades.html', grades=grades)

# ---------- STUDY RESOURCES ROUTES ----------
@app.route('/study-resources')
@login_required
def study_resources():
    if current_user.role != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('student_dashboard'))
    
    try:
        student = Student.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Get enrolled class IDs safely
        enrolled_class_ids = [enrollment.class_id for enrollment in student.enrollments] if student.enrollments else []
        
        notes = Resource.query.filter(
            Resource.classroom_id.in_(enrolled_class_ids),
            Resource.is_approved == True
        ).join(Subject).join(User).join(Teacher).order_by(Resource.upload_date.desc()).all()
        
        # Get unique subjects for the student
        subjects = Subject.query.join(Classroom).join(Enrollment).filter(
            Enrollment.student_id == student.id
        ).distinct().all()
        
        return render_template('student/study_resources.html', 
                            notes=notes, 
                            subjects=subjects,
                            current_user=current_user)
                            
    except Exception as e:
        app.logger.error(f"Error in study_resources: {str(e)}", exc_info=True)
        flash('An error occurred while loading resources', 'error')
        return redirect(url_for('student_dashboard'))
    
# ---------- STUDENT NOTE DOWNLOAD ROUTE ----------
@app.route('/download-note/<int:note_id>')
@login_required
def student_download_notes(note_id):
    note = Resource.query.get_or_404(note_id)
    
    # Verify student is enrolled in the class
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not any(enrollment.class_id == note.classroom_id for enrollment in student.enrollments):
        abort(403)
    
    # Increment download count
    note.download_count += 1
    db.session.commit()
    
    return send_from_directory(
        os.path.join(current_app.root_path, 'uploads/notes'),
        note.file_path,
        as_attachment=True,
        download_name=note.file_name
    )