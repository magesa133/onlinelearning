"""empty message

Revision ID: d7fa1bda7635
Revises: 2de1f0141b17
Create Date: 2025-04-03 16:30:08.606691

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd7fa1bda7635'
down_revision = '2de1f0141b17'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False))
        batch_op.add_column(sa.Column('archived_at', sa.DateTime(), nullable=True))
        batch_op.drop_column('is_deleted')
        batch_op.drop_column('is_published')
        batch_op.drop_column('is_archived')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_archived', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('is_published', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('is_deleted', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
        batch_op.drop_column('archived_at')
        batch_op.drop_column('status')

    # ### end Alembic commands ###
