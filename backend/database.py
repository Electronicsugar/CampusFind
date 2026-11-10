from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException,Request
from backend.settings import Settings


def configure(app,settings=None):
    settings=settings or Settings.from_env();app.state.settings=settings
    if not settings.database_url:
        app.state.sessions=None;return
    if not settings.database_url.startswith('postgresql+psycopg://') and not (settings.testing and settings.database_url.startswith('sqlite')):
        raise ValueError('Use PostgreSQL with psycopg. SQLite is only allowed in automated tests.')
    kwargs={'pool_pre_ping':True}
    if settings.database_url.startswith('sqlite'):
        kwargs['connect_args']={'check_same_thread':False}
    else:
        kwargs['connect_args']={'connect_timeout':5}
    engine=create_engine(settings.database_url,**kwargs)
    if engine.dialect.name=='postgresql':
        @event.listens_for(engine,'connect')
        def timeouts(connection,_):
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SET statement_timeout = '30s'")
            connection.commit()
    if settings.database_url.startswith('sqlite'):
        @event.listens_for(engine,'connect')
        def foreign_keys(connection,_):connection.execute('PRAGMA foreign_keys=ON')
    app.state.engine=engine
    app.state.sessions=sessionmaker(engine,expire_on_commit=False)


def get_db(request:Request):
    factory=getattr(request.app.state,'sessions',None)
    if not factory:raise HTTPException(503,'Database is not configured. Follow the local setup guide.')
    with factory() as db:
        try:
            if request.method not in {'GET','HEAD','OPTIONS'}:maintenance_guard(db)
            yield db
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503,'Database operation unavailable. Please try again.') from None
        except Exception:
            db.rollback();raise


def maintenance_guard(db):
    """Backups take the exclusive counterpart; file mutations take shared locks."""
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock_shared(72439107)'))
