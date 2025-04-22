"""Update datetime columns to support timezones with proper constraint handling

Revision ID: ee0b6e656ab4
Revises: f8204914ecbf
Create Date: 2025-04-19 10:18:58.291447

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision = 'ee0b6e656ab4'
down_revision = 'f8204914ecbf'
branch_labels = None
depends_on = None

def safe_drop_index(table_name, index_name):
    """Safely drop an index if it exists and isn't needed for constraints"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if index exists
    indexes = inspector.get_indexes(table_name)
    if not any(idx['name'] == index_name for idx in indexes):
        return False
    
    # Check if index is used in any foreign key constraints
    try:
        fks = inspector.get_foreign_keys(table_name)
        index_columns = None
        
        # Get columns in the index we want to drop
        for idx in indexes:
            if idx['name'] == index_name:
                index_columns = set(idx['column_names'])
                break
        
        if index_columns:
            for fk in fks:
                if set(fk['constrained_columns']) == index_columns:
                    # Index is used in a foreign key - skip dropping
                    return False
        
        # Safe to drop the index
        op.drop_index(index_name, table_name=table_name)
        return True
    except Exception as e:
        print(f"Warning: Could not check foreign keys for {table_name}.{index_name}: {str(e)}")
        return False

def handle_orphaned_questions():
    """Handle questions with invalid quiz references before adding constraints"""
    conn = op.get_bind()
    
    # First make the column nullable if it isn't already
    inspector = Inspector.from_engine(conn)
    questions_cols = {c['name']: c for c in inspector.get_columns('questions')}
    if 'quiz_id' in questions_cols and not questions_cols['quiz_id']['nullable']:
        op.alter_column(
            'questions',
            'quiz_id',
            existing_type=sa.Integer(),
            nullable=True
        )
    
    # Set invalid references to NULL
    conn.execute(
        sa.text("""
            UPDATE questions 
            SET quiz_id = NULL 
            WHERE quiz_id IS NOT NULL 
            AND quiz_id NOT IN (SELECT id FROM quizzes)
        """)
    )

def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Step 1: Handle data integrity first
    if 'questions' in inspector.get_table_names() and 'quizzes' in inspector.get_table_names():
        handle_orphaned_questions()
    
    # Step 2: Add foreign key constraint (with proper error handling)
    if 'questions' in inspector.get_table_names():
        try:
            with op.batch_alter_table('questions', schema=None) as batch_op:
                batch_op.create_foreign_key(
                    'fk_question_quiz',
                    'quizzes',
                    ['quiz_id'],
                    ['id'],
                    ondelete='SET NULL'  # Handle quiz deletions gracefully
                )
        except OperationalError as e:
            print(f"Warning: Could not create foreign key: {str(e)}")
            # Continue with migration even if FK creation fails
    
    # Step 3: Safely drop the index (only if not needed for constraints)
    if 'quizzes' in inspector.get_table_names():
        safe_drop_index('quizzes', 'ix_quiz_teacher_id')

def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Step 1: Recreate index if it doesn't exist
    if 'quizzes' in inspector.get_table_names():
        indexes = inspector.get_indexes('quizzes')
        if not any(idx['name'] == 'ix_quiz_teacher_id' for idx in indexes):
            op.create_index(
                'ix_quiz_teacher_id',
                'quizzes',
                ['teacher_id'],
                unique=False
            )
    
    # Step 2: Drop foreign key constraint if it exists
    if 'questions' in inspector.get_table_names():
        constraints = inspector.get_foreign_keys('questions')
        if any(fk['name'] == 'fk_question_quiz' for fk in constraints):
            with op.batch_alter_table('questions', schema=None) as batch_op:
                batch_op.drop_constraint('fk_question_quiz', type_='foreignkey')