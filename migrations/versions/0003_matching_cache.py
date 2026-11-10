"""Cache exact appearance descriptors and batch-friendly read indexes."""
from alembic import op
import sqlalchemy as sa
revision='0003_matching_cache'
down_revision='0002_pilot_operations'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('item_images',sa.Column('cache_signature',sa.String(64),nullable=True))
    op.add_column('item_images',sa.Column('appearance',sa.JSON(),nullable=True))
    op.create_index('ix_match_jobs_pending','match_jobs',['status','updated_at'])
    op.create_index('ix_notifications_recipient_order','notifications',['user_id','created_at','id'])
    op.create_index('ix_items_owner_order','items',['owner_id','created_at','id'])

def downgrade():
    op.drop_index('ix_items_owner_order',table_name='items')
    op.drop_index('ix_notifications_recipient_order',table_name='notifications')
    op.drop_index('ix_match_jobs_pending',table_name='match_jobs')
    op.drop_column('item_images','appearance');op.drop_column('item_images','cache_signature')
