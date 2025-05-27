"""empty message

Revision ID: d9f909641b5c
Revises: ede64e3ec248
Create Date: 2025-04-24 15:48:03.659485

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9f909641b5c'
down_revision = 'ede64e3ec248'
branch_labels = None
depends_on = None


"""Your migration message here"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'd9f909641b5c'
down_revision = 'ede64e3ec248'
branch_labels = None
depends_on = None


def upgrade():
    # Get existing constraint names
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    fkeys = inspector.get_foreign_keys('messages')

    # Drop foreign key only if it exists
    for fk in fkeys:
        if 'recipient_id' in fk['constrained_columns']:
            with op.batch_alter_table('messages') as batch_op:
                batch_op.drop_constraint(fk['name'], type_='foreignkey')
            break  # Assuming only one FK on recipient_id


def downgrade():
    # Recreate the foreign key if needed
    with op.batch_alter_table('messages') as batch_op:
        batch_op.create_foreign_key(
            'fk_messages_recipient_id',
            'users',
            ['recipient_id'],
            ['id']
        )
