"""Fix teacher relationship

Revision ID: 7e09f3cbcaab
Revises: 080f80557848
Create Date: 2024-12-15 13:55:08.768356

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7e09f3cbcaab'
down_revision = '080f80557848'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.alter_column('teacher_name',
               existing_type=mysql.VARCHAR(length=100),
               nullable=True)
        batch_op.alter_column('subject',
               existing_type=mysql.VARCHAR(length=100),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('teacher', schema=None) as batch_op:
        batch_op.alter_column('subject',
               existing_type=mysql.VARCHAR(length=100),
               nullable=False)
        batch_op.alter_column('teacher_name',
               existing_type=mysql.VARCHAR(length=100),
               nullable=False)

    # ### end Alembic commands ###