"""Persist Google's immutable subject rather than using email as identity.

Revision ID: b17006a91f42
Revises: 62243260b0ef
"""
from alembic import op
import sqlalchemy as sa

revision = "b17006a91f42"
down_revision = "62243260b0ef"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("google_subject", sa.String(255), nullable=True))
    op.create_index("uq_users_google_subject", "users", ["google_subject"], unique=True)


def downgrade():
    op.drop_index("uq_users_google_subject", table_name="users")
    op.drop_column("users", "google_subject")
