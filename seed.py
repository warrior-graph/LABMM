"""
Seed script: creates the first super-admin account.
Run once after `flask db upgrade`:

    python seed.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from labhive import create_app
from labhive.extensions import db
from labhive.models.member import Member


def seed():
    app = create_app()
    with app.app_context():
        email = os.environ.get("ADMIN_EMAIL", "admin@labhive.local").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "changeme")
        first_name = os.environ.get("ADMIN_FIRST_NAME", "Admin")
        last_name = os.environ.get("ADMIN_LAST_NAME", "User")

        if Member.query.filter_by(email=email).first():
            print(f"Admin account already exists ({email}) — skipping.")
            return

        admin = Member(
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_super_admin=True,
            is_approved=True,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Super-admin created: {email}")


if __name__ == "__main__":
    seed()
