"""empty message

Revision ID: e87c9a99a3ed
Revises: da58b181a02d
Create Date: 2025-05-21 00:01:18.662002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e87c9a99a3ed'
down_revision = 'da58b181a02d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=100), nullable=False))
        batch_op.add_column(sa.Column('notification_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('related_id', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_column('related_id')
        batch_op.drop_column('notification_type')
        batch_op.drop_column('title')

    # ### end Alembic commands ###
