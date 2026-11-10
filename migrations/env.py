from alembic import context
from sqlalchemy import create_engine,pool
from backend.models import Base
from backend.settings import Settings

config=context.config
url=config.get_main_option('sqlalchemy.url') or Settings.from_env().database_url
if not url:raise RuntimeError('DATABASE_URL is required for migrations.')
if context.is_offline_mode():
    context.configure(url=url,target_metadata=Base.metadata,literal_binds=True,compare_type=True)
    with context.begin_transaction():context.run_migrations()
else:
    engine=create_engine(url,poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()
