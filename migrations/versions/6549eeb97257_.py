"""Update foreign key constraints for questions table

Revision ID: 6549eeb97257
Revises: ee0b6e656ab4
Create Date: 2025-04-19 12:06:19.384681

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '6549eeb97257'
down_revision = 'ee0b6e656ab4'
branch_labels = None
depends_on = None

def check_table_exists(table_name):
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    return table_name in inspector.get_table_names()

def check_column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def upgrade():
    conn = op.get_bind()
    
    # Step 1: Clean up orphaned records
    if check_table_exists('questions') and check_table_exists('quizzes'):
        conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
        conn.execute(sa.text("""
            UPDATE questions 
            SET quiz_id = NULL 
            WHERE quiz_id IS NOT NULL 
            AND quiz_id NOT IN (SELECT id FROM quizzes)
            AND quiz_id != 0
        """))
        conn.execute(sa.text("""
            DELETE FROM questions
            WHERE quiz_id IS NOT NULL
            AND quiz_id NOT IN (SELECT id FROM quizzes)
        """))
        conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))

    # Step 2: Modify the questions table
    if check_table_exists('questions'):
        with op.batch_alter_table('questions', schema=None) as batch_op:
            inspector = Inspector.from_engine(conn)
            
            # Find and drop any existing foreign keys to quizzes
            for fk in inspector.get_foreign_keys('questions'):
                if fk['referred_table'] == 'quizzes' and 'quiz_id' in fk['constrained_columns']:
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
                    batch_op.drop_constraint(fk['name'], type_='foreignkey')
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
            
            # Modify quiz_id column
            if check_column_exists('questions', 'quiz_id'):
                conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
                conn.execute(sa.text("UPDATE questions SET quiz_id = 0 WHERE quiz_id IS NULL"))
                batch_op.alter_column(
                    'quiz_id',
                    existing_type=mysql.INTEGER(display_width=11),
                    nullable=False
                )
                conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
            
            # Create new foreign key with CASCADE
            batch_op.create_foreign_key(
                'fk_questions_quiz_id',
                'quizzes',
                ['quiz_id'],
                ['id'],
                ondelete='CASCADE'
            )

    # Step 3: Skip dropping problematic indexes (not essential for the migration)
    # We'll leave these indexes in place since they're required by foreign keys

def downgrade():
    conn = op.get_bind()
    
    # Step 1: Revert questions table changes
    if check_table_exists('questions'):
        with op.batch_alter_table('questions', schema=None) as batch_op:
            inspector = Inspector.from_engine(conn)
            
            # Drop current foreign key if it exists
            for fk in inspector.get_foreign_keys('questions'):
                if fk['referred_table'] == 'quizzes' and 'quiz_id' in fk['constrained_columns']:
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
                    batch_op.drop_constraint(fk['name'], type_='foreignkey')
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
            
            # Revert to nullable if column exists
            if check_column_exists('questions', 'quiz_id'):
                batch_op.alter_column(
                    'quiz_id',
                    existing_type=mysql.INTEGER(display_width=11),
                    nullable=True
                )
            
            # Recreate original foreign key with SET NULL
            batch_op.create_foreign_key(
                'fk_question_quiz',
                'quizzes',
                ['quiz_id'],
                ['id'],
                ondelete='SET NULL'
            )