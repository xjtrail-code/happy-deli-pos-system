import test_auth
from app import User, app, db
from models import PERMISSIONS
from werkzeug.security import check_password_hash


class EmployeeManagementTests(test_auth.AuthenticationTests):
    def payload(self, **changes):
        data = dict(action='create', username=' NewEmployee ', email='new@example.com',
                    first_name='New', last_name='Employee', role='cashier', is_active='on',
                    password='employee-password-123', confirm_password='employee-password-123',
                    permissions=['pos'], csrf_token=self.token())
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
                self.assertEqual(other.get(route).status_code, 200 if key == permission else 403)
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
        self.assertEqual(self.client.post('/complete-sale', data={'csrf_token': self.token()}).status_code, 403)
        self.assertEqual(self.client.get('/product-lookup/123').status_code, 403)
