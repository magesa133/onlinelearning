"""empty message

Revision ID: f8204914ecbf
Revises: 5330149b5435
Create Date: 2025-04-19 09:00:03.346130

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'f8204914ecbf'
down_revision = '5330149b5435'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def index_exists(table_name, index_name):
    """Check if an index exists in a table"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def safe_drop_index(table_name, index_name):
    """Safely drop an index only if it exists and isn't needed for a foreign key"""
    if not index_exists(table_name, index_name):
        return
    
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if index is used in any foreign key constraints
    fks = inspector.get_foreign_keys(table_name)
    index_columns = None
    
    # Get columns in the index we want to drop
    for idx in inspector.get_indexes(table_name):
        if idx['name'] == index_name:
            index_columns = set(idx['column_names'])
            break
    
    if index_columns:
        for fk in fks:
            if set(fk['constrained_columns']) == index_columns:
                # Index is used in a foreign key - skip dropping
                return
    
    # Safe to drop the index
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_index(index_name)


def upgrade():
    # Handle questions table index
    safe_drop_index('questions', 'ix_question_quiz_id')

    # Add new columns to quiz_answers if they don't exist
    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        if not column_exists('quiz_answers', 'selected_answer'):
            batch_op.add_column(sa.Column('selected_answer', sa.String(length=500), nullable=True))
        if not column_exists('quiz_answers', 'points_earned'):
            batch_op.add_column(sa.Column('points_earned', sa.Float(), nullable=True))
        if not index_exists('quiz_answers', 'ix_quiz_answer_is_correct'):
            batch_op.create_index('ix_quiz_answer_is_correct', ['is_correct'], unique=False)

    # Add index to quiz_attempts if it doesn't exist
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        if not index_exists('quiz_attempts', 'ix_quiz_attempt_user_id'):
            batch_op.create_index('ix_quiz_attempt_user_id', ['user_id'], unique=False)

    # Handle quizzes table indexes
    safe_drop_index('quizzes', 'ix_quiz_status')
    safe_drop_index('quizzes', 'ix_quiz_teacher_id')


def downgrade():
    # Recreate indexes on quizzes if they don't exist
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        if not index_exists('quizzes', 'ix_quiz_teacher_id'):
            batch_op.create_index('ix_quiz_teacher_id', ['teacher_id'], unique=False)
        if not index_exists('quizzes', 'ix_quiz_status'):
            batch_op.create_index('ix_quiz_status', ['status'], unique=False)

    # Remove index from quiz_attempts if it exists
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        if index_exists('quiz_attempts', 'ix_quiz_attempt_user_id'):
            batch_op.drop_index('ix_quiz_attempt_user_id')

    # Remove columns from quiz_answers if they exist
    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        if index_exists('quiz_answers', 'ix_quiz_answer_is_correct'):
            batch_op.drop_index('ix_quiz_answer_is_correct')
        if column_exists('quiz_answers', 'points_earned'):
            batch_op.drop_column('points_earned')
        if column_exists('quiz_answers', 'selected_answer'):
            batch_op.drop_column('selected_answer')

    # Recreate index on questions if it doesn't exist
    with op.batch_alter_table('questions', schema=None) as batch_op:
        if not index_exists('questions', 'ix_question_quiz_id'):
            batch_op.create_index('ix_question_quiz_id', ['quiz_id'], unique=False)