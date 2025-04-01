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
from wtforms.validators import DataRequired
from zoneinfo import ZoneInfo  # Python 3.9+ (preferred) or use pytz as fallback
from forms import AssignmentForm, SubmissionForm  # Import the forms
from forms import QuizCreateForm  # Ensure this import is added at the top of the file



from flask import (abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, url_for, current_app)
from flask_login import current_user, login_required, login_user, logout_user
from PIL import Image
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import face_recognition
from app import app, db
from models import (Activity, Assignment, Attendance, Classroom, Department,
                    Grade, Resource, OnlineSession, Question, Quiz, Student,
                    Submission, Subject, Teacher, User, Enrollment, QuizAttempt, QuizAnswer)

# Configuration
UPLOAD_FOLDER = 'uploads/faces'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
                current_app.logger.error(f"An error occurred: {e}")
                return jsonify({'success': False, 'error': 'An error occurred'}), 500
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
        # Face recognition login
        if image_data := request.form.get('image_data'):
            try:
                _, encoded = image_data.split(",", 1)
                face_image_data = BytesIO(base64.b64decode(encoded))
                
                # Debugging (optional)
                debug_image_path = os.path.join(UPLOAD_FOLDER, "debug_image.jpg")
                with open(debug_image_path, "wb") as f:
                    f.write(base64.b64decode(encoded))

                face_image = face_recognition.load_image_file(face_image_data)
                face_locations = face_recognition.face_locations(face_image)
                
                if not face_locations:
                    flash('No face detected in the captured image. Please try again.', 'danger')
                    return redirect(url_for('login'))

                face_encoding = face_recognition.face_encodings(face_image, face_locations)[0]
                
                # Compare with registered users
                users_with_faces = User.query.filter(User.face_image.isnot(None)).all()
                for user in users_with_faces:
                    stored_face_path = os.path.join(UPLOAD_FOLDER, user.face_image)
                    if os.path.exists(stored_face_path):
                        stored_image = face_recognition.load_image_file(stored_face_path)
                        stored_encoding = face_recognition.face_encodings(stored_image)[0]
                        
                        if face_recognition.compare_faces([stored_encoding], face_encoding, tolerance=0.6)[0]:
                            login_user(user)
                            flash('Login successful!', 'success')
                            return redirect(url_for(f'{user.role}_dashboard'))

                flash('Face does not match our records!', 'danger')
            except Exception as e:
                flash(f'Error during face recognition: {e}', 'danger')
                return redirect(url_for('login'))

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

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    """Student dashboard showing available sessions"""
    if current_user.role != 'student':
        flash('Access denied. Students only.', 'danger')
        return redirect(url_for('index'))

    now = datetime.now(timezone.utc)
    sessions = OnlineSession.query.order_by(OnlineSession.start_time.asc()).all()
    
    # Categorize sessions
    active_sessions = []
    upcoming_sessions = []
    past_sessions = []
    
    for session in sessions:
        # Check if student is enrolled in this session's class
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.id,
            class_id=session.class_id
        ).first()
        
        if enrollment:  # Only show sessions for enrolled classes
            if now >= session.start_time and (not session.end_time or now <= session.end_time):
                active_sessions.append(session)
            elif now < session.start_time:
                upcoming_sessions.append(session)
            else:
                past_sessions.append(session)
    
    return render_template(
        'student_dashboard.html',
        active_sessions=active_sessions,
        upcoming_sessions=upcoming_sessions,
        past_sessions=past_sessions,
        username=current_user.username,
        current_time=now,
        timezone=current_user.timezone or 'UTC'
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
        'students': Enrollment.query.filter_by(class_id=classroom.id).all()
    } for classroom in classrooms]

    return render_template('teacher_dashboard.html', 
                         username=current_user.username, 
                         classes=classes)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard route with statistics."""
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    # Time period calculations
    current_time = datetime.utcnow()
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
from datetime import datetime, timezone, timedelta
from flask import jsonify, request, render_template, redirect, url_for, flash
from werkzeug.exceptions import NotFound

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
    enrolled_class_ids = [e.class_id for e in current_user.student_profile.class_enrollments]
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
    """Add a new student (teacher only)."""
    if current_user.role != 'teacher':
        flash('Access denied. You must be a teacher to access this page.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Get form data
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            date_of_birth = request.form['date_of_birth']
            class_id = request.form.get('class_id')
            department_id = request.form['department_id']

            # Validate existing user
            if User.query.filter((User.username == username) | (User.email == email)).first():
                flash('Username or Email already exists. Please choose another.', 'danger')
                return redirect(url_for('add_student'))

            # Create user
            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                role='student'
            )
            db.session.add(new_user)
            db.session.flush()

            # Create student profile
            new_student = Student(
                user_id=new_user.id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                department_id=department_id
            )
            db.session.add(new_student)
            db.session.flush()

            # Link to class if provided
            if class_id:
                db.session.add(Enrollment(class_id=int(class_id), student_id=new_student.id))

            db.session.commit()
            flash('Student added successfully!', 'success')
            return redirect(url_for('add_student'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}. Please try again later.', 'danger')

    # GET request - show form
    classes = Classroom.query.all()
    departments = Department.query.all()
    return render_template('teacher/add_student.html', 
                         classes=classes, 
                         departments=departments)

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
            'teacher_name': request.form.get('teacher_name', '').strip(),
            'specialization': request.form.get('specialization', '').strip(),
            'department_id': request.form.get('department', '').strip(),
            'subjects': request.form.getlist('subjects')  # For multiple subject selection
        }

        # Validation
        required_fields = ['username', 'email', 'password', 'teacher_name', 'department_id']
        if not all(form_data[field] for field in required_fields):
            flash("All required fields must be filled", 'danger')
        else:
            try:
                # Create user
                new_user = User(
                    username=form_data['username'],
                    email=form_data['email'],
                    password=generate_password_hash(form_data['password']),
                    role='teacher'
                )
                db.session.add(new_user)
                db.session.flush()

                # Create teacher
                new_teacher = Teacher(
                    user_id=new_user.id,
                    teacher_name=form_data['teacher_name'],
                    specialization=form_data['specialization'],
                    department_id=int(form_data['department_id'])
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

    teachers = Teacher.query.all()
    subjects = Subject.query.all()
    current_year = datetime.now().year
    academic_years = [f"{year}-{year+1}" for year in range(current_year-1, current_year+2)]
    semesters = [1, 2, 3]  # Assuming 3 semesters

    if request.method == 'POST':
        try:
            class_name = request.form.get('class_name', '').strip()
            subject_id = request.form.get('subject_id')
            teacher_id = request.form.get('teacher_id')
            academic_year = request.form.get('academic_year')
            semester = request.form.get('semester')

            # Validate required fields
            if not all([class_name, subject_id, teacher_id, academic_year, semester]):
                flash('All fields are required.', 'danger')
                return redirect(url_for('add_class'))

            # Check if teacher and subject exist
            teacher = Teacher.query.get(teacher_id)
            subject = Subject.query.get(subject_id)
            if not teacher or not subject:
                flash('Invalid teacher or subject selected.', 'danger')
                return redirect(url_for('add_class'))

            # Check for duplicate class name
            if Classroom.query.filter(Classroom.class_name.ilike(class_name)).first():
                flash(f'A class with the name "{class_name}" already exists!', 'danger')
                return redirect(url_for('add_class'))

            # Create new class
            new_class = Classroom(
                class_name=class_name,
                subject_id=subject_id,
                teacher_id=teacher_id,
                academic_year=academic_year,
                semester=int(semester),
                is_active=True,
                max_students=30  # Default value
            )

            db.session.add(new_class)
            db.session.commit()
            flash(f'Class "{class_name}" added successfully!', 'success')
            return redirect(url_for('add_class'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding class: {str(e)}")
            flash('An error occurred while adding the class.', 'danger')
            return redirect(url_for('add_class'))

    return render_template('admin/add_class.html',
                         teachers=teachers,
                         subjects=subjects,
                         academic_years=academic_years,
                         semesters=semesters)

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

# ---------- ASSIGNMENT/QUIZ ROUTES ----------


# ---------- ASSIGNMENT ROUTES ----------

@app.route('/assignments/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    """Create a new assignment (teacher only)."""
    if current_user.role != 'teacher':
        flash('Only teachers can create assignments', 'danger')
        return redirect(url_for('index'))

    form = AssignmentForm()
    
    # Populate the subject and classroom dropdowns
    form.subject_id.choices = [(s.id, s.name) for s in current_user.teacher_profile.subjects]
    form.classroom_id.choices = [
        (c.id, f"{c.class_name} ({c.class_code})") 
        for c in Classroom.query.filter_by(teacher_id=current_user.id).all()
    ]
    
    if form.validate_on_submit():
        try:
            assignment = Assignment(
                title=form.title.data,
                description=form.description.data,
                due_date=form.due_date.data,
                max_score=form.max_score.data,
                subject_id=form.subject_id.data,
                class_id=form.classroom_id.data,
                author_id=current_user.id
            )
            db.session.add(assignment)
            db.session.commit()
            flash('Assignment created successfully!', 'success')
            return redirect(url_for('assignments'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating assignment: ' + str(e), 'danger')
            current_app.logger.error(f"Assignment creation error: {str(e)}")
    
    return render_template('teacher/assignments/create.html', form=form)

@app.route('/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    """View assignment details with access control."""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Student access check
    if current_user.role == 'student':
        is_enrolled = Enrollment.query.filter_by(
            student_id=current_user.id,
            class_id=assignment.class_id
        ).first()
        if not is_enrolled:
            flash('You are not enrolled in this class', 'danger')
            return redirect(url_for('index'))
    
    # Teacher sees submissions
    submissions = []
    if current_user.role == 'teacher' and assignment.author_id == current_user.id:
        submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    return render_template('assignments/view.html', 
                         assignment=assignment,
                         submissions=submissions)

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
        student_id=current_user.id,
        class_id=assignment.class_id
    ).first()
    if not is_enrolled:
        flash('You are not enrolled in this class', 'danger')
        return redirect(url_for('index'))
    
    # Check for existing submission
    existing_submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).first()
    if existing_submission:
        flash('You already submitted this assignment', 'warning')
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    form = SubmissionForm()
    if form.validate_on_submit():
        file_path = None
        if form.file.data:
            filename = secure_filename(f"{current_user.id}_{form.file.data.filename}")
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            form.file.data.save(file_path)
        
        submission = Submission(
            content=form.content.data,
            file_path=file_path,
            assignment_id=assignment_id,
            student_id=current_user.id
        )
        db.session.add(submission)
        db.session.commit()
        flash('Assignment submitted successfully!', 'success')
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    return render_template('assignments/submit.html', form=form, assignment=assignment)

# ---------- QUIZ ROUTES ----------

@app.route('/quizzes')
@login_required
def view_quiz():
    if current_user.role != 'teacher':
        abort(403)
    
    quizzes = Quiz.query.filter_by(teacher_id=current_user.teacher_profile.id)\
                       .order_by(Quiz.created_at.desc())\
                       .all()
    
    return render_template('teacher/quizzes/list.html', quizzes=quizzes)

@app.route('/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if current_user.role != 'teacher':
        abort(403)

    form = QuizCreateForm()
    form.subject_id.choices = [(s.id, f"{s.name} ({s.department.name})") 
                             for s in current_user.teacher_profile.subjects]
    form.classroom_id.choices = [(c.id, f"{c.class_name} ({c.subject.name})") 
                                for c in current_user.teacher_profile.classrooms]

    if form.validate_on_submit():
        try:
            quiz = Quiz(
                title=form.title.data,
                description=form.description.data,
                subject_id=form.subject_id.data,
                classroom_id=form.classroom_id.data,
                due_date=form.due_date.data,
                time_limit=form.duration.data * 60,
                teacher_id=current_user.teacher_profile.id
            )
            
            for question_data in form.questions.data:
                options = [opt.strip() for opt in question_data['options'].split(',') if opt.strip()]
                question = Question(
                    text=question_data['text'],
                    options=options,
                    correct_option=question_data['correct_option'],
                    points=question_data['points'],
                    time_limit=question_data['time_limit']
                )
                quiz.questions.append(question)
            
            db.session.add(quiz)
            db.session.commit()
            flash('Quiz created successfully!', 'success')
            return redirect(url_for('teacher_quiz_view', quiz_id=quiz.id))  # Changed to teacher_quiz_view
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating quiz: {str(e)}', 'danger')
            app.logger.error(f"Quiz creation failed: {str(e)}")

    return render_template('teacher/quizzes/create.html', form=form)

@app.route('/teacher/quiz/<int:quiz_id>')  # Added this new route
@login_required
def teacher_quiz_view(quiz_id):
    if current_user.role != 'teacher':
        abort(403)
        
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
        
    return render_template('teacher/quizzes/view.html', quiz=quiz)

@app.route('/api/save_draft', methods=['POST'])
@login_required
def save_draft():
    if current_user.role != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    
    try:
        quiz = Quiz(
            title=data.get('title', 'Untitled Quiz'),
            description=data.get('description', ''),
            subject_id=data.get('subject_id'),
            classroom_id=data.get('classroom_id'),
            due_date=datetime.fromisoformat(data.get('due_date')) if data.get('due_date') else None,
            time_limit=int(data.get('duration', 30)) * 60,
            teacher_id=current_user.teacher_profile.id,
            status='draft'
        )
        
        for q in data.get('questions', []):
            options = [opt.strip() for opt in q.get('options', '').split(',') if opt.strip()]
            question = Question(
                text=q.get('text', ''),
                options=options,
                correct_option=q.get('correct_option', 'A'),
                points=int(q.get('points', 1)),
                time_limit=int(q.get('time_limit', 60))
            )
            quiz.questions.append(question)
        
        db.session.add(quiz)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'quiz_id': quiz.id,
            'message': 'Draft saved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Draft save failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/quiz/<int:quiz_id>/preview')
@login_required
def preview_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
        
    if quiz.status != 'draft':
        flash('Only draft quizzes can be previewed', 'warning')
        return redirect(url_for('teacher_quiz_view', quiz_id=quiz_id))  # Changed to teacher_quiz_view
    
    return render_template('teacher/quizzes/preview.html', quiz=quiz)

@app.route('/quiz/<int:quiz_id>/publish', methods=['POST'])
@login_required
def publish_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if quiz.teacher_id != current_user.teacher_profile.id:
        abort(403)
        
    if quiz.status != 'draft':
        flash('Only draft quizzes can be published', 'warning')
        return redirect(url_for('teacher_quiz_view', quiz_id=quiz_id))  # Changed to teacher_quiz_view
    
    if not quiz.title or not quiz.questions:
        flash('Quiz must have a title and at least one question', 'danger')
        return redirect(url_for('preview_quiz', quiz_id=quiz_id))
    
    quiz.status = 'published'
    db.session.commit()
    
    flash('Quiz published successfully!', 'success')
    return redirect(url_for('teacher_quiz_view', quiz_id=quiz_id))  # Changed to teacher_quiz_view

# ---------- RESOURCES MANAGEMENT ROUTES ----------

# Configuration
# Define allowed file extensions
ALLOWED_EXTENSIONS = {
    'document': ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt'],
    'image': ['jpg', 'jpeg', 'png', 'gif'],
    'audio': ['mp3', 'wav'],
    'video': ['mp4', 'mov']
}

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
                upload_date=datetime.utcnow(),
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
        enrolled_class_ids = [enrollment.class_id for enrollment in student.class_enrollments] if student.class_enrollments else []
        
        notes = Resource.query.filter(
            Resource.classroom_id.in_(enrolled_class_ids),
            Resource.is_approved == True
        ).join(Subject).join(User).join(Teacher).order_by(Resource.upload_date.desc()).all()
        
        # Get unique subjects for the student
        subjects = Subject.query.join(Classroom).join(Enrollment).filter(
            Enrollment.student_id == student.id
        ).distinct().all()
        
        return render_template('study_resources.html', 
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
    if not any(enrollment.class_id == note.classroom_id for enrollment in student.class_enrollments):
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