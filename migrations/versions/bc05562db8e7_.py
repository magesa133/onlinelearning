from alembic import op
import sqlalchemy as sa
import sqlalchemy.engine.reflection as reflection


# revision identifiers, used by Alembic.
revision = 'bc05562db8e7'
down_revision = 'c92821c66fec'
branch_labels = None
depends_on = None


def upgrade():
    # Connect to the database
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)

    # Get existing columns in 'enrollments' table
    columns = [col['name'] for col in inspector.get_columns('enrollments')]

    # Only add the column if it does not already exist
    if 'is_dropped' not in columns:
        with op.batch_alter_table('enrollments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_dropped', sa.Boolean(), nullable=True))

    # Drop foreign key constraint before dropping the index
        with op.batch_alter_table('students', schema=None) as batch_op:
            batch_op.drop_constraint('fk_students_department_id', type_='foreignkey')
  # Update with actual FK name
            batch_op.drop_index('idx_student_department')


def downgrade():
    # Restore the previous state
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.create_index('idx_student_department', ['department_id'], unique=False)
        batch_op.create_foreign_key('fk_students_department_id', 'departments', ['department_id'], ['id'])  # Adjust accordingly

    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.drop_column('is_dropped')
