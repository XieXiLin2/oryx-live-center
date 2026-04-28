"""Add transcode tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create transcode_nodes table
    op.create_table(
        'transcode_nodes',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('region', sa.String(50), nullable=False),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('status', sa.String(50)),
        sa.Column('max_tasks', sa.Integer, default=4),
        sa.Column('current_tasks', sa.Integer, default=0),
        sa.Column('cpu_usage', sa.Float),
        sa.Column('memory_usage', sa.Float),
        sa.Column('gpu_usage', sa.Float),
        sa.Column('network_latency', sa.Integer),
        sa.Column('last_heartbeat', sa.DateTime),
        sa.Column('capabilities', sa.JSON),
    )

    # Create transcode_profiles table
    op.create_table(
        'transcode_profiles',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('source_protocol', sa.String(50)),
        sa.Column('outputs', sa.JSON),
        sa.Column('latency_mode', sa.String(50)),
        sa.Column('created_at', sa.DateTime),
    )

    # Create transcode_tasks table
    op.create_table(
        'transcode_tasks',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('stream_name', sa.String(255), nullable=False),
        sa.Column('profile_id', sa.Integer, nullable=False),
        sa.Column('node_id', sa.String(255)),
        sa.Column('source_protocol', sa.String(50)),
        sa.Column('source_url', sa.String(512)),
        sa.Column('outputs', sa.JSON),
        sa.Column('status', sa.String(50)),
        sa.Column('started_at', sa.DateTime),
        sa.Column('stopped_at', sa.DateTime),
        sa.Column('error_message', sa.Text),
        sa.Column('metrics', sa.JSON),
        sa.ForeignKeyConstraint(['profile_id'], ['transcode_profiles.id']),
        sa.ForeignKeyConstraint(['node_id'], ['transcode_nodes.id']),
    )


def downgrade() -> None:
    op.drop_table('transcode_tasks')
    op.drop_table('transcode_profiles')
    op.drop_table('transcode_nodes')
