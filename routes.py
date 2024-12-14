from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app import app, db
from models import User, OnlineSession, Assignment, Quiz, Class, Question
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
@app.route('/join_session/<room_id>', methods=['GET'])
@login_required
def join_session(room_id):
    session = OnlineSession.query.filter_by(room_id=room_id).first()

    if not session:
        flash("Session not found!", 'danger')
        return redirect(url_for('student_dashboard'))

    return render_template('student/join.html', session=session, username=current_user.username)

# Teacher Dashboard Route
@app.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    classes = Class.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher_dashboard.html', username=current_user.username, classes=classes)

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('student_dashboard') if user.role == 'student' else url_for('teacher_dashboard'))

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

@app.route('/get_session_data/<room_id>', methods=['GET'])
def get_session_data(room_id):
    session = OnlineSession.query.filter_by(room_id=room_id).first()
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({
        'roomID': session.room_id,
        'startTime': session.start_time.isoformat(),
        'endTime': session.end_time.isoformat(),
        'sessionLink': session.session_link,
    })

@app.route('/create_session', methods=['POST'])
def create_session():
    try:
        data = request.json
        room_id = data.get('roomID')
        session_name = data.get('sessionName')
        session_link = data.get('sessionLink')
        start_time = datetime.fromisoformat(data.get('startTime'))
        end_time = datetime.fromisoformat(data.get('endTime'))

        if not (room_id and start_time and end_time):
            return jsonify({'error': 'Missing required fields'}), 400

        new_session = OnlineSession(
            room_id=room_id,
            session_name=session_name,
            session_link=session_link,
            start_time=start_time,
            end_time=end_time,
            created_by=current_user.id
        )
        db.session.add(new_session)
        db.session.commit()

        return jsonify({'message': 'Session created successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
