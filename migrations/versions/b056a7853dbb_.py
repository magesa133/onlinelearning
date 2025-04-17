"""empty message

Revision ID: b056a7853dbb_fixed
Revises: 0a40d123793d
Create Date: 2025-04-02 05:03:44.030905

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'b056a7853dbb_fixed'
down_revision = '0a40d123793d'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)

def upgrade():
    # Activities table
    with op.batch_alter_table('activities', schema=None) as batch_op:
        if not column_exists('activities', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('activities', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('activities', 'timestamp'):
            batch_op.drop_column('timestamp')

    # Assignments table
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        if not column_exists('assignments', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Attendances table
    with op.batch_alter_table('attendances', schema=None) as batch_op:
        if not column_exists('attendances', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('attendances', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('attendances', 'timestamp'):
            batch_op.drop_column('timestamp')

    # Class announcements table
    with op.batch_alter_table('class_announcements', schema=None) as batch_op:
        if not column_exists('class_announcements', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Classrooms table
    with op.batch_alter_table('classrooms', schema=None) as batch_op:
        if not column_exists('classrooms', 'name'):
            batch_op.add_column(sa.Column('name', sa.String(length=100), nullable=False))
        if not column_exists('classrooms', 'code'):
            batch_op.add_column(sa.Column('code', sa.String(length=20), nullable=True))
        if not column_exists('classrooms', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        if column_exists('classrooms', 'class_code'):
            batch_op.drop_index('class_code')
            batch_op.drop_column('class_code')
        if column_exists('classrooms', 'class_name'):
            batch_op.drop_column('class_name')
        
        batch_op.create_unique_constraint(None, ['code'])

    # Enrollments table
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        if not column_exists('enrollments', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('enrollments', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('enrollments', 'enrollment_date'):
            batch_op.drop_column('enrollment_date')

    # Messages table
    with op.batch_alter_table('messages', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('messages_ibfk_1', type_='foreignkey')
        except:
            pass
        try:
            batch_op.drop_constraint('messages_ibfk_3', type_='foreignkey')
        except:
            pass
        
        if index_exists('messages', 'idx_message_class'):
            batch_op.drop_index('idx_message_class')
        if index_exists('messages', 'ix_messages_timestamp'):
            batch_op.drop_index('ix_messages_timestamp')
        if index_exists('messages', 'idx_message_sender'):
            batch_op.drop_index('idx_message_sender')
        
        if not column_exists('messages', 'classroom_id'):
            batch_op.add_column(sa.Column('classroom_id', sa.Integer(), nullable=True))
        if not column_exists('messages', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('messages', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        batch_op.create_index('idx_message_sender', ['sender_id'], unique=False)
        batch_op.create_index('idx_message_classroom', ['classroom_id'], unique=False)
        
        batch_op.create_foreign_key('fk_messages_classroom', 'classrooms', ['classroom_id'], ['id'])
        batch_op.create_foreign_key('fk_messages_sender', 'users', ['sender_id'], ['id'])
        batch_op.create_foreign_key('fk_messages_recipient', 'users', ['recipient_id'], ['id'])
        
        if column_exists('messages', 'class_id'):
            batch_op.drop_column('class_id')
        if column_exists('messages', 'timestamp'):
            batch_op.drop_column('timestamp')
        if column_exists('messages', 'sender_role'):
            batch_op.drop_column('sender_role')

    # Online sessions table
    with op.batch_alter_table('online_sessions', schema=None) as batch_op:
        if not column_exists('online_sessions', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('online_sessions', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Questions table
    with op.batch_alter_table('questions', schema=None) as batch_op:
        if not column_exists('questions', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('questions', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Quiz answers table
    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        if not column_exists('quiz_answers', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('quiz_answers', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('quiz_answers', 'answered_at'):
            batch_op.drop_column('answered_at')

    # Quiz attempts table
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        if not column_exists('quiz_attempts', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('quiz_attempts', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('quiz_attempts', 'completed_at'):
            batch_op.drop_column('completed_at')
        if column_exists('quiz_attempts', 'started_at'):
            batch_op.drop_column('started_at')

    # Quizzes table
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        if not column_exists('quizzes', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Resource comments table
    with op.batch_alter_table('resource_comments', schema=None) as batch_op:
        if not column_exists('resource_comments', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Resources table
    with op.batch_alter_table('resources', schema=None) as batch_op:
        if not column_exists('resources', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('resources', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if index_exists('resources', 'idx_upload_date'):
            batch_op.drop_index('idx_upload_date')
        if column_exists('resources', 'upload_date'):
            batch_op.drop_column('upload_date')

    # Students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        if not column_exists('students', 'student_id'):
            batch_op.add_column(sa.Column('student_id', sa.String(length=20), nullable=True))
        if not column_exists('students', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('students', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        batch_op.alter_column('enrollment_date',
               existing_type=mysql.DATETIME(),
               type_=sa.Date(),
               nullable=False)
        batch_op.alter_column('graduation_date',
               existing_type=mysql.DATETIME(),
               type_=sa.Date(),
               existing_nullable=True)
        
        if index_exists('students', 'idx_student_name'):
            batch_op.drop_index('idx_student_name')
        if index_exists('students', 'student_id_number'):
            batch_op.drop_index('student_id_number')
        
        batch_op.create_unique_constraint(None, ['student_id'])
        
        if column_exists('students', 'first_name'):
            batch_op.drop_column('first_name')
        if column_exists('students', 'student_id_number'):
            batch_op.drop_column('student_id_number')
        if column_exists('students', 'last_name'):
            batch_op.drop_column('last_name')

    # Subjects table
    with op.batch_alter_table('subjects', schema=None) as batch_op:
        if not column_exists('subjects', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Submissions table
    with op.batch_alter_table('submissions', schema=None) as batch_op:
        if not column_exists('submissions', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('submissions', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('submissions', 'submitted_at'):
            batch_op.drop_column('submitted_at')

    # Tags table
    with op.batch_alter_table('tags', schema=None) as batch_op:
        if not column_exists('tags', 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        if not column_exists('tags', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Teachers table
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        if not column_exists('teachers', 'bio'):
            batch_op.add_column(sa.Column('bio', sa.Text(), nullable=True))
        if not column_exists('teachers', 'office_location'):
            batch_op.add_column(sa.Column('office_location', sa.String(length=100), nullable=True))
        if not column_exists('teachers', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        if column_exists('teachers', 'teacher_name'):
            batch_op.drop_column('teacher_name')

    # Users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        if not column_exists('users', 'is_active'):
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))
        if not column_exists('users', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.alter_column('role',
               existing_type=mysql.VARCHAR(length=50),
               type_=sa.String(length=20),
               existing_nullable=False)

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('role',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(length=50),
               existing_nullable=False)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('is_active')

    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_name', mysql.VARCHAR(length=100), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('office_location')
        batch_op.drop_column('bio')

    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('submissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitted_at', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('subjects', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_name', mysql.VARCHAR(length=100), nullable=False))
        batch_op.add_column(sa.Column('student_id_number', mysql.VARCHAR(length=20), nullable=True))
        batch_op.add_column(sa.Column('first_name', mysql.VARCHAR(length=100), nullable=False))
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_index('student_id_number', ['student_id_number'], unique=True)
        batch_op.create_index('idx_student_name', ['first_name', 'last_name'], unique=False)
        batch_op.alter_column('graduation_date',
               existing_type=sa.Date(),
               type_=mysql.DATETIME(),
               existing_nullable=True)
        batch_op.alter_column('enrollment_date',
               existing_type=sa.Date(),
               type_=mysql.DATETIME(),
               nullable=True)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('student_id')

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('upload_date', mysql.DATETIME(), nullable=True))
        batch_op.create_index('idx_upload_date', ['upload_date'], unique=False)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('resource_comments', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('started_at', mysql.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('answered_at', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('online_sessions', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sender_role', mysql.VARCHAR(length=20), nullable=False))
        batch_op.add_column(sa.Column('timestamp', mysql.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('class_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
        
        # First drop the new foreign keys
        batch_op.drop_constraint('fk_messages_classroom', type_='foreignkey')
        batch_op.drop_constraint('fk_messages_sender', type_='foreignkey')
        batch_op.drop_constraint('fk_messages_recipient', type_='foreignkey')
        
        # Drop new indexes
        batch_op.drop_index('idx_message_classroom')
        batch_op.drop_index('idx_message_sender')
        
        # Recreate old indexes
        batch_op.create_index('idx_message_sender', ['sender_id', 'sender_role'], unique=False)
        batch_op.create_index('ix_messages_timestamp', ['timestamp'], unique=False)
        batch_op.create_index('idx_message_class', ['class_id'], unique=False)
        
        # Recreate old foreign keys
        batch_op.create_foreign_key('messages_ibfk_1', 'classrooms', ['class_id'], ['id'])
        batch_op.create_foreign_key('messages_ibfk_3', 'students', ['recipient_id'], ['id'])
        
        # Drop new columns
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('classroom_id')

    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enrollment_date', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('classrooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('class_name', mysql.VARCHAR(length=100), nullable=False))
        batch_op.add_column(sa.Column('class_code', mysql.VARCHAR(length=20), nullable=True))
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_index('class_code', ['class_code'], unique=True)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('code')
        batch_op.drop_column('name')

    with op.batch_alter_table('class_announcements', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('attendances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timestamp', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timestamp', mysql.DATETIME(), nullable=True))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    # ### end Alembic commands ###