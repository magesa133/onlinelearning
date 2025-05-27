from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask import current_app, url_for
from flask_login import current_user
from enum import Enum, unique
from sqlalchemy import event, Index
from sqlalchemy.orm import validates
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from pytz import utc

# Define a default application timezone
APP_TIMEZONE = 'UTC'


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
    profile_image_url = db.Column(db.String(255), nullable=True)  # Add this line
    timezone = db.Column(db.String(50), default='Africa/Dar_es_Salaam')
    is_active = db.Column(db.Boolean, default=True)

    # Relationships

    # Add these relationships
    notifications = db.relationship(
        'Notification', 
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    notification_settings = db.relationship(
        'NotificationSettings',
        back_populates='user',
        uselist=False,  # One-to-one relationship
        cascade='all, delete-orphan'
    )

    teacher_profile = db.relationship(
        'Teacher', 
        back_populates='user', 
        uselist=False, 
        cascade='all, delete-orphan'
    )
    student_profile = db.relationship(
        'Student', 
        back_populates='user', 
        uselist=False, 
        cascade='all, delete-orphan'
    )
    notifications = db.relationship(
        'Notification',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        back_populates='sender',
        lazy='dynamic'
    )
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.recipient_id',
        back_populates='recipient',
        lazy='dynamic'
    )
    comments = db.relationship(
        'ResourceComment',
        back_populates='author',
        cascade='all, delete-orphan'
    )
    uploaded_resources = db.relationship(
        'Resource',
        back_populates='teacher'
    )
    created_assignments = db.relationship(
        'Assignment',
        back_populates='author',
        cascade='all, delete-orphan'
    )
    created_sessions = db.relationship(
        'OnlineSession',
        back_populates='creator',
        cascade='all, delete-orphan'
    )
    quiz_attempts = db.relationship(
        'QuizAttempt',
        back_populates='user',
        cascade='all, delete-orphan'
    )

    # In your User model
    def validate_timezone(timezone_str):
        try:
            import pytz
            return timezone_str in pytz.all_timezones
        except:
            try:
                from zoneinfo import available_timezones
                return timezone_str in available_timezones()
            except:
                return False

    # Add to your User model
    @property
    def enrollments(self):
        if self.role == 'student' and self.student_profile:
            return self.student_profile.enrollments
        return []

    @validates('email')
    def validate_email(self, key, email):
        if '@' not in email:
            raise ValueError("Invalid email address")
        return email

    def get_full_name(self):
        if self.role == 'teacher' and self.teacher_profile:
            return self.teacher_profile.full_name
        elif self.role == 'student' and self.student_profile:
            return self.student_profile.full_name
        return self.username

    @property
    def is_student(self):
        return self.role == 'student' and self.student_profile is not None

    def get_submissions(self):
        return self.student_profile.submissions if self.is_student else []

    def set_password(self, password):
        self.password = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=16
        )

    def check_password(self, password):
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
    user = db.relationship('User', back_populates='teacher_profile', overlaps="teacher")
    department = db.relationship('Department', back_populates='teachers')
    subjects = db.relationship('Subject', secondary=teacher_subjects, back_populates='teachers')
    classrooms = db.relationship('Classroom', back_populates='teacher', cascade='all, delete-orphan')
    announcements = db.relationship('Announcement', back_populates='author')
    quizzes = db.relationship('Quiz', back_populates='teacher')

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
    user = db.relationship('User', back_populates='student_profile', overlaps="student")
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
    

# models.py
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
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages')
    classroom = db.relationship('Classroom', back_populates='messages')
    parent = db.relationship('Message', remote_side=[id], back_populates='replies')
    replies = db.relationship('Message', back_populates='parent', order_by='Message.sent_at.asc()')

    def get_recipients(self):
        """Returns all recipients of this message"""
        if self.is_announcement and self.classroom:
            return [s.user for s in self.classroom.students]
        elif self.recipient:
            return [self.recipient]
        return []

    def send_notifications(self):
        """Create notifications for all recipients"""
        for recipient in self.get_recipients():
            notification = Notification(
                user_id=recipient.id,
                title=f"New message from {self.sender.full_name()}",
                message=f"{self.title}",
                action_url=url_for('view_message', message_id=self.id),
                is_read=False
            )
            db.session.add(notification)
        db.session.commit()

    @classmethod
    def send_system_message(cls, title, content, recipient=None, classroom=None):
        """Helper method for system-generated messages"""
        message = cls(
            title=title,
            content=content,
            sender_id=1,  # System user
            recipient_id=recipient.id if recipient else None,
            classroom_id=classroom.id if classroom else None,
            is_announcement=bool(classroom and not recipient)
        )
        db.session.add(message)
        db.session.commit()
        message.send_notifications()
        return message

    def __repr__(self):
        return f'<Message {self.id}: {self.title}>'


class NotificationSettings(db.Model, BaseMixin):
    __tablename__ = 'notification_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Delivery methods
    email_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    in_app_enabled = db.Column(db.Boolean, default=True)
    
    # Notification types
    receive_assignments = db.Column(db.Boolean, default=True)
    receive_messages = db.Column(db.Boolean, default=True)
    receive_attendance = db.Column(db.Boolean, default=True)
    receive_announcements = db.Column(db.Boolean, default=True)
    receive_system = db.Column(db.Boolean, default=True)
    
    # Frequency settings
    digest_frequency = db.Column(db.String(20), default='immediate')  # immediate, daily, weekly
    quiet_hours_enabled = db.Column(db.Boolean, default=False)
    quiet_hours_start = db.Column(db.Time, default=time(22, 0))  # 10 PM
    quiet_hours_end = db.Column(db.Time, default=time(7, 0))    # 7 AM
    
    # Relationships
    user = db.relationship('User', back_populates='notification_settings')

    @classmethod
    def get_or_create(cls, user_id):
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings

    def update_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def to_dict(self):
        return {
            'email_enabled': self.email_enabled,
            'push_enabled': self.push_enabled,
            'in_app_enabled': self.in_app_enabled,
            'receive_assignments': self.receive_assignments,
            'receive_messages': self.receive_messages,
            'receive_attendance': self.receive_attendance,
            'receive_announcements': self.receive_announcements,
            'receive_system': self.receive_system,
            'digest_frequency': self.digest_frequency,
            'quiet_hours_enabled': self.quiet_hours_enabled,
            'quiet_hours_start': self.quiet_hours_start.strftime('%H:%M') if self.quiet_hours_start else None,
            'quiet_hours_end': self.quiet_hours_end.strftime('%H:%M') if self.quiet_hours_end else None
        }

    def should_receive(self, notification_type):
        """Check if user should receive this type of notification"""
        type_map = {
            'assignment': self.receive_assignments,
            'message': self.receive_messages,
            'attendance': self.receive_attendance,
            'announcement': self.receive_announcements,
            'system': self.receive_system
        }
        return type_map.get(notification_type, True)

    def is_quiet_time(self):
        """Check if current time falls within quiet hours"""
        if not self.quiet_hours_enabled:
            return False
            
        now = datetime.now().time()
        if self.quiet_hours_start < self.quiet_hours_end:
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:  # Overnight quiet hours (e.g., 10 PM to 7 AM)
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end

    def __repr__(self):
        return f'<NotificationSettings for User {self.user_id}>'


# Enhanced Notification class with additional methods
class Notification(db.Model, BaseMixin):
    __tablename__ = 'notifications'
    
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255))
    notification_type = db.Column(db.String(50))  # 'attendance', 'message', 'video_join', etc.
    related_id = db.Column(db.Integer)  # ID of related entity
    is_read = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default=PRIORITY_MEDIUM)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', back_populates='notifications')

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
        return self

    @classmethod
    def create_for_user(cls, user_id, title, message, link=None, 
                       notification_type=None, related_id=None, priority=PRIORITY_MEDIUM):
        """Create a notification for a single user"""
        notification = cls(
            user_id=user_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type,
            related_id=related_id,
            priority=priority
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @classmethod
    def create_for_users(cls, users, title, message, link=None, 
                        notification_type=None, related_id=None, priority=PRIORITY_MEDIUM):
        """Bulk create notifications for multiple users"""
        notifications = [
            cls(
                user_id=user.id,
                title=title,
                message=message,
                link=link,
                notification_type=notification_type,
                related_id=related_id,
                priority=priority
            )
            for user in users
        ]
        db.session.bulk_save_objects(notifications)
        db.session.commit()
        return notifications

    @classmethod
    def get_unread_count(cls, user_id):
        """Count unread notifications for a user"""
        return cls.query.filter_by(user_id=user_id, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user_id):
        """Mark all notifications as read for a user"""
        updated = cls.query.filter_by(user_id=user_id, is_read=False).update(
            {'is_read': True, 'read_at': datetime.utcnow()},
            synchronize_session=False
        )
        db.session.commit()
        return updated

    @classmethod
    def clear_all(cls, user_id):
        """Delete all notifications for a user"""
        deleted = cls.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return deleted

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'link': self.link,
            'type': self.notification_type,
            'is_read': self.is_read,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'related_id': self.related_id
        }

    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'

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
    timezone = db.Column(db.String(50), default='Africa/Dar_es_Salaam')  # Add this line

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
    
    @property
    def students(self):
        """Get active students in this classroom"""
        return [enrollment.student.user for enrollment in self.enrollments 
                if not getattr(enrollment, 'is_dropped', False) 
                and enrollment.student.user.is_active]

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

    @property
    def formatted_file_size(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    
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
    due_date = db.Column(db.DateTime(timezone=True), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_draft = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    subject = db.relationship('Subject', back_populates='assignments')
    classroom = db.relationship('Classroom', back_populates='assignments')
    author = db.relationship('User', back_populates='created_assignments')
    submissions = db.relationship('Submission', back_populates='assignment', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Assignment {self.title}>'

    def get_timezone(self, tz_string=None):
        """Safely get timezone object with proper fallbacks"""
        if not tz_string:
            return utc  # Default to UTC if no timezone specified
            
        try:
            # Try modern ZoneInfo first (Python 3.9+)
            from zoneinfo import ZoneInfo
            try:
                return ZoneInfo(tz_string)
            except Exception:
                pass
        except ImportError:
            pass
        
        # Fallback to pytz
        try:
            return timezone(tz_string)
        except Exception as e:
            current_app.logger.error(f"Invalid timezone '{tz_string}': {str(e)}")
            return utc  # Final fallback to UTC

    def time_remaining(self, user_tz_string=None):
        """Calculate time remaining until due date"""
        try:
            now = datetime.now(utc)
            
            # Ensure due_date is timezone-aware (convert if needed)
            if self.due_date.tzinfo is None:
                due_date = self.due_date.replace(tzinfo=utc)
            else:
                due_date = self.due_date
            
            remaining = due_date - now
            return remaining if remaining.total_seconds() > 0 else timedelta(0)
        except Exception as e:
            current_app.logger.error(f"Error calculating time remaining: {str(e)}")
            return timedelta(0)

    def local_due_date(self, user_tz_string=None):
        """Convert due date to user's local timezone"""
        try:
            user_tz = self.get_timezone(user_tz_string)
            
            # Ensure due_date is timezone-aware
            if self.due_date.tzinfo is None:
                due_date = self.due_date.replace(tzinfo=utc)
            else:
                due_date = self.due_date
            
            return due_date.astimezone(user_tz)
        except Exception as e:
            current_app.logger.error(f"Error converting to local time: {str(e)}")
            return self.due_date  # Fallback to original date

    def status(self, user_tz_string=None):
        """Get assignment status with icons"""
        remaining = self.time_remaining(user_tz_string)
        seconds = remaining.total_seconds()
        
        if self.is_draft:
            return ("draft", "Draft", "fas fa-edit")
        elif seconds <= 0:
            return ("overdue", "Overdue", "fas fa-exclamation-triangle")
        elif seconds <= 86400:  # 1 day
            return ("due-soon", "Due Soon", "fas fa-clock")
        else:
            return ("active", "Active", "far fa-clock")
        

class Submission(db.Model, BaseMixin):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    file_path = db.Column(db.String(512))
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_modified = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    assignment = db.relationship('Assignment', back_populates='submissions')
    student = db.relationship('Student', back_populates='submissions')
    
    def get_file_name(self):
        if self.file_path:
            return os.path.basename(self.file_path)
        return None
    
    @property
    def file_size(self):
        """Return the file size in bytes."""
        if self.file_path and os.path.exists(self.file_path):
            return os.path.getsize(self.file_path)
        return None

    def human_readable_file_size(self):
        """Return the file size in a human-readable format."""
        size = self.file_size
        if size is not None:
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "Unknown size"

    def get_file_size(self):
        if self.file_path and os.path.exists(self.file_path):
            size = os.path.getsize(self.file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024*1024:
                return f"{size/1024:.1f} KB"
            else:
                return f"{size/(1024*1024):.1f} MB"
        return None
    
    def get_file_icon(self):
        if not self.file_path:
            return "fa-file"
        
        ext = self.file_path.split('.')[-1].lower()
        if ext in {'pdf'}:
            return "fa-file-pdf"
        elif ext in {'doc', 'docx', 'odt', 'rtf'}:
            return "fa-file-word"
        elif ext in {'xls', 'xlsx'}:
            return "fa-file-excel"
        elif ext in {'ppt', 'pptx'}:
            return "fa-file-powerpoint"
        elif ext in {'zip', 'rar', '7z'}:
            return "fa-file-archive"
        elif ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg'}:
            return "fa-file-image"
        else:
            return "fa-file"

    @property
    def is_late(self):
        if not self.submitted_at or not self.assignment.due_date:
            return False
        return self.submitted_at > self.assignment.due_date

    @property
    def submitted_at_aware(self):
        """Return submission time as timezone-aware datetime in UTC"""
        if not self.submitted_at:
            return None
        return self.submitted_at.replace(tzinfo=ZoneInfo('UTC'))
    
    @property
    def last_modified_aware(self):
        """Return last modified time as timezone-aware datetime in UTC"""
        if not self.last_modified:
            return None
        return self.last_modified.replace(tzinfo=ZoneInfo('UTC'))
    
    def to_local_timezone(self, tz_string):
        """Convert timestamps to local timezone and return as dict"""
        try:
            user_tz = ZoneInfo(tz_string)
            result = {
                'submitted_at': self.submitted_at_aware.astimezone(user_tz) if self.submitted_at else None,
                'last_modified': self.last_modified_aware.astimezone(user_tz) if self.last_modified else None
            }
        except Exception as e:
            current_app.logger.error(f"Timezone conversion error: {str(e)}")
            # Fallback to UTC if conversion fails
            result = {
                'submitted_at': self.submitted_at_aware,
                'last_modified': self.last_modified_aware
            }
        return result
    
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
    """
    Database model representing a quiz question with multiple answer types.
    Supports multiple choice, true/false, and short answer questions.
    """
    
    __tablename__ = 'questions'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Question Content
    text = db.Column(db.Text, nullable=False, comment="The question text/content")
    question_type = db.Column(db.String(20), default='multiple_choice', 
                            comment="Type of question: multiple_choice, true_false, or short_answer")
    
    # Answer Options (stored as JSON for flexibility)
    options = db.Column(db.JSON, comment="Available choices for multiple choice questions")
    correct_option = db.Column(db.String(500), comment="Correct answer key or value")
    
    # Question Metadata
    points = db.Column(db.Integer, default=1, comment="Point value for this question")
    time_limit = db.Column(db.Integer, default=60, comment="Time limit in seconds (0 for no limit)")
    position = db.Column(db.Integer, comment="Ordering position within the quiz")
    is_optional = db.Column(db.Boolean, default=False, comment="Whether answering is optional")
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment="When question was created")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                         onupdate=datetime.utcnow, comment="When question was last updated")
    
    # Foreign Key Relationships
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    
    # Relationships
    quiz = db.relationship('Quiz', back_populates='questions')
    answers = db.relationship('QuizAnswer', back_populates='question', 
                            cascade='all, delete-orphan')

    def update_position(self, new_position):
        """
        Update this question's position and reorder other questions in the quiz
        
        Args:
            new_position (int): The new position for this question
            
        Returns:
            Question: The updated question instance
        """
        old_position = self.position
        
        if new_position > old_position:
            # Move down - shift questions between old and new up
            Question.query.filter(
                Question.quiz_id == self.quiz_id,
                Question.position > old_position,
                Question.position <= new_position
            ).update({Question.position: Question.position - 1})
        else:
            # Move up - shift questions between new and old down
            Question.query.filter(
                Question.quiz_id == self.quiz_id,
                Question.position >= new_position,
                Question.position < old_position
            ).update({Question.position: Question.position + 1})
            
        self.position = new_position
        db.session.commit()
        return self

    @property
    def formatted_options(self):
        """
        Returns question options in a standardized dictionary format
        
        Returns:
            dict: Options formatted as {letter: text} for multiple choice,
                  {0: 'False', 1: 'True'} for true/false,
                  empty dict for short answer
        """
        if self.question_type == 'multiple_choice':
            if isinstance(self.options, dict):
                return self.options
            elif isinstance(self.options, list):
                return {chr(65+i): option for i, option in enumerate(self.options)}
            return {
                'A': 'Option A',
                'B': 'Option B', 
                'C': 'Option C',
                'D': 'Option D'
            }
        elif self.question_type == 'true_false':
            return {0: 'False', 1: 'True'}
        return {}

    def validate_answer(self, answer):
        """
        Check if the provided answer is correct
        
        Args:
            answer (str): The answer to validate
            
        Returns:
            bool: True if answer is correct, False otherwise
        """
        if not answer:
            return False
            
        answer = str(answer).strip()
        
        if self.question_type == 'multiple_choice':
            # For dictionary format options (e.g., {'A': 'Option 1'})
            if isinstance(self.options, dict):
                return answer.upper() == str(self.correct_option).upper()
            
            # For list format options (e.g., ['Option 1', 'Option 2'])
            elif isinstance(self.options, list):
                try:
                    selected_index = int(answer)
                    if 0 <= selected_index < len(self.options):
                        selected_text = str(self.options[selected_index]).upper()
                        return selected_text == str(self.correct_option).upper()
                except ValueError:
                    return False
                    
        elif self.question_type == 'true_false':
            return answer.upper() == str(self.correct_option).upper()
            
        elif self.question_type == 'short_answer':
            user_answer = answer.lower()
            # Support multiple correct answers separated by pipes
            correct_answers = [a.strip().lower() 
                             for a in str(self.correct_option).split('|')]
            return user_answer in correct_answers
            
        return False

    def __repr__(self):
        """String representation for debugging"""
        return f'<Question {self.id}: {self.text[:50]}{"..." if len(self.text)>50 else ""}>'
    

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
    score = db.Column(db.Float, default=0.0)  # Changed from None to 0.0 default
    correct_answers = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    time_spent = db.Column(db.Integer, default=0)  # in seconds
    
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

    @property
    def is_completed(self):
        """Check if attempt is completed"""
        return self.completed_at is not None
    
    @property
    def is_passed(self):
        """Check if attempt passed (score >= 70%)"""
        return self.score >= 70 if self.is_completed else False
    
    @validates('score')
    def validate_score(self, key, score):
        """Validate score is between 0 and 100 and only set when completed"""
        if score is not None:
            if not 0 <= score <= 100:
                raise ValueError("Score must be between 0 and 100")
            if not self.is_completed:
                raise ValueError("Cannot set score before completing attempt")
        return score

    def calculate_score(self):
        """Calculate score based on correct answers"""
        if not self.answers:
            self.score = 0.0
            self.correct_answers = 0
            self.total_questions = 0
            return self.score
            
        self.correct_answers = sum(1 for answer in self.answers if answer.is_correct)
        self.total_questions = len(self.quiz.questions) if self.quiz else len(self.answers)
        
        if self.total_questions > 0:
            self.score = round((self.correct_answers / self.total_questions) * 100, 2)
        else:
            self.score = 0.0
            
        return self.score

    def complete_attempt(self):
        """Mark attempt as completed and calculate final score"""
        if not self.is_completed:
            self.completed_at = datetime.now(timezone.utc)
            if self.started_at:
                started = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
                self.time_spent = (self.completed_at - started).total_seconds()
            self.calculate_score()
            db.session.commit()

    def to_dict(self):
        """Convert attempt to dictionary for JSON responses"""
        return {
            'id': self.id,
            'quiz_id': self.quiz_id,
            'score': self.score,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'time_spent': self.time_spent,
            'status': self.status,
            'is_passed': self.is_passed,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    @property
    def status(self):
        """Get attempt status"""
        if self.is_completed:
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
    answered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('Question', back_populates='answers')

    @property
    def has_answer(self):
        """Simplified and more reliable answer check"""
        if self.question.question_type == 'short_answer':
            return bool(self.answer_text and str(self.answer_text).strip())
        return self.selected_answer is not None



class OnlineSession(db.Model, BaseMixin):
    __tablename__ = 'online_sessions'
    
    STATUS_CHOICES = {
        'scheduled': 'Scheduled',
        'upcoming': 'Starting Soon',
        'live': 'Live Now',
        'ended': 'Completed',
        'cancelled': 'Cancelled'
    }

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(100), unique=True, nullable=False)
    session_name = db.Column(db.String(200), nullable=False, default="New Session")
    description = db.Column(db.Text, nullable=True)
    session_link = db.Column(db.String(500), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='scheduled')
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True))
    original_timezone = db.Column(db.String(50), default='Africa/Dar_es_Salaam')
    duration_minutes = db.Column(db.Integer)
    recording_url = db.Column(db.String(500))
    last_updated = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    max_participants = db.Column(db.Integer, default=50)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(100))  # e.g., 'weekly', 'daily'
    attendance_finalized = db.Column(db.Boolean, default=False)


    # Relationships
    classroom = db.relationship('Classroom', back_populates='sessions')
    creator = db.relationship('User', back_populates='created_sessions')
    attendances = db.relationship('Attendance', back_populates='session')


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensure_timezone_awareness()
        self._set_default_name()
        self.validate_and_calculate()

    def get_local_time_range(self):
        """
        Get formatted time range string in local timezone
        Replaces the previous get_local_time_string method with more functionality
        """
        try:
            start_local, end_local = self.get_local_times()
            
            if not start_local:
                return "Invalid time data"
                
            if not end_local:
                return start_local.strftime('%b %d, %Y %I:%M %p')
                
            if start_local.date() == end_local.date():
                return f"{start_local.strftime('%b %d, %Y %I:%M %p')} - {end_local.strftime('%I:%M %p')}"
            return f"{start_local.strftime('%b %d, %Y %I:%M %p')} - {end_local.strftime('%b %d, %Y %I:%M %p')}"
            
        except Exception as e:
            current_app.logger.error(f"Error formatting time range: {e}")
            return "Invalid time data"

    def _ensure_timezone_awareness(self):
        """
        Ensure all datetime fields are timezone-aware UTC.
        This is the key fix for the comparison errors.
        """
        if self.start_time:
            if not isinstance(self.start_time, datetime):
                raise ValueError("start_time must be a datetime object")
            if not self.start_time.tzinfo:
                self.start_time = self.start_time.replace(tzinfo=timezone.utc)
            else:
                self.start_time = self.start_time.astimezone(timezone.utc)
        
        if self.end_time:
            if not isinstance(self.end_time, datetime):
                raise ValueError("end_time must be a datetime object")
            if not self.end_time.tzinfo:
                self.end_time = self.end_time.replace(tzinfo=timezone.utc)
            else:
                self.end_time = self.end_time.astimezone(timezone.utc)


    def _set_default_name(self):
        """Set default session name if not provided"""
        if not self.session_name:
            self.session_name = f"Session {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    def validate_and_calculate(self):
        """Validate session data and calculate derived fields"""
        self._validate_times()
        self._calculate_duration()
        self._update_status()

    def _validate_times(self):
        """Validate start and end times"""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValueError("End time must be after start time")
        if self.start_time and self.start_time < datetime.now(timezone.utc) - timedelta(days=30):
            raise ValueError("Start time cannot be more than 30 days in the past")

    def _calculate_duration(self):
        """Calculate duration in minutes"""
        if self.start_time and self.end_time:
            self.duration_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        else:
            self.duration_minutes = None

    def _update_status(self):
        """Update status based on current time"""
        if not self.is_valid:
            self.status = 'cancelled'
            return
            
        now = datetime.now(timezone.utc)
        if now < self.start_time:
            self.status = 'scheduled'
        elif self.start_time <= now <= self.end_time:
            self.status = 'live'
        else:
            self.status = 'ended'

    # In your model
    def update_status(self):
        """Update status based on current time"""
        if not self.is_valid:
            self.status = 'cancelled'
            return
            
        now = datetime.now(timezone.utc)
        if now < self.start_time:
            self.status = 'scheduled'
        elif self.start_time <= now <= self.end_time:
            self.status = 'live'
        else:
            self.status = 'ended'

    # Add this new method to replace the missing get_status
    def get_status(self, current_time=None):
        """
        Get current status of the session with proper timezone handling.
        Replaces the previous _update_status method.
        """
        if not self.is_valid:
            return 'cancelled'
            
        now = current_time if current_time else datetime.now(timezone.utc)
        if not now.tzinfo:
            now = now.replace(tzinfo=timezone.utc)
        
        # Ensure our comparison datetimes are timezone-aware
        self._ensure_timezone_awareness()
        
        if now < self.start_time:
            return 'scheduled'
        elif self.start_time <= now <= self.end_time:
            return 'live'
        return 'ended'

    @property
    def is_valid(self):
        """Check if session has valid data with safe timezone comparisons"""
        try:
            self._ensure_timezone_awareness()
            
            if not all([
                self.room_id,
                self.session_name,
                self.start_time,
                self.end_time,
                isinstance(self.start_time, datetime),
                isinstance(self.end_time, datetime)
            ]):
                return False
                
            # Now safe to compare as both are timezone-aware
            return self.start_time < self.end_time
            
        except Exception as e:
            current_app.logger.error(f"Validation error: {e}")
            return False

    @property
    def time_until_start(self):
        """Time remaining until session starts with timezone safety"""
        if not self.is_valid:
            return None
            
        self._ensure_timezone_awareness()
        now = datetime.now(timezone.utc)
        return max(self.start_time - now, timedelta(0))

    @property
    def time_remaining(self):
        """Time remaining in current session with timezone safety"""
        if not self.is_valid or not self.is_active:
            return None
            
        self._ensure_timezone_awareness()
        now = datetime.now(timezone.utc)
        return max(self.end_time - now, timedelta(0))

    @property
    def is_active(self):
        """Check if session is currently live with timezone safety"""
        if not self.is_valid:
            return False
            
        self._ensure_timezone_awareness()
        now = datetime.now(timezone.utc)
        if not now.tzinfo:
            now = now.replace(tzinfo=timezone.utc)
        return self.start_time <= now <= self.end_time

    @property
    def display_timezone(self):
        """Get display timezone with fallbacks"""
        return (
            self.original_timezone or
            getattr(self.classroom, 'timezone', None) or
            getattr(self.creator, 'timezone', None) or
            'Africa/Dar_es_Salaam'
        )

    def get_local_times(self):
        """Return start and end times in local timezone"""
        try:
            tz = ZoneInfo(self.display_timezone)
            return (
                self.start_time.astimezone(tz),
                self.end_time.astimezone(tz) if self.end_time else None
            )
        except Exception as e:
            current_app.logger.error(f"Timezone conversion error: {e}")
            return self.start_time, self.end_time

    def get_local_time_string(self):
        """Get formatted local time string"""
        start, end = self.get_local_times()
        if not start:
            return "Invalid time data"
            
        if not end:
            return start.strftime('%b %d, %Y %I:%M %p')
            
        if start.date() == end.date():
            return f"{start.strftime('%b %d, %Y %I:%M %p')} - {end.strftime('%I:%M %p')}"
        return f"{start.strftime('%b %d, %Y %I:%M %p')} - {end.strftime('%b %d, %Y %I:%M %p')}"

    def can_join(self, user=None):
        """Check if session can be joined"""
        if not self.is_valid or self.status == 'cancelled':
            return False
            
        now = datetime.now(timezone.utc)
        join_window_start = self.start_time - timedelta(minutes=15)  # 15 minute early join window
        return join_window_start <= now <= self.end_time

    def to_dict(self):
        """Convert session to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.session_name,
            'description': self.description,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'room_id': self.room_id,
            'recording_url': self.recording_url,
            'time_until_start': self.time_until_start.total_seconds() if self.time_until_start else None,
            'time_remaining': self.time_remaining.total_seconds() if self.time_remaining else None,
            'is_active': self.is_active,
            'can_join': self.can_join()
        }

    def __repr__(self):
        return f"<OnlineSession {self.id}: {self.session_name} ({self.status})>"
 
class Attendance(db.Model, BaseMixin):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('online_sessions.id'), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False)  # Added this
    date = db.Column(db.Date, nullable=False)  # Added this
    duration = db.Column(db.Integer)  # Added this (nullable since it's set later)
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