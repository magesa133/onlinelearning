from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

# Initialize the db object here
db = SQLAlchemy()

# User Roles Enum for clarity
class UserRole:
    STUDENT = 'student'
    TEACHER = 'teacher'

# User Model (student/teacher)
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    face_image = db.Column(db.String(200), nullable=True)  # Path to the saved face image

    # Relationship with Teacher model (one-to-one)
    teacher = db.relationship('Teacher', backref='user', uselist=False)

    def __repr__(self):
        return f"<User {self.username}>"


class Class(db.Model):
    __tablename__ = 'class'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)

    # Define relationship with Teacher
    teacher = db.relationship('Teacher', back_populates='classes')

    def __repr__(self):
        return f"<Class {self.name}>"

# Many-to-Many Relationship for Students and Classes
class ClassStudent(db.Model):
    __tablename__ = 'class_student'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f"<ClassStudent {self.class_id} - {self.student_id}>"

# Assignment Model
class Assignment(db.Model):
    __tablename__ = 'assignment'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)

    # Use a unique backref name
    class_ = db.relationship('Class', backref='class_assignments')

    def __repr__(self):
        return f"<Assignment {self.title}>"

# Quiz Model
class Quiz(db.Model):
    __tablename__ = 'quiz'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete')
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('online_session.id'), nullable=True)

    def __repr__(self):
        return f"<Quiz {self.title}>"

# Question Model
class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)  # Example: {'A': 'Option 1', 'B': 'Option 2'}
    correct_option = db.Column(db.String(1), nullable=False)  # Example: 'A', 'B', 'C', 'D'
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)

    def __repr__(self):
        return f"<Question {self.text[:30]}...>"

# Online Session Model
class OnlineSession(db.Model):
    __tablename__ = 'online_session'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    session_name = db.Column(db.String(200), nullable=False)
    session_link = db.Column(db.String(500), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<OnlineSession {self.session_name} (Room: {self.room_id})>"

# Teacher Model
class Teacher(db.Model):
    __tablename__ = 'teacher'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Link to User
    teacher_name = db.Column(db.String(100))
    subject = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)

    # Relationship with Department
    department = db.relationship('Department', backref='teachers')

    # Relationship with Class (one-to-many)
    classes = db.relationship('Class', back_populates='teacher')

    def __repr__(self):
        return f"<Teacher {self.teacher_name}>"

# Department Model
class Department(db.Model):
    __tablename__ = 'department'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Department {self.name}>"
