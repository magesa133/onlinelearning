"""empty message

Revision ID: f003dcecbfd6
Revises: 6a66d995524a
Create Date: 2025-05-23 23:06:15.465157

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'f003dcecbfd6'
down_revision = '6a66d995524a'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    columns = [column["name"] for column in inspector.get_columns("messages")]
    
    if "sent_at" not in columns:
        with op.batch_alter_table('messages', schema=None) as batch_op:
            batch_op.add_column(sa.Column('sent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('sent_at')
