"""Run `python -m app.cli promote EMAIL` or `python -m app.cli cleanup-sessions`."""

import argparse
import time

from sqlalchemy import delete, select

from app.database.session import SessionLocal
from app.models import RefreshSession, User


def main():
    parser = argparse.ArgumentParser(description="Local administrator utilities")
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote", help="Promote an existing registered user")
    promote.add_argument("email")
    commands.add_parser("cleanup-sessions", help="Delete expired refresh session records")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "promote":
            user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
            if user is None:
                raise SystemExit("User not found; register this account first.")
            user.is_superuser = True
        else:
            db.execute(delete(RefreshSession).where(RefreshSession.expires_at <= int(time.time())))
        db.commit()
    print("Done.")


if __name__ == "__main__":
    main()
