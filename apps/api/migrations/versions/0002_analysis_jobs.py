"""Durable analysis queue.

Revision ID: 0002_analysis_jobs
Revises: 0001_initial
"""
from alembic import op
from datatalk.models import AnalysisJob

revision = "0002_analysis_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    AnalysisJob.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    AnalysisJob.__table__.drop(bind=op.get_bind(), checkfirst=True)
