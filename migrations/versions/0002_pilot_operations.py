"""Durable private-file deletion and worker health."""
from alembic import op
import sqlalchemy as sa
revision='0002_pilot_operations'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('file_deletions',sa.Column('storage_key',sa.String(80),primary_key=True),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_table('worker_state',sa.Column('name',sa.String(40),primary_key=True),sa.Column('heartbeat',sa.DateTime(),nullable=False),sa.Column('status',sa.String(16),nullable=False))

def downgrade():
    op.drop_table('worker_state');op.drop_table('file_deletions')
