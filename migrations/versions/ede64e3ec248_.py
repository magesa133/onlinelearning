"""Optimize message indexes and add notifications table

Revision ID: ede64e3ec248
Revises: 90f32d9e867b
Create Date: 2025-04-24 01:50:08.525825

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers
revision = 'ede64e3ec248'
down_revision = '90f32d9e867b'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # 1. Create notifications table if it doesn't exist
    if 'notifications' not in inspector.get_table_names():
        op.create_table('notifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('message', sa.String(length=255), nullable=False),
            sa.Column('link', sa.String(length=255), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
    
    # 2. Get foreign key constraints
    fk_constraints = inspector.get_foreign_keys('messages')
    fk_columns = set()
    for fk in fk_constraints:
        fk_columns.update(fk['constrained_columns'])
    
    # 3. Get current indexes
    existing_indexes = {i['name']: i for i in inspector.get_indexes('messages')}
    
    # 4. Apply index changes safely
    with op.batch_alter_table('messages', schema=None) as batch_op:
        # Create new indexes
        if 'idx_message_classroom_created' not in existing_indexes:
            batch_op.create_index('idx_message_classroom_created', 
                               ['classroom_id', 'created_at'], 
                               unique=False)
        
        if 'idx_message_sender_recipient_read' not in existing_indexes:
            batch_op.create_index('idx_message_sender_recipient_read',
                               ['sender_id', 'recipient_id', 'is_read'],
                               unique=False)
        
        # Only drop indexes that:
        # 1. Exist
        # 2. Aren't on columns used in foreign keys
        # 3. Aren't primary/unique constraints
        
        # For idx_message_sender
        if 'idx_message_sender' in existing_indexes:
            idx = existing_indexes['idx_message_sender']
            if (not idx.get('unique', False) and \
               ('sender_id' not in fk_columns)):
                batch_op.drop_index('idx_message_sender')
        
        # For idx_message_recipient - skip dropping since it's used by FK
        # Just leave it in place if it exists

def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_indexes = {i['name']: i for i in inspector.get_indexes('messages')}
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        # Recreate old indexes if they don't exist
        if 'idx_message_sender' not in existing_indexes:
            batch_op.create_index('idx_message_sender', ['sender_id'], unique=False)
        
        if 'idx_message_recipient' not in existing_indexes:
            batch_op.create_index('idx_message_recipient', ['recipient_id'], unique=False)
        
        # Drop new indexes if they exist
        if 'idx_message_sender_recipient_read' in existing_indexes:
            batch_op.drop_index('idx_message_sender_recipient_read')
        
        if 'idx_message_classroom_created' in existing_indexes:
            batch_op.drop_index('idx_message_classroom_created')
    
    # Drop notifications table if it exists
    if 'notifications' in inspector.get_table_names():
        op.drop_table('notifications')