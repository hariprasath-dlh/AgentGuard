"""restrict_user_fk_on_hitl_requests

Revision ID: 4a7b2c9d1e3f
Revises: 3f8a9e1b2c4d
Create Date: 2026-09-26 15:45:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a7b2c9d1e3f'
down_revision: Union[str, None] = '3f8a9e1b2c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        conn.execute(sa.text("""
            ALTER TABLE hitl_requests DROP CONSTRAINT IF EXISTS hitl_requests_reviewer_id_fkey;
            ALTER TABLE hitl_requests ADD CONSTRAINT hitl_requests_reviewer_id_fkey
                FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE RESTRICT;
        """))
    else:
        # For SQLite, batch_alter_table rebuilds table with updated foreign key
        with op.batch_alter_table('hitl_requests', schema=None, recreate='always') as batch_op:
            batch_op.create_foreign_key('hitl_requests_reviewer_id_fkey', 'users', ['reviewer_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        conn.execute(sa.text("""
            ALTER TABLE hitl_requests DROP CONSTRAINT IF EXISTS hitl_requests_reviewer_id_fkey;
            ALTER TABLE hitl_requests ADD CONSTRAINT hitl_requests_reviewer_id_fkey
                FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL;
        """))
    else:
        with op.batch_alter_table('hitl_requests', schema=None, recreate='always') as batch_op:
            batch_op.create_foreign_key('hitl_requests_reviewer_id_fkey', 'users', ['reviewer_id'], ['id'], ondelete='SET NULL')
