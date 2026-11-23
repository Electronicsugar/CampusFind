"""Store hashed, single-use account recovery codes."""
from alembic import op
import sqlalchemy as sa

revision='0004_account_recovery'
down_revision='0003_matching_cache'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('recovery_codes',
        sa.Column('code_hash',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_recovery_codes_user_id','recovery_codes',['user_id'])


def downgrade():
    op.drop_index('ix_recovery_codes_user_id',table_name='recovery_codes')
    op.drop_table('recovery_codes')
