from unittest.mock import patch
import test_auth
from app import app, db, User, password_reset_serializer, password_fingerprint


class PasswordResetTests(test_auth.AuthenticationTests):
    def setUp(self):
        super().setUp()
        self.original_config = {key: app.config[key] for key in
            ('SMTP_HOST', 'SMTP_FROM', 'APP_BASE_URL', 'SMTP_SSL', 'SMTP_USERNAME', 'SMTP_PASSWORD')}
        app.config.update(SMTP_HOST='smtp.example.com', SMTP_FROM='pos@example.com',
                          APP_BASE_URL='https://pos.example.com', SMTP_SSL=False,
                          SMTP_USERNAME='mailer', SMTP_PASSWORD='test-mail-password')
        self.addCleanup(app.config.update, self.original_config)

    def reset_token(self):
        user = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        return password_reset_serializer().dumps(dict(user_id=user.id,
            password=password_fingerprint(user), email=user.email))

    def test_email_delivery_and_unknown_accounts(self):
        with patch('app.smtplib.SMTP') as smtp:
            response = self.client.post('/forgot-password', data={
                'email': ' CASHIER@example.com ', 'csrf_token': self.token()}, follow_redirects=True)
            self.assertIn(b'If an active account matches', response.data)
            connection = smtp.return_value.__enter__.return_value
            connection.starttls.assert_called_once()
            connection.login.assert_called_once_with('mailer', 'test-mail-password')
            message = connection.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'cashier@example.com')
            self.assertIn('https://pos.example.com/reset-password/', message.get_content())
            smtp.reset_mock()
            for email in ('unknown@example.com', 'admin@example.com'):
                if email.startswith('admin'):
                    admin = db.session.scalar(db.select(User).where(User.username == 'admin'))
                    admin.isActive = False
                    db.session.commit()
                response = self.client.post('/forgot-password', data={
                    'email': email, 'csrf_token': self.token()}, follow_redirects=True)
                self.assertIn(b'If an active account matches', response.data)
                smtp.assert_not_called()

    def test_reset_validation_single_use_and_login(self):
        route = '/reset-password/' + self.reset_token()
        self.assertEqual(self.client.get(route).status_code, 200)
        for password, confirmation in [('short', 'short'), ('new-password-123', 'different')]:
            response = self.client.post(route, data={'password': password,
                'confirm_password': confirmation, 'csrf_token': self.token()})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(route, data={}).status_code, 400)
        response = self.client.post(route, data={'password': 'new-password-123',
            'confirm_password': 'new-password-123', 'csrf_token': self.token()})
        self.assertEqual(response.location, '/')
        self.assertEqual(self.client.get(route).status_code, 400)
        self.assertEqual(self.client.post(route, data={'password': 'another-password-123',
            'confirm_password': 'another-password-123', 'csrf_token': self.token()}).status_code, 400)
        self.assertEqual(self.login('cashier', 'long-test-password').status_code, 401)
        self.assertEqual(self.login('cashier', 'new-password-123').location, '/pos')

    def test_expired_tampered_and_disabled_tokens(self):
        import time
        with patch('itsdangerous.timed.time.time', return_value=time.time() - 1900):
            expired = self.reset_token()
        self.assertEqual(self.client.get('/reset-password/' + expired).status_code, 400)
        token = self.reset_token()
        self.assertEqual(self.client.get('/reset-password/' + token + 'tampered').status_code, 400)
        user = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        user.isActive = False
        db.session.commit()
        self.assertEqual(self.client.get('/reset-password/' + token).status_code, 400)

    def test_missing_configuration_and_delivery_failure(self):
        self.assertEqual(self.client.post('/forgot-password', data={}).status_code, 400)
        app.config['SMTP_HOST'] = ''
        self.assertEqual(self.client.post('/forgot-password', data={
            'email': 'cashier@example.com', 'csrf_token': self.token()}).status_code, 503)
        app.config['SMTP_HOST'] = 'smtp.example.com'
        with patch('app.smtplib.SMTP', side_effect=OSError('unavailable')):
            response = self.client.post('/forgot-password', data={
                'email': 'cashier@example.com', 'csrf_token': self.token()}, follow_redirects=True)
            self.assertIn(b'If an active account matches', response.data)
