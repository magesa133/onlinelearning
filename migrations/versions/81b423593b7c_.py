"""Remove department foreign key from students

Revision ID: 81b423593b7c
Revises: bc05562db8e7
Create Date: 2025-04-02 09:37:20.512152

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '81b423593b7c'
down_revision = 'bc05562db8e7'
branch_labels = None
depends_on = None

def get_foreign_key_name(table_name, column_name):
    """Get the actual foreign key constraint name"""
    conn = op.get_bind()
    inspector = inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk['constrained_columns']:
            return fk['name']
    return None

def index_exists(table_name, index_name):
    """Check if an index exists"""
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)

def upgrade():
    # First get the actual foreign key name
    fk_name = get_foreign_key_name('students', 'department_id')
    
    # Use raw SQL to ensure proper execution order
    if fk_name:
        op.execute(f"ALTER TABLE students DROP FOREIGN KEY {fk_name}")
    
    # Then drop the index if it exists
    if index_exists('students', 'idx_student_department'):
        op.execute("ALTER TABLE students DROP INDEX idx_student_department")

def downgrade():
    # Recreate the index first
    if not index_exists('students', 'idx_student_department'):
        op.execute("CREATE INDEX idx_student_department ON students (department_id)")
    
    # Then recreate the foreign key
    if not get_foreign_key_name('students', 'department_id'):
        op.execute(
            "ALTER TABLE students ADD CONSTRAINT fk_students_department_id "
            "FOREIGN KEY (department_id) REFERENCES departments (id)"
        )