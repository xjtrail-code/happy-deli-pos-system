import test_auth
from app import User, app, db
from models import PERMISSIONS
from werkzeug.security import check_password_hash


class EmployeeManagementTests(test_auth.AuthenticationTests):
    def test_delete_user_removes_permissions_and_ends_access(self):
        employee = self.create_employee()
        employee_id = employee.id
        other = app.test_client()
        with other.session_transaction() as session:
            session['user_id'] = employee_id
            session['login_startup_token'] = app.config['LOGIN_STARTUP_TOKEN']
        route = f'/employees/{employee_id}/delete'
        self.assertEqual(self.client.get(route).status_code, 405)
        self.assertEqual(self.client.post(route).status_code, 400)
        response = self.client.post(route, data={'csrf_token': self.token()}, follow_redirects=True)
        self.assertIn(b'User deleted.', response.data)
        self.assertIsNone(db.session.get(User, employee_id))
        from models import UserPermission
        self.assertEqual(db.session.scalars(db.select(UserPermission).where(
            UserPermission.user_id == employee_id)).all(), [])
        self.assertEqual(other.get('/pos').location, '/')

    def test_delete_requires_admin_and_prevents_self_deletion(self):
        cashier = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        route = f'/employees/{cashier.id}/delete'
        self.assertEqual(self.client.post(route, data={'csrf_token': self.token()}).location, '/')
        self.login('cashier')
        self.assertEqual(self.client.post(route, data={'csrf_token': self.token()}).status_code, 403)
        self.client.post('/logout', data={'csrf_token': self.token()})
        self.login('admin')
        admin = db.session.scalar(db.select(User).where(User.username == 'admin'))
        response = self.client.post(f'/employees/{admin.id}/delete',
                                    data={'csrf_token': self.token()}, follow_redirects=True)
        self.assertIn(b'You cannot delete your own account.', response.data)
        self.assertIsNotNone(db.session.get(User, admin.id))
        self.assertEqual(self.client.post('/employees/99999/delete',
            data={'csrf_token': self.token()}).status_code, 404)

    def test_delete_preserves_user_with_history(self):
        from models import Transaction, PurchaseReceipt, Supplier
        employee = self.create_employee()
        route = f'/employees/{employee.id}/delete'
        sale = Transaction(userId=employee.id, paymentMethod='cash', subtotal=6,
                           taxAmount=0, totalAmount=6, status='completed')
        supplier = Supplier(supplierName='Test supplier', reorderFreqDays=7)
        receipt = PurchaseReceipt(user_id=employee.id, supplier=supplier, reference='INV-1')
        for record in (sale, receipt):
            db.session.add(record)
            db.session.commit()
            response = self.client.post(route, data={'csrf_token': self.token()}, follow_redirects=True)
            self.assertIn(b'Deactivate the account instead', response.data)
            self.assertIsNotNone(db.session.get(User, employee.id))
            self.assertIsNotNone(db.session.get(type(record), record.id if record is receipt else record.transactionID))
            db.session.delete(record)
            db.session.commit()

    def payload(self, **changes):
        data = dict(action='create', username=' NewEmployee ', email='new@example.com',
                    first_name='New', last_name='Employee', role='cashier', is_active='on',
                    password='employee-password-123', confirm_password='employee-password-123',
                    permissions=[], csrf_token=self.token())
        data.update(changes)
        return data

    def create_employee(self):
        self.login('admin')
        response = self.client.post('/employee-management', data=self.payload())
        self.assertEqual(response.status_code, 302)
        return db.session.scalar(db.select(User).where(User.username == 'newemployee'))

    def test_create_and_login(self):
        employee = self.create_employee()
        self.assertTrue(check_password_hash(employee.passwordHash, 'employee-password-123'))
        self.assertTrue(employee.has_permission('pos'))
        self.assertFalse(employee.has_permission('reports'))
        page = self.client.get('/employee-management')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(b'employee-password-123', page.data)
        self.assertNotIn(b'value="pos"', page.data)
        self.client.post('/logout', data={'csrf_token': self.token()})
        self.assertEqual(self.login('NEWEMPLOYEE', 'employee-password-123').status_code, 302)
        self.assertEqual(self.client.get('/pos').status_code, 200)

    def test_validation_and_duplicate(self):
        self.create_employee()
        for changes in ({}, {'username': 'other', 'email': 'NEW@example.com'},
                        {'password': 'short', 'confirm_password': 'short'},
                        {'confirm_password': 'different'}, {'permissions': ['employees']},
                        {'role': 'superuser'}, {'username': 'x' * 51}):
            response = self.client.post('/employee-management', data=self.payload(**changes))
            self.assertEqual(response.status_code, 400)
        self.assertEqual(db.session.scalar(db.select(db.func.count(User.id))), 3)

    def test_admin_has_full_access_without_permission_overrides(self):
        employee = self.create_employee()
        self.assertTrue(employee.permissions)
        response = self.client.post('/employee-management', data=self.payload(
            action='update', employee_id=employee.id, username=employee.username,
            role='admin', password='', confirm_password='', permissions=[]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(employee.permissions, [])
        self.assertTrue(all(employee.has_permission(key) for key in PERMISSIONS))

        response = self.client.post('/employee-management', data=self.payload(
            username='newadmin', email='admin2@example.com', role='admin', permissions=[]))
        self.assertEqual(response.status_code, 302)
        admin = db.session.scalar(db.select(User).where(User.username == 'newadmin'))
        self.assertEqual(admin.permissions, [])
        self.assertTrue(all(admin.has_permission(key) for key in PERMISSIONS))

        response = self.client.post('/employee-management', data=self.payload(
            action='update', employee_id=employee.id, username=employee.username,
            password='', confirm_password='', permissions=['pos']))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(employee.has_permission('pos'))
        self.assertFalse(employee.has_permission('reports'))

    def test_admin_only_and_csrf(self):
        self.assertEqual(self.client.get('/employee-management').location, '/')
        self.login('cashier')
        self.assertEqual(self.client.get('/employee-management').status_code, 403)
        self.assertEqual(self.client.post('/employee-management', data=self.payload()).status_code, 403)
        self.login('admin')
        self.assertEqual(self.client.post('/employee-management', data={}).status_code, 400)

    def test_permission_changes_and_deactivation_affect_existing_session(self):
        employee = self.create_employee()
        other = app.test_client()
        other.get('/')
        with other.session_transaction() as session:
            token = session['csrf_token']
        other.post('/', data=dict(username=employee.username, password='employee-password-123', csrf_token=token))
        for permission in PERMISSIONS:
            response = self.client.post('/employee-management', data=self.payload(
                action='update', employee_id=employee.id, username=employee.username,
                password='', confirm_password='', permissions=[permission]))
            self.assertEqual(response.status_code, 302)
            for key, route in [('pos', '/pos'), ('inventory', '/inventory'),
                               ('products', '/product-entry'), ('reports', '/reports'),
                               ('suppliers', '/supplier-management')]:
                self.assertEqual(other.get(route).status_code, 200 if key == 'pos' or key == permission else 403)
            self.assertEqual(other.get('/employee-management').status_code, 403)
        self.client.post('/employee-management', data=self.payload(
            action='update', employee_id=employee.id, username=employee.username,
            password='', confirm_password='', is_active=''))
        self.assertEqual(other.get('/workspace').location, '/')
        self.client.post('/logout', data={'csrf_token': self.token()})
        self.assertEqual(self.login(employee.username, 'employee-password-123').status_code, 401)

    def test_password_reset_and_self_protection(self):
        employee = self.create_employee()
        response = self.client.post('/employee-management', data=self.payload(
            action='update', employee_id=employee.id, username=employee.username,
            password='replacement-password', confirm_password='replacement-password'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(employee.check_password('replacement-password'))
        self.assertFalse(employee.check_password('employee-password-123'))
        admin = db.session.scalar(db.select(User).where(User.username == 'admin'))
        for changes in ({'role': 'cashier'}, {'role': 'admin', 'is_active': ''}):
            response = self.client.post('/employee-management', data=self.payload(
                action='update', employee_id=admin.id, username='admin', email=admin.email,
                password='', confirm_password='', **changes))
            self.assertEqual(response.status_code, 400)
        self.assertEqual(admin.role, 'admin')
        self.assertTrue(admin.isActive)

    def test_mutating_routes_enforce_permissions(self):
        self.login('cashier')
        for route in ('/delete-product/1', '/inventory/receive', '/product-entry'):
            self.assertEqual(self.client.post(route, data={'csrf_token': self.token()}).status_code, 403)
        cashier = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        from models import UserPermission
        cashier.permissions.append(UserPermission(permission='pos', allowed=False))
        db.session.commit()
        self.assertTrue(cashier.has_permission('pos'))
        self.assertEqual(self.client.get('/pos').status_code, 200)
        self.assertEqual(self.client.post('/complete-sale', data={'csrf_token': self.token()}).status_code, 400)
        self.assertEqual(self.client.get('/product-lookup/123').status_code, 200)
        cashier.isActive = False
        self.assertFalse(cashier.has_permission('pos'))
