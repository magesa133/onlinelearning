"""empty message

Revision ID: e2d436faacec
Revises: d7fa1bda7635
Create Date: 2025-04-04 20:47:08.506722

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'e2d436faacec'
down_revision = 'd7fa1bda7635'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    conn = op.get_bind()
    # Use text() to properly format the SQL query
    query = text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    )
    result = conn.execute(query, {'table': table_name, 'column': column_name})
    return result.scalar() > 0


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        if not column_exists('questions', 'question_type'):
            batch_op.add_column(sa.Column('question_type', sa.String(length=20), nullable=True))
        if not column_exists('questions', 'correct_answer'):
            batch_op.add_column(sa.Column('correct_answer', sa.String(length=255), nullable=True))
        
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=True)
        batch_op.alter_column('correct_option',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
        batch_op.create_index('ix_question_quiz_id', ['quiz_id'], unique=False)

    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        if not column_exists('quiz_answers', 'answer_text'):
            batch_op.add_column(sa.Column('answer_text', sa.Text(), nullable=True))
        if not column_exists('quiz_answers', 'time_taken'):
            batch_op.add_column(sa.Column('time_taken', sa.Integer(), nullable=True))
        
        batch_op.create_index('ix_quiz_answer_attempt_id', ['attempt_id'], unique=False)
        batch_op.create_index('ix_quiz_answer_question_id', ['question_id'], unique=False)
        
        if column_exists('quiz_answers', 'selected_answer'):
            batch_op.drop_column('selected_answer')
        if column_exists('quiz_answers', 'updated_at'):
            batch_op.drop_column('updated_at')

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        if not column_exists('quiz_attempts', 'started_at'):
            batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        if not column_exists('quiz_attempts', 'ip_address'):
            batch_op.add_column(sa.Column('ip_address', sa.String(length=45), nullable=True))
        
        batch_op.create_index('ix_quiz_attempt_quiz_id', ['quiz_id'], unique=False)
        batch_op.create_index('ix_quiz_attempt_student_id', ['student_id'], unique=False)
        
        # Check if foreign key exists before dropping
        inspector = sa.inspect(op.get_bind())
        fks = inspector.get_foreign_keys('quiz_attempts')
        if any(fk['name'] == 'quiz_attempts_ibfk_2' for fk in fks):
            batch_op.drop_constraint('quiz_attempts_ibfk_2', type_='foreignkey')
        
        batch_op.create_foreign_key(None, 'users', ['student_id'], ['id'])
        
        if column_exists('quiz_attempts', 'updated_at'):
            batch_op.drop_column('updated_at')
        if column_exists('quiz_attempts', 'created_at'):
            batch_op.drop_column('created_at')

    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.create_index('ix_quiz_status', ['status'], unique=False)
        batch_op.create_index('ix_quiz_teacher_id', ['teacher_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.drop_index('ix_quiz_teacher_id')
        batch_op.drop_index('ix_quiz_status')

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        if not column_exists('quiz_attempts', 'created_at'):
            batch_op.add_column(sa.Column('created_at', mysql.DATETIME(), nullable=True))
        if not column_exists('quiz_attempts', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', mysql.DATETIME(), nullable=True))
        
        # Drop the new foreign key if it exists
        inspector = sa.inspect(op.get_bind())
        fks = inspector.get_foreign_keys('quiz_attempts')
        if any(fk['referred_table'] == 'users' for fk in fks):
            batch_op.drop_constraint(None, type_='foreignkey')
        
        batch_op.create_foreign_key('quiz_attempts_ibfk_2', 'students', ['student_id'], ['id'])
        
        batch_op.drop_index('ix_quiz_attempt_student_id')
        batch_op.drop_index('ix_quiz_attempt_quiz_id')
        
        if column_exists('quiz_attempts', 'ip_address'):
            batch_op.drop_column('ip_address')
        if column_exists('quiz_attempts', 'started_at'):
            batch_op.drop_column('started_at')

    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        if not column_exists('quiz_answers', 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', mysql.DATETIME(), nullable=True))
        if not column_exists('quiz_answers', 'selected_answer'):
            batch_op.add_column(sa.Column('selected_answer', mysql.VARCHAR(length=1), nullable=False))
        
        batch_op.drop_index('ix_quiz_answer_question_id')
        batch_op.drop_index('ix_quiz_answer_attempt_id')
        
        if column_exists('quiz_answers', 'time_taken'):
            batch_op.drop_column('time_taken')
        if column_exists('quiz_answers', 'answer_text'):
            batch_op.drop_column('answer_text')

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_index('ix_question_quiz_id')
        batch_op.alter_column('correct_option',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=False)
        
        if column_exists('questions', 'correct_answer'):
            batch_op.drop_column('correct_answer')
        if column_exists('questions', 'question_type'):
            batch_op.drop_column('question_type')

    # ### end Alembic commands ###