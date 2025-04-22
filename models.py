from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask import current_app
from enum import Enum, unique
from sqlalchemy import func, event, Index, and_, or_
from sqlalchemy.orm import validates
from datetime import datetime, timezone, timedelta
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import NotFound, Forbidden
import pytz

db = SQLAlchemy()

# Association Tables
teacher_subjects = db.Table('teacher_subjects',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subjects.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

resource_tags = db.Table('resource_tags',
    db.Column('resource_id', db.Integer, db.ForeignKey('resources.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class UserRole:
    STUDENT = 'student'
    TEACHER = 'teacher'
    ADMIN = 'admin'

class ActivityTypes:
    QUIZ_PUBLISHED = 'quiz_published'
    QUIZ_UNPUBLISHED = 'quiz_unpublished'
    ANNOUNCEMENT = 'announcement'
    MATERIAL_ADDED = 'material_added'
    CLASS_CANCELLED = 'class_cancelled'
    GRADE_POSTED = 'grade_posted'

class BaseMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        db.session.delete(self)
        db.session.commit()

# Moved Announcement class before Teacher since Teacher references it
class Announcement(db.Model, BaseMixin):
    __tablename__ = 'announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(255))

    author = db.relationship('Teacher', back_populates='announcements')

    def __repr__(self):
        return f'<Announcement {self.title[:20]}...>'

# Updated User model (remove conflicting relationship)
class User(UserMixin, db.Model, BaseMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    face_image = db.Column(db.String(255))
    last_login = db.Column(db.DateTime)
    timezone = db.Column(db.String(50), default='UTC')
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    teacher_profile = db.relationship('Teacher', 
                                    back_populates='user', 
                                    uselist=False, 
                                    cascade='all, delete-orphan',
                                    foreign_keys='Teacher.user_id')
    
    student_profile = db.relationship('Student', 
                                    back_populates='user', 
                                    uselist=False, 
                                    cascade='all, delete-orphan',
                                    primaryjoin='User.id==Student.user_id')
    sent_messages = db.relationship('Message', 
                                  foreign_keys='Message.sender_id', 
                                  back_populates='sender')
    received_messages = db.relationship('Message', 
                                      foreign_keys='Message.recipient_id', 
                                      back_populates='recipient')
    comments = db.relationship('ResourceComment', 
                             back_populates='author')
    uploaded_resources = db.relationship('Resource', 
                                       back_populates='teacher')
    created_assignments = db.relationship('Assignment', 
                                        back_populates='author', 
                                        cascade='all, delete-orphan')
    created_sessions = db.relationship('OnlineSession', 
                                     back_populates='creator', 
                                     cascade='all, delete-orphan')
    quiz_attempts = db.relationship('QuizAttempt', 
                                  back_populates='user', 
                                  cascade='all, delete-orphan')

    @validates('email')
    def validate_email(self, key, email):
        """Validate email format"""
        if '@' not in email:
            raise ValueError("Invalid email address")
        return email

    def get_full_name(self):
        """Get user's full name based on their role"""
        if self.role == 'teacher' and self.teacher_profile:
            return self.teacher_profile.full_name()
        elif self.role == 'student' and self.student_profile:
            return self.student_profile.full_name()
        return self.username

    @property
    def is_student(self):
        """Check if user is a student"""
        return self.role == 'student' and self.student_profile is not None
    
    def get_submissions(self):
        """Get student submissions if user is a student"""
        if self.is_student:
            return self.student_profile.submissions
        return []
    
    def set_password(self, password):
        """Create hashed password."""
        self.password = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=16
        )

    def check_password(self, password):
        """Check hashed password."""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class Department(db.Model, BaseMixin):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))

    students = db.relationship('Student', back_populates='department')
    teachers = db.relationship('Teacher', back_populates='department')
    subjects = db.relationship('Subject', back_populates='department')

    def __repr__(self):
        return f'<Department {self.name}>'
    
class Subject(db.Model, BaseMixin):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))

    # Relationships
    department = db.relationship('Department', back_populates='subjects')
    
    teachers = db.relationship('Teacher', 
                             secondary=teacher_subjects, 
                             back_populates='subjects')
    
    classrooms = db.relationship('Classroom', 
                               back_populates='subject')
    
    resources = db.relationship('Resource', 
                              back_populates='subject', 
                              cascade='all, delete-orphan')
    
    assignments = db.relationship('Assignment', 
                                back_populates='subject', 
                                cascade='all, delete-orphan')
    
    # Changed to back_populates to match Quiz model
    quizzes = db.relationship("Quiz", back_populates="subject")

    
    grades = db.relationship('Grade', 
                           back_populates='subject', 
                           cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Subject {self.name}>'

    def get_teacher_count(self):
        """Return count of teachers associated with this subject"""
        return len(self.teachers)

    def get_classroom_count(self):
        """Return count of classrooms using this subject"""
        return len(self.classrooms)

    def get_active_teachers(self):
        """Return list of all active teachers for this subject"""
        classroom_teachers = {c.teacher for c in self.classrooms if c.teacher}
        direct_teachers = set(self.teachers)
        return list(classroom_teachers | direct_teachers)
    

# Updated Teacher model with quizzes relationship
class Teacher(db.Model, BaseMixin):
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    teacher_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    specialization = db.Column(db.String(100))
    office_location = db.Column(db.String(100))

    # Relationships
    user = db.relationship('User', back_populates='teacher_profile')
    department = db.relationship('Department', back_populates='teachers')
    subjects = db.relationship('Subject', secondary=teacher_subjects, back_populates='teachers')
    classrooms = db.relationship('Classroom', back_populates='teacher', cascade='all, delete-orphan')
    announcements = db.relationship('Announcement', back_populates='author')
    quizzes = db.relationship('Quiz', back_populates='teacher')  # Added this relationship

    def full_name(self):
        return f"{self.user.username}"

    def get_all_subjects(self):
        """Get all subjects assigned through both direct assignment and classrooms"""
        direct_subjects = self.subjects
        classroom_subjects = [c.subject for c in self.classrooms]
        return list({s.id: s for s in direct_subjects + classroom_subjects}.values())

    def get_subject_stats(self, subject_id):
        """Get statistics for a specific subject"""
        subject = Subject.query.get(subject_id)
        if not subject:
            return None
            
        return {
            'class_count': len([c for c in self.classrooms if c.subject_id == subject_id]),
            'assignment_count': len(subject.assignments),
            'quiz_count': len(subject.quizzes),
            'resource_count': len(subject.resources),
            'student_count': sum(len(c.enrollments) for c in self.classrooms if c.subject_id == subject_id)
        }

    def can_teach_subject(self, subject_id):
        """Check if teacher is assigned to teach this subject"""
        return any(s.id == subject_id for s in self.get_all_subjects())

    def __repr__(self):
        return f'<Teacher {self.user.username}>'

class Student(db.Model, BaseMixin):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    student_id = db.Column(db.String(20), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    date_of_birth = db.Column(db.Date)
    enrollment_date = db.Column(db.Date, default=datetime.utcnow().date)
    graduation_date = db.Column(db.Date)
    current_semester = db.Column(db.Integer, default=1)
    gpa = db.Column(db.Float, default=0.0)
    address = db.Column(db.String(200))
    phone_number = db.Column(db.String(20))
    emergency_contact = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', back_populates='student_profile')
    department = db.relationship('Department', back_populates='students')
    enrollments = db.relationship('Enrollment', back_populates='student', cascade='all, delete-orphan')
    submissions = db.relationship('Submission', back_populates='student', cascade='all, delete-orphan')
    quiz_attempts = db.relationship('QuizAttempt', back_populates='student', cascade='all, delete-orphan')
    grades = db.relationship('Grade', back_populates='student', cascade='all, delete-orphan')
    attendances = db.relationship('Attendance', back_populates='student')

    def __repr__(self):
        return f'<Student {self.full_name()} ({self.student_id})>'

    def full_name(self):
        """Return the student's full name"""
        return f"{self.first_name} {self.last_name}"

    def calculate_gpa(self):
        """Calculate the student's current GPA"""
        if not self.grades:
            self.gpa = 0.0
            return self.gpa
        
        total_credits = sum(
            grade.classroom.course.credits 
            for grade in self.grades 
            if (grade.final_score is not None and 
                grade.classroom and 
                grade.classroom.course)
        )
        
        if total_credits == 0:
            self.gpa = 0.0
            return self.gpa
            
        weighted_sum = sum(
            grade.final_score * grade.classroom.course.credits 
            for grade in self.grades 
            if (grade.final_score is not None and 
                grade.classroom and 
                grade.classroom.course)
        )
        
        self.gpa = round(weighted_sum / total_credits, 2)
        return self.gpa

    def active_courses(self):
        """Get list of currently active courses the student is enrolled in"""
        return [
            enrollment.classroom 
            for enrollment in self.enrollments 
            if (enrollment.classroom and 
                enrollment.classroom.is_active)
        ]

    @property
    def grade_counts(self):
        """Returns a dictionary of grade counts by letter grade"""
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        
        for grade in self.grades:
            if grade.final_score is None:
                continue
                
            if grade.final_score >= 90:
                counts['A'] += 1
            elif grade.final_score >= 80:
                counts['B'] += 1
            elif grade.final_score >= 70:
                counts['C'] += 1
            elif grade.final_score >= 60:
                counts['D'] += 1
            else:
                counts['F'] += 1
                
        return counts
    
    @property
    def grade_a_count(self):
        return self.grade_counts['A']
    
    @property
    def grade_b_count(self):
        return self.grade_counts['B']
    
    @property
    def grade_c_count(self):
        return self.grade_counts['C']
    
    @property
    def grade_d_count(self):
        return self.grade_counts['D']
    
    @property
    def grade_f_count(self):
        return self.grade_counts['F']
    
    @property
    def assignment_completion_rate(self):
        """Percentage of completed assignments"""
        total_assignments = sum(
            len(enrollment.classroom.assignments)
            for enrollment in self.enrollments
            if enrollment.classroom
        )
        
        if total_assignments == 0:
            return 0.0
            
        completed = sum(1 for submission in self.submissions if submission.is_completed)
        return round((completed / total_assignments) * 100, 1)
    

class Message(db.Model, BaseMixin):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    is_urgent = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    is_announcement = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages')
    classroom = db.relationship('Classroom', back_populates='messages')
    parent = db.relationship('Message', remote_side=[id], back_populates='replies')
    replies = db.relationship('Message', back_populates='parent')

    __table_args__ = (
        Index('idx_message_sender', 'sender_id'),
        Index('idx_message_recipient', 'recipient_id'),
        Index('idx_message_classroom', 'classroom_id'),
    )

    def mark_as_read(self):
        self.is_read = True
        self.save()

    def reply(self, content, sender):
        reply = Message(
            title=f"Re: {self.title}",
            content=content,
            sender_id=sender.id,
            recipient_id=self.sender_id,
            classroom_id=self.classroom_id,
            parent_id=self.id,
            is_urgent=self.is_urgent
        )
        return reply.save()

    def get_thread(self):
        """Get the entire conversation thread"""
        thread = []
        current = self
        while current.parent:
            current = current.parent
        thread.append(current)
        thread.extend(current.replies.order_by(Message.created_at.asc()).all())
        return thread

    def __repr__(self):
        return f'<Message {self.title[:20]}...>'

class Classroom(db.Model, BaseMixin):
    __tablename__ = 'classrooms'
    
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    academic_year = db.Column(db.String(9), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    max_students = db.Column(db.Integer, default=30)
    schedule = db.Column(db.String(100))
    section = db.Column(db.String(10))
    room_number = db.Column(db.String(20))
    description = db.Column(db.Text)

    # Relationships
    subject = db.relationship('Subject', back_populates='classrooms')
    
    teacher = db.relationship('Teacher', back_populates='classrooms')
    
    enrollments = db.relationship('Enrollment',
                                back_populates='classroom',
                                cascade='all, delete-orphan')
    
    messages = db.relationship('Message', back_populates='classroom')
    
    assignments = db.relationship('Assignment',
                                back_populates='classroom',
                                cascade='all, delete-orphan')
    
    resources = db.relationship('Resource',
                              back_populates='classroom',
                              cascade='all, delete-orphan')
    
    announcements = db.relationship('ClassAnnouncement',
                                  back_populates='classroom',
                                  cascade='all, delete-orphan')
    
    quizzes = db.relationship("Quiz", back_populates="classroom")
    
    sessions = db.relationship('OnlineSession',
                             back_populates='classroom',
                             cascade='all, delete-orphan')
    activities = db.relationship('ClassroomActivity', 
                               back_populates='classroom',
                               cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_classroom_subject', 'subject_id'),
        Index('idx_classroom_teacher', 'teacher_id'),
        Index('idx_classroom_active', 'is_active'),
    )

    def generate_code(self):
        """Generate a unique class code"""
        subject_code = (self.subject.code if hasattr(self.subject, 'code') 
                      else (self.subject.name[:3].upper() if self.subject else 'CLS'))
        year_part = self.academic_year.replace('-', '')[:4]
        return f"{subject_code}-{year_part}-{self.semester}-{self.id:03d}"

    def current_student_count(self):
        """Return count of active enrolled students"""
        return len([e for e in self.enrollments if not e.is_dropped])

    def is_full(self):
        """Check if classroom has reached maximum capacity"""
        return self.current_student_count() >= self.max_students

    def __repr__(self):
        return f'<Classroom {self.class_name} ({self.academic_year} S{self.semester})>'
    
class ClassroomActivity(db.Model):
    """Tracks all significant classroom events and activities"""
    __tablename__ = 'classroom_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'quiz_published', 'announcement'
    content = db.Column(db.Text, nullable=False)              # Human-readable description
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Teacher who initiated
    activity_data = db.Column(db.JSON)                        # Changed from 'metadata' to 'activity_data'

    # Relationships
    classroom = db.relationship('Classroom', back_populates='activities')
    author = db.relationship('User')

    def __init__(self, classroom_id, activity_type, content, created_by=None, activity_data=None):
        self.classroom_id = classroom_id
        self.activity_type = activity_type
        self.content = content
        self.created_by = created_by
        self.activity_data = activity_data or {}

class ClassAnnouncement(db.Model, BaseMixin):
    __tablename__ = 'class_announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    attachment_path = db.Column(db.String(255))

    classroom = db.relationship('Classroom', back_populates='announcements')
    author = db.relationship('User')

    def __repr__(self):
        return f'<ClassAnnouncement {self.title[:20]}...>'

class Enrollment(db.Model, BaseMixin):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    is_dropped = db.Column(db.Boolean, default=False)  # Add this column
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)  # Add this line

    classroom = db.relationship('Classroom', back_populates='enrollments')
    student = db.relationship('Student', back_populates='enrollments')

    def __repr__(self):
        return f'<Enrollment {self.id}>'

class Resource(db.Model, BaseMixin):
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
        Index('idx_resource_type', 'resource_type'),
    )

    def __repr__(self):
        return f'<Resource {self.title[:20]}...>'

class Tag(db.Model, BaseMixin):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    resources = db.relationship('Resource', secondary='resource_tags', back_populates='tags')

    def __repr__(self):
        return f'<Tag {self.name}>'

class ResourceComment(db.Model, BaseMixin):
    __tablename__ = 'resource_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'), nullable=False)
    
    author = db.relationship('User', back_populates='comments')
    resource = db.relationship('Resource', back_populates='comments')

    def __repr__(self):
        return f'<ResourceComment {self.id}>'

class Assignment(db.Model, BaseMixin):
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text)
    question_file_path = db.Column(db.String(255))
    due_date = db.Column(db.DateTime(timezone=True), nullable=False)  # Explicit timezone
    max_score = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_draft = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)

    subject = db.relationship('Subject', back_populates='assignments')
    classroom = db.relationship('Classroom', back_populates='assignments')
    author = db.relationship('User', back_populates='created_assignments')
    submissions = db.relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Assignment {self.title}>'

    def time_remaining(self):
        remaining = self.due_date - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def submission_count(self):
        return len(self.submissions)

    def status(self):
        if self.is_draft:
            return "Draft"
        if datetime.utcnow() > self.due_date:
            return "Closed"
        return "Active"

    def average_score(self):
        avg = db.session.query(db.func.avg(Submission.score)) \
              .filter(Submission.assignment_id == self.id) \
              .filter(Submission.score.isnot(None)) \
              .scalar()
        return round(avg, 2) if avg else None

class Submission(db.Model, BaseMixin):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(300))
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    assignment = db.relationship('Assignment', back_populates='submissions')
    student = db.relationship('Student', back_populates='submissions')

    def __repr__(self):
        return f'<Submission {self.id}>'
    
@unique
class QuizStatus(Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'
    DELETED = 'deleted'


# Updated Quiz model with proper relationships
class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    due_date = db.Column(db.DateTime(timezone=True), nullable=False)
    time_limit = db.Column(db.Integer)  # in minutes
    max_attempts = db.Column(db.Integer, default=1)  # max number of attempts allowed
    total_points = db.Column(db.Integer, default=0)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))  # Changed to reference teachers.id
    
    # Status tracking
    status = db.Column(db.String(20), default=QuizStatus.DRAFT.value, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    archived_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships
    subject = db.relationship('Subject', back_populates='quizzes')
    classroom = db.relationship('Classroom', back_populates='quizzes')
    questions = db.relationship('Question', 
                              back_populates='quiz', 
                              cascade='all, delete-orphan',
                              order_by='Question.position')
    attempts = db.relationship('QuizAttempt', 
                             back_populates='quiz', 
                             cascade='all, delete-orphan')
    teacher = db.relationship('Teacher', back_populates='quizzes')  # Updated to reference Teacher

    # Status Management Methods
    def publish(self):
        """Publish the quiz to make it available to students"""
        if self.is_deleted:
            raise ValueError("Cannot publish a deleted quiz")
        if not self.questions:
            raise ValueError("Cannot publish quiz with no questions")
        
        self.status = QuizStatus.PUBLISHED.value
        self.published_at = datetime.utcnow()
        self.archived_at = None
        self.update_total_points()
        db.session.commit()
        return self

    def unpublish(self):
        """Revert quiz to draft status"""
        if self.is_deleted:
            raise ValueError("Cannot unpublish a deleted quiz")
            
        self.status = QuizStatus.DRAFT.value
        self.published_at = None
        db.session.commit()
        return self

    def archive(self):
        """Archive an inactive quiz"""
        if self.is_deleted:
            raise ValueError("Cannot archive a deleted quiz")
            
        self.status = QuizStatus.ARCHIVED.value
        self.archived_at = datetime.utcnow()
        db.session.commit()
        return self

    def soft_delete(self):
        """Mark quiz as deleted without DB removal"""
        self.status = QuizStatus.DELETED.value
        self.deleted_at = datetime.utcnow()
        db.session.commit()
        return self

    def restore(self):
        """Restore a deleted quiz to draft status"""
        if not self.is_deleted:
            raise ValueError("Can only restore deleted quizzes")
            
        self.status = QuizStatus.DRAFT.value
        self.deleted_at = None
        db.session.commit()
        return self

    # Property Accessors
    @property
    def is_published(self):
        return self.status == QuizStatus.PUBLISHED.value
        
    @property
    def is_draft(self):
        return self.status == QuizStatus.DRAFT.value
        
    @property
    def is_archived(self):
        return self.status == QuizStatus.ARCHIVED.value
        
    @property
    def is_deleted(self):
        return self.status == QuizStatus.DELETED.value

    # Utility Methods
    def update_total_points(self):
        """Recalculate total points from questions"""
        self.total_points = sum(question.points for question in self.questions)
        db.session.commit()
        return self.total_points

    def validate_for_publishing(self):
        """Check if quiz can be published"""
        errors = []
        if not self.questions:
            errors.append("Quiz must have at least one question")
        if not self.due_date or self.due_date < datetime.utcnow():
            errors.append("Due date must be in the future")
        if not self.time_limit or self.time_limit <= 0:
            errors.append("Time limit must be positive")
        return errors

    @classmethod
    def get_active(cls):
        """Get all non-deleted quizzes"""
        return cls.query.filter(cls.status != QuizStatus.DELETED.value)

    @classmethod
    def bulk_status_update(cls, quiz_ids, new_status):
        """Update status for multiple quizzes"""
        if new_status not in [s.value for s in QuizStatus]:
            raise ValueError("Invalid status")
            
        updates = {'status': new_status}
        
        if new_status == QuizStatus.PUBLISHED.value:
            updates['published_at'] = datetime.utcnow()
        elif new_status == QuizStatus.ARCHIVED.value:
            updates['archived_at'] = datetime.utcnow()
        elif new_status == QuizStatus.DELETED.value:
            updates['deleted_at'] = datetime.utcnow()
            
        return cls.query.filter(
            cls.id.in_(quiz_ids),
            cls.status != QuizStatus.DELETED.value
        ).update(updates, synchronize_session=False)

    def __repr__(self):
        return f'<Quiz {self.id}: {self.title} ({self.status})>'


class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='multiple_choice')
    
    # For multiple choice questions - store options as JSON
    options = db.Column(db.JSON)  # This is correct for your use case
    
    # For other fields
    correct_option = db.Column(db.Integer)
    correct_answer = db.Column(db.String(50))
    points = db.Column(db.Integer, default=1)
    time_limit = db.Column(db.Integer, default=60)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    position = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    quiz = db.relationship('Quiz', back_populates='questions')
    answers = db.relationship('QuizAnswer', 
                            back_populates='question', 
                            cascade='all, delete-orphan')

    # Methods
    def update_position(self, new_position):
        """Update question position and reorder others"""
        old_position = self.position
        
        if new_position > old_position:
            Question.query.filter(
                Question.quiz_id == self.quiz_id,
                Question.position > old_position,
                Question.position <= new_position
            ).update({Question.position: Question.position - 1})
        else:
            Question.query.filter(
                Question.quiz_id == self.quiz_id,
                Question.position >= new_position,
                Question.position < old_position
            ).update({Question.position: Question.position + 1})
            
        self.position = new_position
        db.session.commit()
        return self

    def get_options(self):
        """Return question options in a standardized format"""
        if self.question_type == 'multiple_choice':
            # Return options as a dictionary if they're stored that way
            if isinstance(self.options, dict):
                return self.options
            # Or convert from list to dict if needed
            elif isinstance(self.options, list):
                return {chr(65+i): option for i, option in enumerate(self.options)}
            # Default fallback
            return {
                'A': getattr(self, 'option_a', 'Option A'),
                'B': getattr(self, 'option_b', 'Option B'),
                'C': getattr(self, 'option_c', 'Option C'),
                'D': getattr(self, 'option_d', 'Option D')
            }
        elif self.question_type == 'true_false':
            return {0: 'False', 1: 'True'}
        elif self.question_type == 'short_answer':
            return {}  # No options for short answer questions
        else:
            return {}

    def validate_answer(self, answer):
        """Validate student's answer against correct answer"""
        if self.question_type == 'multiple_choice':
            if isinstance(self.options, dict):
                return str(answer) in self.options
            elif isinstance(self.options, list):
                try:
                    index = int(answer)
                    return 0 <= index < len(self.options)
                except ValueError:
                    return False
        return str(answer).strip().lower() == str(self.correct_answer).strip().lower()

    def __repr__(self):
        return f'<Question {self.id}: {self.text[:50]}...>'
    

class BaseMixin:
    def save(self):
        db.session.add(self)
        db.session.commit()
    
    def delete(self):
        db.session.delete(self)
        db.session.commit()

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    
    # Timestamps
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))
    
    # Performance metrics
    score = db.Column(db.Float)
    time_spent = db.Column(db.Integer)  # in seconds
    
    # Relationships
    quiz = db.relationship('Quiz', back_populates='attempts')
    student = db.relationship('Student', back_populates='quiz_attempts')
    user = db.relationship('User', back_populates='quiz_attempts')
    answers = db.relationship('QuizAnswer', 
                            back_populates='attempt', 
                            cascade='all, delete-orphan',
                            order_by='QuizAnswer.id')

    def __init__(self, **kwargs):
        # Automatically set student_id from user's student_profile if not provided
        if 'student_id' not in kwargs and 'user' in kwargs:
            user = kwargs['user']
            if user and user.student_profile:
                kwargs['student_id'] = user.student_profile.id
                kwargs['user_id'] = user.id
        super().__init__(**kwargs)

    @validates('student_id')
    def validate_student(self, key, student_id):
        """Validate the student exists and is active"""
        student = Student.query.get(student_id)
        
        if not student:
            raise ValueError("Student account not found")
            
        if hasattr(student, 'is_active') and not student.is_active:
            raise ValueError("Student account is not active")
            
        return student_id

    def calculate_score(self):
        """Calculate score based on correct answers"""
        if not self.answers:
            self.score = 0.0
            return self.score
            
        correct = sum(1 for answer in self.answers if answer.is_correct)
        total = len(self.quiz.questions) if self.quiz else len(self.answers)
        
        self.score = round((correct / total) * 100, 2) if total > 0 else 0.0
        return self.score

    def complete_attempt(self):
        """Mark attempt as completed and calculate final score"""
        if not self.completed_at:
            self.completed_at = datetime.now(timezone.utc)
            if self.started_at:
                started = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
                self.time_spent = (self.completed_at - started).total_seconds()
            self.calculate_score()

    @property
    def status(self):
        """Get attempt status"""
        if self.completed_at:
            return 'completed'
        if self.started_at:
            return 'in_progress'
        return 'not_started'

    def __repr__(self):
        return f'<QuizAttempt {self.id} for quiz {self.quiz_id} by student {self.student_id}>'
    

# ======================
# QUIZ MODELS
# ======================

class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    selected_answer = db.Column(db.String(500))
    answer_text = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    points_earned = db.Column(db.Float)
    time_taken = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('Question', back_populates='answers')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points_earned = 0
        self.time_taken = 0

    @validates('selected_answer')
    def validate_selected_answer(self, key, selected_answer):
        if self.question and self.question.question_type == 'multiple_choice':
            if selected_answer not in self.question.options:
                raise ValueError(f"Invalid answer for question {self.question_id}")
        return selected_answer

    def check_correctness(self):
        if not self.question:
            return False
            
        if self.question.question_type == 'multiple_choice':
            self.is_correct = str(self.selected_answer) == str(self.question.correct_option)
        else:
            self.is_correct = str(self.answer_text).strip().lower() == str(self.question.correct_answer).strip().lower()
        
        return self.is_correct

    def calculate_points(self):
        if not self.question:
            return 0
            
        self.check_correctness()
        self.points_earned = self.question.points if self.is_correct else 0
        return self.points_earned

    def update_from_request(self, data):
        if 'selected_answer' in data:
            self.selected_answer = data['selected_answer']
        if 'answer_text' in data:
            self.answer_text = data['answer_text']
        if 'time_taken' in data:
            self.time_taken = data['time_taken']
        
        self.calculate_points()
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'selected_answer': self.selected_answer,
            'answer_text': self.answer_text,
            'is_correct': self.is_correct,
            'points_earned': self.points_earned,
            'time_taken': self.time_taken,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class OnlineSession(db.Model, BaseMixin):
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
    original_timezone = db.Column(db.String(50), nullable=False)
    duration_minutes = db.Column(db.Integer)
    recording_url = db.Column(db.String(500))
    timezone = db.Column(db.String(50))
    
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
        return f'<OnlineSession {self.room_id}>'
 
class Attendance(db.Model, BaseMixin):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('online_sessions.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    student = db.relationship('Student', back_populates='attendances')
    session = db.relationship('OnlineSession', back_populates='attendances')

    def __repr__(self):
        return f'<Attendance {self.student.full_name()} for {self.session.session_name} - {self.status}>'
    
class Grade(db.Model, BaseMixin):
    __tablename__ = 'grades'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    quiz_score = db.Column(db.Float)
    assignment_score = db.Column(db.Float)
    participation_score = db.Column(db.Float)
    final_score = db.Column(db.Float)
    grade_letter = db.Column(db.String(2))

    student = db.relationship('Student', back_populates='grades')
    subject = db.relationship('Subject', back_populates='grades')

    def __repr__(self):
        return f'<Grade {self.id}>'

class Activity(db.Model, BaseMixin):
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    icon = db.Column(db.String(30))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # Ensure timestamp field exists


    def __repr__(self):
        return f'<Activity {self.id}>'

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