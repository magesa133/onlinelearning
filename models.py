from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask import current_app
from sqlalchemy import func, event
from datetime import datetime, timezone, timedelta
import os
import json

db = SQLAlchemy()

class UserRole:
    STUDENT = 'student'
    TEACHER = 'teacher'
    ADMIN = 'admin'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    face_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    timezone = db.Column(db.String(50), default='UTC')  # Default to UTC


    # Relationships
    teacher_profile = db.relationship('Teacher', back_populates='user', uselist=False, cascade='all, delete-orphan')
    student_profile = db.relationship('Student', back_populates='user', uselist=False, cascade='all, delete-orphan')
    uploaded_resources = db.relationship('Resource', back_populates='teacher')
    created_assignments = db.relationship('Assignment', back_populates='author', cascade='all, delete-orphan')
    created_sessions = db.relationship('OnlineSession', back_populates='creator', cascade='all, delete-orphan')
    comments = db.relationship('ResourceComment', back_populates='user')

    def get_submissions(self):
        if self.role == UserRole.STUDENT and self.student_profile:
            return self.student_profile.submissions
        return []

    def __repr__(self):
        return f"<User {self.username}>"

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    students = db.relationship('Student', back_populates='department')
    teachers = db.relationship('Teacher', back_populates='department')
    subjects = db.relationship('Subject', back_populates='department')

    def __repr__(self):
        return f"<Department {self.name}>"

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))

    department = db.relationship('Department', back_populates='subjects')
    teachers = db.relationship('Teacher', secondary='teacher_subjects', back_populates='subjects')
    classrooms = db.relationship('Classroom', back_populates='subject')
    resources = db.relationship('Resource', back_populates='subject', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', back_populates='subject', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', back_populates='subject', cascade='all, delete-orphan')
    grades = db.relationship('Grade', back_populates='subject', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Subject {self.name}>"

teacher_subjects = db.Table('teacher_subjects',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subjects.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    teacher_name = db.Column(db.String(100))
    specialization = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='teacher_profile')
    department = db.relationship('Department', back_populates='teachers')
    subjects = db.relationship('Subject', secondary='teacher_subjects', back_populates='teachers')
    classrooms = db.relationship('Classroom', back_populates='teacher', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Teacher {self.teacher_name}>"

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)
    graduation_date = db.Column(db.DateTime)
    student_id_number = db.Column(db.String(20), unique=True)
    current_semester = db.Column(db.Integer, default=1)
    gpa = db.Column(db.Float, default=0.0)  # Added field for GPA tracking

    # Relationships
    user = db.relationship('User', back_populates='student_profile')
    department = db.relationship('Department', back_populates='students')
    class_enrollments = db.relationship('Enrollment', back_populates='student', 
                                      cascade='all, delete-orphan')
    grades = db.relationship('Grade', back_populates='student', 
                           cascade='all, delete-orphan')
    submissions = db.relationship('Submission', back_populates='student', 
                                cascade='all, delete-orphan')
    attendances = db.relationship('Attendance', back_populates='student')
    quiz_attempts = db.relationship('QuizAttempt', back_populates='student', 
                                  cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_student_name', 'first_name', 'last_name'),
        db.Index('idx_student_department', 'department_id'),
        db.Index('idx_student_gpa', 'gpa'),
    )

    def full_name(self):
        """Return the student's full name."""
        return f"{self.first_name} {self.last_name}"

    def calculate_gpa(self):
        """Calculate GPA based on all grades."""
        if not self.grades:
            return 0.0
            
        total_points = sum(grade.final_score for grade in self.grades if grade.final_score)
        return round(total_points / len(self.grades), 2)

    def active_quizzes(self):
        """Return quizzes available to this student."""
        from sqlalchemy import and_, or_
        return Quiz.query.join(
            Subject
        ).join(
            Classroom,
            Subject.id == Classroom.subject_id
        ).join(
            Enrollment,
            Classroom.id == Enrollment.class_id
        ).filter(
            and_(
                Enrollment.student_id == self.id,
                or_(
                    Quiz.due_date.is_(None),
                    Quiz.due_date >= datetime.utcnow()
                )
            )
        ).all()

    def __repr__(self):
        return f"<Student {self.full_name()}>"
    

class Classroom(db.Model):
    __tablename__ = 'classrooms'
    
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    class_code = db.Column(db.String(20), unique=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    academic_year = db.Column(db.String(9), nullable=False)  # Required
    semester = db.Column(db.Integer, nullable=False)  # Required
    is_active = db.Column(db.Boolean, default=True)
    max_students = db.Column(db.Integer, default=30)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    schedule = db.Column(db.String(100))

    subject = db.relationship('Subject', back_populates='classrooms')
    teacher = db.relationship('Teacher', back_populates='classrooms')
    enrolled_students = db.relationship('Enrollment', back_populates='classroom', cascade='all, delete-orphan')
    sessions = db.relationship('OnlineSession', back_populates='classroom', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', back_populates='classroom', cascade='all, delete-orphan')
    resources = db.relationship('Resource', back_populates='classroom', cascade='all, delete-orphan')
    announcements = db.relationship('ClassAnnouncement', back_populates='classroom', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', back_populates='classroom')

    __table_args__ = (
        db.Index('idx_classroom_subject', 'subject_id'),
        db.Index('idx_classroom_teacher', 'teacher_id'),
        db.Index('idx_classroom_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Classroom {self.class_code}>"

class ClassAnnouncement(db.Model):
    __tablename__ = 'class_announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_pinned = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(255))

    classroom = db.relationship('Classroom', back_populates='announcements')
    author = db.relationship('User')

    def __repr__(self):
        return f"<Announcement {self.title[:20]}...>"

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)

    classroom = db.relationship('Classroom', back_populates='enrolled_students')
    student = db.relationship('Student', back_populates='class_enrollments')

    def __repr__(self):
        return f"<Enrollment {self.id}>"


class Resource(db.Model):
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300), nullable=False)
    file_name = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    resource_type = db.Column(db.String(20), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    is_approved = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    thumbnail_path = db.Column(db.String(300))
    
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
        
    subject = db.relationship('Subject', back_populates='resources')
    classroom = db.relationship('Classroom', back_populates='resources')
    teacher = db.relationship('User', back_populates='uploaded_resources')
    tags = db.relationship('Tag', secondary='resource_tags', back_populates='resources')
    comments = db.relationship('ResourceComment', back_populates='resource')
    
    __table_args__ = (
        db.Index('idx_resource_type', 'resource_type'),
        db.Index('idx_upload_date', 'upload_date'),
    )

    def __repr__(self):
        return f"<Resource {self.title[:20]}...>"

resource_tags = db.Table('resource_tags',
    db.Column('resource_id', db.Integer, db.ForeignKey('resources.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    resources = db.relationship('Resource', secondary='resource_tags', back_populates='tags')

    def __repr__(self):
        return f"<Tag {self.name}>"

class ResourceComment(db.Model):
    __tablename__ = 'resource_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'), nullable=False)
    
    user = db.relationship('User', back_populates='comments')
    resource = db.relationship('Resource', back_populates='comments')

    def __repr__(self):
        return f"<Comment {self.id}>"

class Assignment(db.Model):
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    max_score = db.Column(db.Integer, default=100)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subject = db.relationship('Subject', back_populates='assignments')
    classroom = db.relationship('Classroom', back_populates='assignments')
    author = db.relationship('User', back_populates='created_assignments')
    submissions = db.relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Assignment {self.title}>"

class Submission(db.Model):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(300))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    assignment = db.relationship('Assignment', back_populates='submissions')
    student = db.relationship('Student', back_populates='submissions')

    def __repr__(self):
        return f"<Submission {self.id}>"

# Update the Quiz model to include attempts relationship
class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)  # Changed to classroom_id
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    time_limit = db.Column(db.Integer)  # in minutes
    total_points = db.Column(db.Integer, default=0)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    subject = db.relationship('Subject', back_populates='quizzes')
    classroom = db.relationship('Classroom', back_populates='quizzes')  # Kept as classroom
    questions = db.relationship('Question', back_populates='quiz', cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', back_populates='quiz', cascade='all, delete-orphan')
    teacher = db.relationship('User')

    def update_total_points(self):
        self.total_points = sum(question.points for question in self.questions)
        return self.total_points

    def __repr__(self):
        return f"<Quiz {self.title}>"
    
class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    points = db.Column(db.Integer, default=1)
    time_limit = db.Column(db.Integer)  # Add this field
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)

    # Relationships
    quiz = db.relationship('Quiz', back_populates='questions')
    answers = db.relationship('QuizAnswer', back_populates='question', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Question {self.id}>"
    
class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    score = db.Column(db.Float)
    time_spent = db.Column(db.Integer)  # in seconds
    
    # Relationships
    quiz = db.relationship('Quiz', back_populates='attempts')
    student = db.relationship('Student', back_populates='quiz_attempts')
    answers = db.relationship('QuizAnswer', back_populates='attempt', cascade='all, delete-orphan')

    def calculate_score(self):
        """Calculate total score based on correct answers"""
        self.score = sum(
            answer.question.points 
            for answer in self.answers 
            if answer.is_correct
        )
        return self.score

    def __repr__(self):
        return f"<QuizAttempt {self.id}>"


class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('Question', back_populates='answers')

    def __repr__(self):
        return f"<QuizAnswer {self.id}>"


class OnlineSession(db.Model):
    __tablename__ = 'online_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(100), unique=True, nullable=False)
    session_name = db.Column(db.String(200), nullable=False)
    session_link = db.Column(db.String(500), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='scheduled')

    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True))
    original_timezone = db.Column(db.String(50), nullable=False)       # e.g. 'America/New_York'
    
    # Additional fields
    duration_minutes = db.Column(db.Integer)  # Calculated field
    recording_url = db.Column(db.String(500))
    timezone = db.Column(db.String(50))  # Store creator's timezone

    # Relationships
    classroom = db.relationship('Classroom', back_populates='sessions')
    creator = db.relationship('User', back_populates='created_sessions')
    attendances = db.relationship('Attendance', back_populates='session')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.start_time and self.end_time:
            self.duration_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        if hasattr(self.creator, 'timezone'):
            self.timezone = self.creator.timezone

    def __repr__(self):
        return f"<Session {self.room_id}>"
    
# Attendance model to track student attendance in online sessions    
class Attendance(db.Model):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('online_sessions.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # e.g., 'present', 'absent', 'late'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', back_populates='attendances')
    session = db.relationship('OnlineSession', back_populates='attendances')

    def __repr__(self):
        return f"<Attendance {self.student.full_name()} for {self.session.session_name} - {self.status}>"


class Grade(db.Model):
    __tablename__ = 'grades'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    quiz_score = db.Column(db.Float)
    assignment_score = db.Column(db.Float)
    participation_score = db.Column(db.Float)
    final_score = db.Column(db.Float)
    grade_letter = db.Column(db.String(2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', back_populates='grades')
    subject = db.relationship('Subject', back_populates='grades')

    def __repr__(self):
        return f"<Grade {self.id}>"

class Activity(db.Model):
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    icon = db.Column(db.String(30))

    def __repr__(self):
        return f"<Activity {self.id}>"

@event.listens_for(Grade, 'before_insert')
@event.listens_for(Grade, 'before_update')
def calculate_final_score(mapper, connection, target):
    if target.quiz_score is not None and target.assignment_score is not None:
        target.final_score = (target.quiz_score * 0.4) + (target.assignment_score * 0.5) + (target.participation_score or 0 * 0.1)
        
        if target.final_score >= 90:
            target.grade_letter = 'A'
        elif target.final_score >= 80:
            target.grade_letter = 'B'
        elif target.final_score >= 70:
            target.grade_letter = 'C'
        elif target.final_score >= 60:
            target.grade_letter = 'D'
        else:
            target.grade_letter = 'F'