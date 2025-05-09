"""empty message

Revision ID: 924b658c441c
Revises: 6d64b52d1a43
Create Date: 2025-04-20 02:42:59.896639

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '924b658c441c'
down_revision = '6d64b52d1a43'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=False)

    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'teachers', ['teacher_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('options',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=True)

    # ### end Alembic commands ###
