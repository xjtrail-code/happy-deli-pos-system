import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import User, create_app, db


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        database = Path(self.tmp.name) / "test.db"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
        })
        with self.app.app_context():
            db.create_all()
            db.session.add_all([
                User(username="owner", password_hash=generate_password_hash("owner-pass"), role="admin"),
                User(username="cashier", password_hash=generate_password_hash("cashier-pass"), role="cashier"),
                User(username="disabled", password_hash=generate_password_hash("disabled-pass"), role="cashier", is_active=False),
            ])
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, username, password):
        self.client.get("/")
        with self.client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        return self.client.post("/", data={"username": username, "password": password, "csrf_token": csrf})

    def test_admin_login_and_logout(self):
        self.assertEqual(self.client.get("/admin-dashboard").status_code, 302)
        self.assertEqual(self.login("owner", "owner-pass").location, "/admin-dashboard")
        self.assertEqual(self.client.get("/admin-dashboard").status_code, 200)
        with self.client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        self.assertEqual(self.client.post("/logout", data={"csrf_token": csrf}).status_code, 302)
        self.assertEqual(self.client.get("/admin-dashboard").status_code, 302)

    def test_cashier_cannot_open_admin_routes(self):
        self.assertEqual(self.login("cashier", "cashier-pass").location, "/pos")
        self.assertEqual(self.client.get("/pos").status_code, 200)
        self.assertEqual(self.client.get("/admin-dashboard").status_code, 403)
        self.assertEqual(self.client.get("/product-entry").status_code, 403)

    def test_invalid_and_inactive_accounts_do_not_start_sessions(self):
        for username, password in [("owner", "wrong"), ("missing", "x"), ("disabled", "disabled-pass")]:
            response = self.login(username, password)
            self.assertIn(b"Invalid username or password", response.data)
            self.assertEqual(self.client.get("/pos").status_code, 302)

    def test_login_and_logout_reject_missing_csrf(self):
        self.assertEqual(self.client.post("/", data={"username": "owner", "password": "owner-pass"}).status_code, 400)
        self.login("owner", "owner-pass")
        self.assertEqual(self.client.post("/logout").status_code, 400)
        self.assertEqual(self.client.get("/admin-dashboard").status_code, 200)


if __name__ == "__main__":
    unittest.main()
