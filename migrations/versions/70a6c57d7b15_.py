"""empty message

Revision ID: 70a6c57d7b15
Revises: 92f47a607067
Create Date: 2025-04-21 02:49:49.410085

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '70a6c57d7b15'
down_revision = '92f47a607067'
branch_labels = None
depends_on = None


def get_foreign_key_names(conn, table_name):
    """Helper function to get actual foreign key names from the database"""
    inspector = Inspector.from_engine(conn)
    fks = inspector.get_foreign_keys(table_name)
    return {fk['referred_table']: fk['name'] for fk in fks}


def upgrade():
    conn = op.get_bind()
    
    # Get actual foreign key names from the database
    fk_names = get_foreign_key_names(conn, 'quiz_attempts')
    
    # Clean up orphaned records first
    op.execute("""
        DELETE FROM quiz_attempts 
        WHERE quiz_id IS NOT NULL 
        AND quiz_id NOT IN (SELECT id FROM quizzes)
    """)
    
    op.execute("""
        DELETE FROM quiz_attempts 
        WHERE user_id IS NOT NULL 
        AND user_id NOT IN (SELECT id FROM users)
    """)
    
    op.execute("""
        DELETE FROM quiz_attempts 
        WHERE student_id IS NOT NULL 
        AND student_id NOT IN (SELECT id FROM students)
    """)

    # Handle quiz_attempts table changes
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        # Drop existing foreign key constraints using actual names
        if 'quizzes' in fk_names:
            batch_op.drop_constraint(fk_names['quizzes'], type_='foreignkey')
        if 'users' in fk_names:
            batch_op.drop_constraint(fk_names['users'], type_='foreignkey')
        if 'students' in fk_names:
            batch_op.drop_constraint(fk_names['students'], type_='foreignkey')
        
        # Drop indexes if they exist
        batch_op.drop_index('ix_quiz_attempt_quiz_id', if_exists=True)
        batch_op.drop_index('ix_quiz_attempt_student_id', if_exists=True)
        batch_op.drop_index('ix_quiz_attempt_user_id', if_exists=True)
        
        # Create new foreign keys with CASCADE
        batch_op.create_foreign_key(
            'fk_quiz_attempt_quiz_id',
            'quizzes', ['quiz_id'], ['id'],
            ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_quiz_attempt_user_id',
            'users', ['user_id'], ['id'],
            ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_quiz_attempt_student_id',
            'students', ['student_id'], ['id'],
            ondelete='CASCADE'
        )

    # Clean up orphaned records in quiz_answers
    op.execute("""
        DELETE FROM quiz_answers 
        WHERE attempt_id IS NOT NULL 
        AND attempt_id NOT IN (SELECT id FROM quiz_attempts)
    """)

    # Handle quiz_answers table changes
    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        # Drop existing foreign key constraint if it exists
        answer_fk_names = get_foreign_key_names(conn, 'quiz_answers')
        if 'quiz_attempts' in answer_fk_names:
            batch_op.drop_constraint(answer_fk_names['quiz_attempts'], type_='foreignkey')
        
        # Drop index if it exists
        batch_op.drop_index('ix_quiz_answer_attempt_id', if_exists=True)
        
        # Create new foreign key with CASCADE
        batch_op.create_foreign_key(
            'fk_quiz_answer_attempt_id',
            'quiz_attempts', ['attempt_id'], ['id'],
            ondelete='CASCADE'
        )


def downgrade():
    conn = op.get_bind()
    
    # Handle quiz_answers table downgrade
    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        # Drop the CASCADE foreign key
        batch_op.drop_constraint('fk_quiz_answer_attempt_id', type_='foreignkey')
        
        # Recreate the original index
        batch_op.create_index('ix_quiz_answer_attempt_id', ['attempt_id'], unique=False)
        
        # Recreate the original foreign key without CASCADE
        batch_op.create_foreign_key(
            'quiz_answers_ibfk_1',
            'quiz_attempts', ['attempt_id'], ['id']
        )

    # Handle quiz_attempts table downgrade
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        # Drop the CASCADE foreign keys
        batch_op.drop_constraint('fk_quiz_attempt_quiz_id', type_='foreignkey')
        batch_op.drop_constraint('fk_quiz_attempt_user_id', type_='foreignkey')
        batch_op.drop_constraint('fk_quiz_attempt_student_id', type_='foreignkey')
        
        # Recreate the original indexes
        batch_op.create_index('ix_quiz_attempt_quiz_id', ['quiz_id'], unique=False)
        batch_op.create_index('ix_quiz_attempt_student_id', ['student_id'], unique=False)
        batch_op.create_index('ix_quiz_attempt_user_id', ['user_id'], unique=False)
        
        # Recreate the original foreign keys without CASCADE
        batch_op.create_foreign_key(
            'quiz_attempts_ibfk_1',
            'quizzes', ['quiz_id'], ['id']
        )
        batch_op.create_foreign_key(
            'quiz_attempts_ibfk_2',
            'students', ['student_id'], ['id']
        )
        batch_op.create_foreign_key(
            'quiz_attempts_ibfk_3',
            'users', ['user_id'], ['id']
        )