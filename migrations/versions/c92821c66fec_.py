"""Add student details and classroom improvements

Revision ID: c92821c66fec
Revises: be0a279c31fe
Create Date: 2025-04-02 08:21:53.230033

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'c92821c66fec'
down_revision = 'be0a279c31fe'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    constraints = inspector.get_unique_constraints(table_name)
    return any(con['name'] == constraint_name for con in constraints)

def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)

def foreign_key_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    fks = inspector.get_foreign_keys(table_name)
    return any(fk['name'] == constraint_name for fk in fks)

def upgrade():
    # First modify classrooms table
    with op.batch_alter_table('classrooms', schema=None) as batch_op:
        if not column_exists('classrooms', 'class_name'):
            batch_op.add_column(sa.Column('class_name', sa.String(length=100), nullable=False))
        
        if not column_exists('classrooms', 'section'):
            batch_op.add_column(sa.Column('section', sa.String(length=10), nullable=True))
        
        if not column_exists('classrooms', 'room_number'):
            batch_op.add_column(sa.Column('room_number', sa.String(length=20), nullable=True))
        
        if not column_exists('classrooms', 'description'):
            batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        
        # Only drop constraints if they exist and aren't needed for FKs
        if constraint_exists('classrooms', 'code'):
            batch_op.drop_constraint('code', type_='unique')
        if constraint_exists('classrooms', 'code_2'):
            batch_op.drop_constraint('code_2', type_='unique')
        
        if column_exists('classrooms', 'name'):
            batch_op.drop_column('name')
        if column_exists('classrooms', 'code'):
            batch_op.drop_column('code')

    # Then modify students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        if not column_exists('students', 'first_name'):
            batch_op.add_column(sa.Column('first_name', sa.String(length=50), nullable=False))
        if not column_exists('students', 'last_name'):
            batch_op.add_column(sa.Column('last_name', sa.String(length=50), nullable=False))
        if not column_exists('students', 'address'):
            batch_op.add_column(sa.Column('address', sa.String(length=200), nullable=True))
        if not column_exists('students', 'phone_number'):
            batch_op.add_column(sa.Column('phone_number', sa.String(length=20), nullable=True))
        if not column_exists('students', 'emergency_contact'):
            batch_op.add_column(sa.Column('emergency_contact', sa.String(length=100), nullable=True))
        
        batch_op.alter_column('enrollment_date',
               existing_type=sa.DATE(),
               nullable=True)
        
        # Skip dropping idx_student_department if it's needed for a foreign key
        if index_exists('students', 'idx_student_gpa'):
            batch_op.drop_index('idx_student_gpa')

def downgrade():
    # Revert students table changes
    with op.batch_alter_table('students', schema=None) as batch_op:
        if not index_exists('students', 'idx_student_gpa'):
            batch_op.create_index('idx_student_gpa', ['gpa'], unique=False)
        
        batch_op.alter_column('enrollment_date',
               existing_type=sa.DATE(),
               nullable=False)
        
        if column_exists('students', 'emergency_contact'):
            batch_op.drop_column('emergency_contact')
        if column_exists('students', 'phone_number'):
            batch_op.drop_column('phone_number')
        if column_exists('students', 'address'):
            batch_op.drop_column('address')
        if column_exists('students', 'last_name'):
            batch_op.drop_column('last_name')
        if column_exists('students', 'first_name'):
            batch_op.drop_column('first_name')

    # Revert classrooms table changes
    with op.batch_alter_table('classrooms', schema=None) as batch_op:
        if not column_exists('classrooms', 'code'):
            batch_op.add_column(sa.Column('code', mysql.VARCHAR(length=20), nullable=True))
        if not column_exists('classrooms', 'name'):
            batch_op.add_column(sa.Column('name', mysql.VARCHAR(length=100), nullable=False))
        
        if not constraint_exists('classrooms', 'code'):
            batch_op.create_index('code', ['code'], unique=True)
        if not constraint_exists('classrooms', 'code_2'):
            batch_op.create_index('code_2', ['code'], unique=True)
        
        if column_exists('classrooms', 'description'):
            batch_op.drop_column('description')
        if column_exists('classrooms', 'room_number'):
            batch_op.drop_column('room_number')
        if column_exists('classrooms', 'section'):
            batch_op.drop_column('section')
        if column_exists('classrooms', 'class_name'):
            batch_op.drop_column('class_name')