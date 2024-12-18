from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app import app, db
from models import User, OnlineSession, Assignment, Quiz, Class, Question, Teacher, Department
from datetime import datetime

# ---------- ROUTES ----------

# Home Route
@app.route('/')
def index():
    return render_template('index.html')

# Video Conference Route
@app.route('/video_conference')
@login_required
def video_conference():
    return render_template('video_conference.html', username=current_user.username)

# Join Session Page
@app.route('/join')
@login_required
def join():
    return render_template('student/join.html', username=current_user.username)

# Student Dashboard Route
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    sessions = OnlineSession.query.order_by(OnlineSession.created_at.desc()).all()
    return render_template('student_dashboard.html', sessions=sessions, username=current_user.username)

# Join Session Route for Student
@app.route('/join_session/<room_id>')
@login_required
def join_session(room_id):
    session = OnlineSession.query.filter_by(room_id=room_id).first()
    if not session:
        flash('Session not found.', 'danger')
        return redirect(url_for('student_dashboard'))

    return render_template(
        'student/join.html',
        session=session,
        username=current_user.username
    )

# Teacher Dashboard Route
@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher_dashboard.html', username=current_user.username, classes=classes)

# Admin Dashboard Route
# Admin Dashboard Route
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # Check if the current user is an admin
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    # Example of fetching relevant data for the admin (e.g., teachers, students, etc.)
    teachers = User.query.filter_by(role='teacher').all()
    students = User.query.filter_by(role='student').all()
    classes = Class.query.all()  # Adjust as needed for class data
    # reports = Report.query.all()  # Adjust as needed for report data

    # Render the admin dashboard template
    return render_template('admin_dashboard.html', username=current_user.username, teachers=teachers, students=students, classes=classes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            # Redirect based on user role (student, teacher, or admin)
            if user.role == 'student':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user.role == 'admin':  # Redirect admin to admin dashboard
                return redirect(url_for('admin_dashboard'))

        flash('Invalid email or password!', 'danger')

    return render_template('login.html')

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip().capitalize()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip()

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password, role='student')
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('Registration successful!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('register.html')

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ---------- SESSION MANAGEMENT ----------

# Start Online Session (Teacher)
@app.route('/start_session', methods=['POST'])
@login_required
def start_session():
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    try:
        room_id = f"room-{int(datetime.now().timestamp())}"
        session_name = request.form.get('session_name', 'Default Session Name')
        session_link = f"{request.host_url}join_session/{room_id}"

        session = OnlineSession(
            room_id=room_id,
            session_name=session_name,
            session_link=session_link,
            created_by=current_user.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow()
        )
        db.session.add(session)
        db.session.commit()

        return jsonify({'roomID': room_id, 'sessionLink': session_link}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ---------- QUIZZES AND ASSIGNMENTS ----------

@app.route('/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        class_id = request.form.get('class_id')

        # Create a new Assignment instance
        assignment = Assignment(
            title=title,
            description=description,
            due_date=datetime.strptime(due_date, '%Y-%m-%d'),
            class_id=class_id,
            created_by=current_user.id
        )
        db.session.add(assignment)
        db.session.commit()

        flash('Assignment created successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))

    # Fetch all the classes taught by the teacher
    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/create_assignment.html', classes=classes)

# Add Quiz (Teacher)
@app.route('/add_quiz/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_quiz(session_id):
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        questions = request.form.getlist('questions')
        options = request.form.getlist('options')
        correct_answers = request.form.getlist('correct_answers')

        quiz = Quiz(title=title, session_id=session_id, class_id=None)
        db.session.add(quiz)
        db.session.flush()

        for question, option, correct_answer in zip(questions, options, correct_answers):
            question_obj = Question(
                text=question,
                options=option,
                correct_option=correct_answer,
                quiz_id=quiz.id
            )
            db.session.add(question_obj)

        db.session.commit()
        flash('Quiz added successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))

    return render_template('add_quiz.html', session_id=session_id)

@app.route('/get_session_data/<roomID>', methods=['GET'])
def get_session_data(roomID):
    session = get_session_from_db(roomID)  # Fetch session from your database
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify({
        "startTime": session.start_time.isoformat(),
        "endTime": session.end_time.isoformat(),
    })


@app.route('/create_session', methods=['POST'])
@login_required
def create_session():
    if current_user.role != 'teacher':
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Parse JSON data from the request
        data = request.get_json()
        room_id = data.get('roomID')
        session_link = data.get('sessionLink')
        start_time = data.get('startTime')
        end_time = data.get('endTime')

        # Ensure all required data is present
        if not all([room_id, session_link, start_time, end_time]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Create a new session record
        new_session = OnlineSession(
            room_id=room_id,
            session_name="Default Session Name",  # Adjust as needed
            session_link=session_link,
            start_time=start_time,
            end_time=end_time,
            created_by=current_user.id
        )

        # Add to database and commit
        db.session.add(new_session)
        db.session.commit()

        return jsonify({'message': 'Session created successfully!'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/add_teacher', methods=['GET', 'POST'])
@login_required
def add_teacher():
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    # Fetch all departments
    departments = Department.query.all()

    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        teacher_name = request.form.get('teacher_name').strip()
        subject = request.form.get('subject').strip()
        department_id = request.form.get('department')

        # Validation
        errors = []

        # Check for required fields
        if not username or not email or not password or not confirm_password or not teacher_name or not subject or not department_id:
            errors.append("All fields are required.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Check if username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            errors.append("A user with this username or email already exists.")

        if errors:
            # Return errors with previously entered data
            return render_template(
                'admin/add_teacher.html',
                errors=errors,
                departments=departments,
                form_data={
                    'username': username,
                    'email': email,
                    'teacher_name': teacher_name,
                    'subject': subject,
                    'department_id': department_id
                }
            )

        # Hash the password and create user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_teacher_user = User(username=username, email=email, password=hashed_password, role='teacher')
        db.session.add(new_teacher_user)
        db.session.commit()

        # Create teacher record
        teacher = Teacher(user_id=new_teacher_user.id, teacher_name=teacher_name, subject=subject, department_id=department_id)
        db.session.add(teacher)
        db.session.commit()

        flash('Teacher added successfully!', 'success')
        return redirect(url_for('add_teacher'))

    return render_template('admin/add_teacher.html', departments=departments)


@app.route('/add_department', methods=['GET', 'POST'])
@login_required
def add_department():
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name').strip()
        description = request.form.get('description').strip()

        if Department.query.filter_by(name=name).first():
            flash('Department already exists!', 'danger')
            return render_template('admin/add_department.html')

        new_department = Department(name=name, description=description)
        db.session.add(new_department)
        db.session.commit()

        flash('Department added successfully!', 'success')
        return render_template('admin/add_department.html')

    return render_template('admin/add_department.html')

@app.route('/departments', methods=['GET'])
@login_required
def view_departments():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    departments = Department.query.all()
    return render_template('admin/view_departments.html', departments=departments)

@app.route('/delete_department/<int:id>', methods=['POST'])
@login_required
def delete_department(id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    department = Department.query.get_or_404(id)
    db.session.delete(department)
    db.session.commit()

    flash('Department deleted successfully!', 'success')
    return redirect(url_for('view_departments'))

@app.route('/add_class', methods=['GET', 'POST'])
@login_required
def add_class():
    if current_user.role != 'admin':
        flash('Access denied. You must be an admin to access this page.', 'danger')
        return redirect(url_for('index'))

    teachers = Teacher.query.all()  # Fetch all teachers for the dropdown list

    if request.method == 'POST':
        class_name = request.form.get('class_name', '').strip()
        subject = request.form.get('subject', '').strip()
        teacher_id = request.form.get('teacher_id')

        # Validation
        if not class_name or not subject or not teacher_id:
            flash('All fields are required. Please fill out the form correctly.', 'danger')
            return render_template('admin/add_class.html', teachers=teachers)

        try:
            # Ensure teacher exists
            teacher = Teacher.query.get(teacher_id)
            if not teacher:
                flash('Invalid teacher selected.', 'danger')
                return render_template('admin/add_class.html', teachers=teachers)

            # Check for duplicate class names (optional constraint)
            existing_class = Class.query.filter_by(name=class_name).first()
            if existing_class:
                flash(f'A class with the name "{class_name}" already exists!', 'danger')
                return render_template('admin/add_class.html', teachers=teachers)

            # Create and save the new class
            new_class = Class(name=class_name, subject=subject, teacher_id=teacher_id)
            db.session.add(new_class)
            db.session.commit()

            flash(f'Class "{class_name}" added successfully!', 'success')
            return redirect(url_for('add_class'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return render_template('admin/add_class.html', teachers=teachers)

    return render_template('admin/add_class.html', teachers=teachers)