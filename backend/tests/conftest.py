import os

os.environ.setdefault("EMBEDDING_BACKEND", "hash")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("RERANKER_ENABLED", "false")
os.environ.setdefault("AUDIT_ENABLED", "false")

import pytest

from app import create_app
from app.bootstrap import bootstrap
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "SECRET_KEY": "test-secret",
        }
    )
    bootstrap(flask_app)
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
