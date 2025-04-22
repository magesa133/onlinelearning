"""Update question model to use JSON options and fix constraints

Revision ID: 6d64b52d1a43
Revises: 5dfb6c80e614
Create Date: 2025-04-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '6d64b52d1a43'
down_revision = '5dfb6c80e614'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # First handle the quizzes table changes
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        # Get all foreign keys for the quizzes table
        fks = inspector.get_foreign_keys('quizzes')
        fk_to_drop = None
        
        # Find the foreign key that references teachers.id
        for fk in fks:
            if fk['referred_table'] == 'teachers' and 'teacher_id' in fk['constrained_columns']:
                fk_to_drop = fk
                break
        
        # If we found the foreign key, drop it first
        if fk_to_drop and fk_to_drop.get('name'):
            batch_op.drop_constraint(fk_to_drop['name'], type_='foreignkey')

        # Now safely drop the index if it exists
        indexes = inspector.get_indexes('quizzes')
        index_to_drop = None
        
        for index in indexes:
            if index['name'] == 'ix_quiz_teacher_id' or \
               (index['column_names'] == ['teacher_id'] and not index['unique']):
                index_to_drop = index
                break
        
        if index_to_drop and index_to_drop.get('name'):
            batch_op.drop_index(index_to_drop['name'])

    # Then handle the questions table changes
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('options',
            type_=sa.JSON(),
            existing_type=sa.Text()
        )


def downgrade():
    # First revert questions table changes
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('options',
            type_=sa.Text(),
            existing_type=sa.JSON()
        )

    # Then recreate quizzes table indexes and constraints
    with op.batch_alter_table('quizzes', schema=None) as batch_op:
        batch_op.create_index('ix_quiz_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_quizzes_teacher_id_teachers',
            'teachers',
            ['teacher_id'],
            ['id']
        )