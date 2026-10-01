import os
import unittest

# Use an isolated database; never modify development accounts.
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'test-only-key'

from app import User, app, db
from werkzeug.security import check_password_hash, generate_password_hash


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.context = app.app_context()
        self.context.push()
        db.create_all()
        for role in ('admin', 'cashier'):
            db.session.add(User(username=role, role=role,
                                password_hash=generate_password_hash('long-test-password')))
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def token(self):
        self.client.get('/')
        with self.client.session_transaction() as session:
            return session['csrf_token']

    def login(self, username, password='long-test-password'):
        return self.client.post('/', data=dict(username=username, password=password,
                                              csrf_token=self.token()))

    def test_anonymous_routes_require_login(self):
        for route in ('/pos', '/admin-dashboard', '/product-entry'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/')

    def test_invalid_login_and_missing_csrf(self):
        self.assertEqual(self.client.post('/', data={'username': 'admin'}).status_code, 400)
        for username in ('admin', 'unknown'):
            response = self.login(username, 'wrong')
            self.assertEqual(response.status_code, 401)
            self.assertIn(b'Invalid username or password.', response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)

    def test_admin_access_and_logout(self):
        old_token = self.token()
        self.assertEqual(self.login(' ADMIN ').location, '/admin-dashboard')
        for route in ('/admin-dashboard', '/pos', '/product-entry'):
            self.assertEqual(self.client.get(route).status_code, 200)
        with self.client.session_transaction() as session:
            new_token = session['csrf_token']
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.post('/logout').status_code, 400)
        self.assertEqual(self.client.post('/logout', data={'csrf_token': new_token}).status_code, 302)
        self.assertEqual(self.client.get('/pos').location, '/')

    def test_cashier_cannot_access_admin_routes(self):
        self.assertEqual(self.login('cashier').location, '/pos')
        response = self.client.get('/pos')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'Back to Dashboard', response.data)
        for route in ('/admin-dashboard', '/product-entry'):
            self.assertEqual(self.client.get(route).status_code, 403)
        with self.client.session_transaction() as session:
            token = session['csrf_token']
        self.assertEqual(self.client.post('/product-entry', data={'csrf_token': token}).status_code, 403)

    def test_deleted_account_loses_access(self):
        self.login('cashier')
        user = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        db.session.delete(user)
        db.session.commit()
        self.assertEqual(self.client.get('/pos').location, '/')

    def test_create_user_command(self):
        runner = app.test_cli_runner()
        result = runner.invoke(args=['create-user', 'NewUser', '--role', 'cashier'],
                               input='another-long-password\nanother-long-password\n')
        self.assertEqual(result.exit_code, 0, result.output)
        user = db.session.scalar(db.select(User).where(User.username == 'newuser'))
        self.assertNotEqual(user.password_hash, 'another-long-password')
        self.assertTrue(check_password_hash(user.password_hash, 'another-long-password'))
        duplicate = runner.invoke(args=['create-user', 'newuser'],
                                  input='another-long-password\nanother-long-password\n')
        self.assertNotEqual(duplicate.exit_code, 0)
        short = runner.invoke(args=['create-user', 'short'], input='short\nshort\n')
        self.assertNotEqual(short.exit_code, 0)


if __name__ == '__main__':
    unittest.main()
