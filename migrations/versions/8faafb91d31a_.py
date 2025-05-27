"""empty message

Revision ID: 8faafb91d31a
Revises: 187de8d09ae2
Create Date: 2025-05-24 03:36:50.721011

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers must be set!
revision = '8faafb91d31a'
down_revision = '187de8d09ae2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Skip if messages table doesn't exist
    if not inspector.has_table('messages'):
        return
    
    # Get all foreign key constraints
    fk_constraints = inspector.get_foreign_keys('messages')
    
    # Check which indexes are needed for FKs
    classroom_index_needed = any(
        'classroom_id' in fk['constrained_columns'] 
        for fk in fk_constraints
    )
    
    sender_recipient_index_needed = any(
        all(col in fk['constrained_columns'] 
            for col in ['sender_id', 'recipient_id'])
        for fk in fk_constraints
    )
    
    # Only drop indexes that aren't needed for FKs
    with op.batch_alter_table('messages', schema=None) as batch_op:
        if not classroom_index_needed and 'idx_message_classroom_created' in [i['name'] for i in inspector.get_indexes('messages')]:
            batch_op.drop_index('idx_message_classroom_created')
        
        if not sender_recipient_index_needed and 'idx_message_sender_recipient_read' in [i['name'] for i in inspector.get_indexes('messages')]:
            batch_op.drop_index('idx_message_sender_recipient_read')


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if not inspector.has_table('messages'):
        return
    
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('messages')]
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        if 'idx_message_sender_recipient_read' not in existing_indexes:
            batch_op.create_index(
                'idx_message_sender_recipient_read', 
                ['sender_id', 'recipient_id', 'is_read'], 
                unique=False
            )
        
        if 'idx_message_classroom_created' not in existing_indexes:
            batch_op.create_index(
                'idx_message_classroom_created', 
                ['classroom_id', 'created_at'], 
                unique=False
            )