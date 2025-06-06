"""Add description to OnlineSession

Revision ID: 4a2b9d34780b
Revises: ed2702ee1196
Create Date: 2025-05-16 22:59:46.235610

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a2b9d34780b'
down_revision = 'ed2702ee1196'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('online_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('online_sessions', schema=None) as batch_op:
        batch_op.drop_column('description')

    # ### end Alembic commands ###
