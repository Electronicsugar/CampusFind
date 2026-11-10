"""Operator-only enrollment after offline campus identity verification."""
import argparse,getpass
from types import SimpleNamespace
from backend.auth import Registration,hash_password
from backend.database import configure
from backend.models import User,ModerationRecord


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('email');parser.add_argument('--name',required=True);args=parser.parse_args()
    password=getpass.getpass('Password (enter privately; never pass on command line): ')
    if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
    data=Registration(email=args.email,display_name=args.name,password=password)
    app=SimpleNamespace(state=SimpleNamespace());configure(app)
    if not app.state.sessions:raise SystemExit('Configure PostgreSQL first.')
    try:
        with app.state.sessions.begin() as db:
            user=User(email=data.email,display_name=data.display_name,password_hash=hash_password(data.password))
            db.add(user);db.flush();db.add(ModerationRecord(actor_id=user.id,action='operator_enrolled_pilot_account'))
        print('Student account created. Deliver access privately after verifying campus identity.')
    except Exception:raise SystemExit('Account could not be created; check for a duplicate email or database error. No existing account was changed.') from None
    finally:app.state.engine.dispose()
