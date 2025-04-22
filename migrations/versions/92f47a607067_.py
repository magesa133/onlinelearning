"""Add updated_at and fix foreign keys in quiz_answers

Revision ID: 92f47a607067
Revises: 0f817d12222d
Create Date: 2025-04-20 21:48:13.037929

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import text
import logging

# revision identifiers, used by Alembic.
revision = '92f47a607067'
down_revision = '0f817d12222d'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    is_mysql = conn.engine.name == 'mysql'
    
    try:
        # 1. Add updated_at column if it doesn't exist
        if 'updated_at' not in [col['name'] for col in inspector.get_columns('quiz_answers')]:
            logger.info("Adding updated_at column to quiz_answers")
            op.add_column(
                'quiz_answers',
                sa.Column('updated_at', 
                         sa.DateTime(timezone=True),
                         server_default=sa.func.now(),
                         nullable=True)
            )

        # 2. Handle orphaned records before adding constraints
        logger.info("Checking for orphaned quiz_answer records")
        
        # Find all question_ids in quiz_answers that don't exist in questions
        result = conn.execute(text("""
            SELECT DISTINCT qa.question_id 
            FROM quiz_answers qa
            LEFT JOIN questions q ON qa.question_id = q.id
            WHERE q.id IS NULL
        """))
        orphaned_question_ids = [row[0] for row in result]
        
        if orphaned_question_ids:
            logger.warning(f"Found {len(orphaned_question_ids)} orphaned records")
            
            # MySQL-compatible way to handle parameterized IN clause
            if is_mysql:
                # For MySQL, we need to format the IDs directly into the query
                id_list = ",".join(str(id) for id in orphaned_question_ids)
                conn.execute(text(f"""
                    DELETE FROM quiz_answers
                    WHERE question_id IN ({id_list})
                """))
            else:
                # For other databases, use normal parameterized query
                conn.execute(text("""
                    DELETE FROM quiz_answers
                    WHERE question_id = ANY(:question_ids)
                """), {'question_ids': orphaned_question_ids})

        # 3. Process foreign key changes
        with op.batch_alter_table('quiz_answers') as batch_op:
            if is_mysql:
                batch_op.execute('SET FOREIGN_KEY_CHECKS=0')
                logger.info("Disabled foreign key checks for MySQL")

            try:
                # Get current constraints
                constraints = inspector.get_foreign_keys('quiz_answers')
                
                # Drop existing foreign keys to questions
                for fk in constraints:
                    if fk['referred_table'] == 'questions':
                        logger.info(f"Dropping foreign key: {fk['name']}")
                        batch_op.drop_constraint(fk['name'], type_='foreignkey')

                # Create new foreign key with CASCADE
                logger.info("Creating new foreign key with CASCADE")
                batch_op.create_foreign_key(
                    'fk_quiz_answers_question_new',
                    'questions',
                    ['question_id'],
                    ['id'],
                    ondelete='CASCADE'
                )

            except Exception as e:
                logger.error(f"Error during batch alter: {str(e)}")
                raise
            finally:
                if is_mysql:
                    batch_op.execute('SET FOREIGN_KEY_CHECKS=1')
                    logger.info("Re-enabled foreign key checks")

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise

def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    is_mysql = conn.engine.name == 'mysql'

    try:
        with op.batch_alter_table('quiz_answers') as batch_op:
            if is_mysql:
                batch_op.execute('SET FOREIGN_KEY_CHECKS=0')

            try:
                # Drop new foreign key if it exists
                constraints = inspector.get_foreign_keys('quiz_answers')
                for fk in constraints:
                    if fk['name'] == 'fk_quiz_answers_question_new':
                        logger.info(f"Dropping foreign key: {fk['name']}")
                        batch_op.drop_constraint(fk['name'], type_='foreignkey')

                # Recreate original foreign key
                logger.info("Recreating original foreign key")
                batch_op.create_foreign_key(
                    'quiz_answers_ibfk_2',
                    'questions',
                    ['question_id'],
                    ['id']
                )

                # Remove updated_at column if exists
                if 'updated_at' in [col['name'] for col in inspector.get_columns('quiz_answers')]:
                    logger.info("Dropping updated_at column")
                    batch_op.drop_column('updated_at')

            except Exception as e:
                logger.error(f"Error during downgrade batch alter: {str(e)}")
                raise
            finally:
                if is_mysql:
                    batch_op.execute('SET FOREIGN_KEY_CHECKS=1')

    except Exception as e:
        logger.error(f"Downgrade failed: {str(e)}")
        raise