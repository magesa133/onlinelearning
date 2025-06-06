"""empty message

Revision ID: da58b181a02d
Revises: 800f4b027702
Create Date: 2025-05-20 03:37:30.580831

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'da58b181a02d'
down_revision = '800f4b027702'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_optional', sa.Boolean(), nullable=True, comment='Whether answering is optional'))
        batch_op.alter_column('text',
               existing_type=mysql.TEXT(),
               comment='The question text/content',
               existing_nullable=False)
        batch_op.alter_column('question_type',
               existing_type=mysql.VARCHAR(length=20),
               comment='Type of question: multiple_choice, true_false, or short_answer',
               existing_nullable=True)
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               comment='Available choices for multiple choice questions',
               existing_nullable=True)
        batch_op.alter_column('correct_option',
               existing_type=mysql.INTEGER(display_width=11),
               type_=sa.String(length=500),
               comment='Correct answer key or value',
               existing_nullable=True)
        batch_op.alter_column('points',
               existing_type=mysql.INTEGER(display_width=11),
               comment='Point value for this question',
               existing_nullable=True)
        batch_op.alter_column('time_limit',
               existing_type=mysql.INTEGER(display_width=11),
               comment='Time limit in seconds (0 for no limit)',
               existing_nullable=True)
        batch_op.alter_column('position',
               existing_type=mysql.INTEGER(display_width=11),
               comment='Ordering position within the quiz',
               existing_nullable=True)
        batch_op.alter_column('created_at',
               existing_type=mysql.DATETIME(),
               comment='When question was created',
               existing_nullable=True)
        batch_op.alter_column('updated_at',
               existing_type=mysql.DATETIME(),
               comment='When question was last updated',
               existing_nullable=True)
        batch_op.drop_column('correct_answer')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('correct_answer', mysql.VARCHAR(length=50), nullable=True))
        batch_op.alter_column('updated_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='When question was last updated',
               existing_nullable=True)
        batch_op.alter_column('created_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='When question was created',
               existing_nullable=True)
        batch_op.alter_column('position',
               existing_type=mysql.INTEGER(display_width=11),
               comment=None,
               existing_comment='Ordering position within the quiz',
               existing_nullable=True)
        batch_op.alter_column('time_limit',
               existing_type=mysql.INTEGER(display_width=11),
               comment=None,
               existing_comment='Time limit in seconds (0 for no limit)',
               existing_nullable=True)
        batch_op.alter_column('points',
               existing_type=mysql.INTEGER(display_width=11),
               comment=None,
               existing_comment='Point value for this question',
               existing_nullable=True)
        batch_op.alter_column('correct_option',
               existing_type=sa.String(length=500),
               type_=mysql.INTEGER(display_width=11),
               comment=None,
               existing_comment='Correct answer key or value',
               existing_nullable=True)
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               comment=None,
               existing_comment='Available choices for multiple choice questions',
               existing_nullable=True)
        batch_op.alter_column('question_type',
               existing_type=mysql.VARCHAR(length=20),
               comment=None,
               existing_comment='Type of question: multiple_choice, true_false, or short_answer',
               existing_nullable=True)
        batch_op.alter_column('text',
               existing_type=mysql.TEXT(),
               comment=None,
               existing_comment='The question text/content',
               existing_nullable=False)
        batch_op.drop_column('is_optional')

    # ### end Alembic commands ###
