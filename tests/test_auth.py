import os
import json
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
        self.client.get('/', follow_redirects=True)
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

    def test_init_db_repairs_missing_tables_and_preserves_accounts(self):
        from app import Product, Sale

        Sale.__table__.drop(db.engine)
        Product.__table__.drop(db.engine)
        result = app.test_cli_runner().invoke(args=['init-db'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.login('admin').location, '/admin-dashboard')
        self.assertEqual(self.client.get('/admin-dashboard').status_code, 200)
        self.assertEqual(self.client.get('/inventory').status_code, 200)

    def test_sale_history_preserves_checkout_details(self):
        from app import Product, Sale

        product = Product(barcode='123', name='Milk', price=3.50, quantity=10)
        db.session.add(product)
        db.session.commit()
        self.login('admin')
        response = self.client.post('/complete-sale', data={
            'csrf_token': self.token(), 'payment_method': 'cash',
            'cart': json.dumps([{'barcode': '123', 'quantity': 2}]),
        })
        self.assertEqual(response.status_code, 200)
        sale = db.session.get(Sale, response.json['sale_id'])
        self.assertEqual(sale.total, 7.44)
        self.assertEqual(sale.items[0].quantity, 2)
        self.assertEqual(product.quantity, 8)
        product.name = 'Renamed product'
        product.price = 9.99
        db.session.commit()
        db.session.delete(product)
        db.session.commit()
        response = self.client.get('/sales-history')
        self.assertEqual(response.status_code, 200)
        for text in (b'Milk', b'$3.50', b'$7.00', b'$7.44',
                     sale.created_at.strftime('%m/%d/%Y').encode()):
            self.assertIn(text, response.data)
        self.assertNotIn(b'Renamed product', response.data)

    def test_sales_history_empty_legacy_and_permissions(self):
        from app import Sale

        self.assertEqual(self.client.get('/sales-history').status_code, 302)
        self.login('cashier')
        self.assertEqual(self.client.get('/sales-history').status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.login('admin')
        self.assertIn(b'No completed transactions yet', self.client.get('/sales-history').data)
        db.session.add(Sale(total=5.00, payment_method='card'))
        db.session.commit()
        response = self.client.get('/sales-history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Item details were not recorded', response.data)
        self.assertIn(b'$5.00', response.data)

    def test_daily_total_includes_whole_day_across_pages(self):
        from datetime import date, datetime, timedelta
        from app import Sale

        start = datetime.combine(date.today(), datetime.min.time())
        db.session.add_all([
            Sale(total=2.50, payment_method='cash', created_at=start)
            for _ in range(21)
        ] + [
            Sale(total=5, payment_method='card', created_at=start + timedelta(days=1, microseconds=-1)),
            Sale(total=100, payment_method='cash', created_at=start - timedelta(microseconds=1)),
            Sale(total=200, payment_method='card', created_at=start + timedelta(days=1)),
        ])
        db.session.commit()
        self.login('admin')
        for page in (1, 2):
            response = self.client.get(f'/sales-history?page={page}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'$57.50', response.data)
            self.assertIn(b'22 completed transactions', response.data)

    def test_daily_total_without_sales(self):
        self.login('admin')
        response = self.client.get('/sales-history')
        self.assertIn(b'$0.00', response.data)
        self.assertIn(b'0 completed transactions', response.data)

    def test_failed_checkout_does_not_save_partial_history(self):
        from app import Product, Sale, SaleItem

        db.session.add(Product(barcode='123', name='Milk', price=3.50, quantity=10))
        db.session.commit()
        self.login('admin')
        response = self.client.post('/complete-sale', data={
            'csrf_token': self.token(), 'payment_method': 'cash',
            'cart': json.dumps([{'barcode': '123', 'quantity': 2},
                                {'barcode': 'missing', 'quantity': 1}]),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.session.scalar(db.select(db.func.count(Sale.id))), 0)
        self.assertEqual(db.session.scalar(db.select(db.func.count(SaleItem.id))), 0)
        self.assertEqual(db.session.scalar(db.select(Product)).quantity, 10)


if __name__ == '__main__':
    unittest.main()
