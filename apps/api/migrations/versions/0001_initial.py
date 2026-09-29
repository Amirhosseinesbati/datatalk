"""Initial workspace-scoped DataTalk schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
from datatalk.database import Base
import datatalk.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
