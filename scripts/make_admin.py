"""Local operator-only role assignment; no registration/admin bootstrap endpoint."""
import argparse
from types import SimpleNamespace
from sqlalchemy import select,delete
from backend.database import configure
from backend.models import User,Session,ModerationRecord

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('email');args=parser.parse_args()
    app=SimpleNamespace(state=SimpleNamespace());configure(app)
    if not app.state.sessions:raise SystemExit('Configure the database first.')
    with app.state.sessions.begin() as db:
        user=db.scalar(select(User).where(User.email==args.email.strip().lower()).with_for_update())
        if not user:raise SystemExit('Register this account through the app first.')
        user.role='admin';db.execute(delete(Session).where(Session.user_id==user.id))
        db.add(ModerationRecord(actor_id=user.id,action='operator_admin_promotion',detail='Role assigned by local operator command; sessions revoked.'))
    print('Administrator role assigned. Log in again.')
