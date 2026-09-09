from __future__ import annotations

import sys

from werkzeug.security import generate_password_hash

from .config import settings
from .extensions import db
from .models import AdminUser


def bootstrap(app) -> None:
    with app.app_context():
        db.create_all()
        user = AdminUser.query.filter_by(username=settings.admin_username).first()
        if not user:
            user = AdminUser(
                username=settings.admin_username,
                password_hash=generate_password_hash(settings.admin_password),
                enabled=True,
            )
            db.session.add(user)
            db.session.commit()


def main() -> None:
    from . import create_app

    if settings.app_env == "production" and settings.admin_username == "admin" and settings.admin_password == "admin123":
        print("ERROR: default admin credentials are not allowed in production.", file=sys.stderr)
        raise SystemExit(2)
    app = create_app()
    bootstrap(app)
    print("SemanticFit database initialized.")


if __name__ == "__main__":
    main()
