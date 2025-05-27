"""empty message

Revision ID: dfc8624ca7e5
Revises: f003dcecbfd6
Create Date: 2025-05-24 03:17:17.832020

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'dfc8624ca7e5'
down_revision = 'f003dcecbfd6'
branch_labels = None
depends_on = None


def upgrade():
    # Get database inspector to check existing tables/columns
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 1. Create notification_settings table if it doesn't exist
    if not inspector.has_table('notification_settings'):
        op.create_table('notification_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('email_enabled', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('push_enabled', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('in_app_enabled', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('receive_assignments', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('receive_messages', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('receive_attendance', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('receive_announcements', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('receive_system', sa.Boolean(), server_default='1', nullable=True),
            sa.Column('digest_frequency', sa.String(length=20), server_default='immediate', nullable=True),
            sa.Column('quiet_hours_enabled', sa.Boolean(), server_default='0', nullable=True),
            sa.Column('quiet_hours_start', sa.Time(), server_default='22:00:00', nullable=True),
            sa.Column('quiet_hours_end', sa.Time(), server_default='07:00:00', nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
    
    # 2. Add columns to notifications table if they don't exist
    if inspector.has_table('notifications'):
        columns = [col['name'] for col in inspector.get_columns('notifications')]
        
        if 'priority' not in columns:
            op.add_column('notifications', 
                sa.Column('priority', sa.String(length=20), nullable=True, server_default='medium'))
        
        if 'read_at' not in columns:
            op.add_column('notifications', 
                sa.Column('read_at', sa.DateTime(), nullable=True))
    
    # 3. Skip dropping indexes for messages table if they're used in FK constraints
    # (We'll leave these indexes in place since they're needed for constraints)


def downgrade():
    # Get database inspector to check existing tables/columns
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 1. Remove columns from notifications table if they exist
    if inspector.has_table('notifications'):
        columns = [col['name'] for col in inspector.get_columns('notifications')]
        
        if 'priority' in columns:
            op.drop_column('notifications', 'priority')
        
        if 'read_at' in columns:
            op.drop_column('notifications', 'read_at')
    
    # 2. Don't recreate indexes that were never dropped
    
    # 3. Drop notification_settings table if it exists
    if inspector.has_table('notification_settings'):
        op.drop_table('notification_settings')