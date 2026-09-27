"""make_email_globally_unique

Revision ID: 3f8a9e1b2c4d
Revises: 0e674447729b
Create Date: 2026-09-25 11:40:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f8a9e1b2c4d'
down_revision: Union[str, None] = '0e674447729b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Deduplicate any existing duplicate emails before applying unique constraint
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        # Remove duplicate users keeping the latest created record per email
        conn.execute(sa.text("""
            DELETE FROM users
            WHERE id NOT IN (
                SELECT DISTINCT ON (email) id
                FROM users
                ORDER BY email, created_at DESC
            );
        """))

    # 2. Apply table alterations using batch_alter_table for SQLite & Postgres compatibility
    with op.batch_alter_table('users', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('uq_users_org_email', type_='unique')
        except Exception:
            pass
        batch_op.create_unique_constraint('uq_users_email', ['email'])
        batch_op.alter_column('hashed_password',
                              existing_type=sa.String(length=255),
                              nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET hashed_password = 'OAUTH_USER_PLACEHOLDER' WHERE hashed_password IS NULL;"))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('hashed_password',
                              existing_type=sa.String(length=255),
                              nullable=False)
        try:
            batch_op.drop_constraint('uq_users_email', type_='unique')
        except Exception:
            pass
        batch_op.create_unique_constraint('uq_users_org_email', ['organization_id', 'email'])
