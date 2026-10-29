import unittest
import test_auth
from datetime import datetime
from decimal import Decimal
from app import app, db
from models import (Category, Product, Inventory, Supplier, SupplierProduct,
                    ReorderRecommendation, PurchaseReceipt, Transaction, TransactionItem,
                    User, UserPermission)


class PurchasingTests(unittest.TestCase):
    setUp = test_auth.AuthenticationTests.setUp
    tearDown = test_auth.AuthenticationTests.tearDown
    token = test_auth.AuthenticationTests.token
    login = test_auth.AuthenticationTests.login

    def seed(self):
        category = Category(categoryName='Test')
        self.product = Product(productName='Test milk', barcode='123', sellingPrice=5,
                               taxRate=0, category=category)
        self.product.inventory = Inventory(quantityOnHand=2, reorderThreshold=5, reorderQuantity=10)
        self.supplier = Supplier(supplierName='Test supplier', reorderFreqDays=7)
        db.session.add_all([self.product, self.supplier])
        db.session.flush()
        db.session.add(SupplierProduct(productId=self.product.id, supplierId=self.supplier.supplierID,
            unitCost=2, minimumOrderQuantity=12, leadTimeDays=2, lastPriceUpdate=datetime.now()))
        db.session.commit()
        self.login('admin')

    def post(self, route, **data):
        return self.client.post(route, data=dict(csrf_token=self.token(), **data))

    def test_generate_and_transitions(self):
        self.seed()
        for _ in range(2):
            self.assertEqual(self.post('/reorder-recommendations', action='generate').status_code, 302)
        rows = db.session.scalars(db.select(ReorderRecommendation)).all()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.recommendedQuantity, 12)
        self.assertEqual(self.post('/reorder-recommendations', action='order', recommendation_id=r.id).status_code, 400)
        for action, expected in [('approve', 'approved'), ('order', 'ordered'), ('complete', 'completed')]:
            self.assertEqual(self.post('/reorder-recommendations', action=action, recommendation_id=r.id).status_code, 302)
            self.assertEqual(r.status, expected)
        self.assertEqual(self.product.inventory.quantityOnHand, 2)
        self.assertEqual(self.client.get('/reorder-recommendations').status_code, 200)

    def test_missing_supplier_and_inactive_product(self):
        self.seed()
        db.session.query(SupplierProduct).delete()
        db.session.commit()
        self.post('/reorder-recommendations', action='generate')
        self.assertEqual(db.session.scalar(db.select(db.func.count(ReorderRecommendation.id))), 0)

    def test_supplier_receipt_atomicity_duplicates_and_stock(self):
        self.seed()
        data = dict(supplier_id=self.supplier.supplierID, reference='INV-1',
                    product_id=[str(self.product.id)], quantity=['3'], unit_cost=['2.50'])
        self.assertEqual(self.post('/purchase-receipts', **data).status_code, 302)
        self.assertEqual(self.product.inventory.quantityOnHand, 5)
        self.assertEqual(db.session.scalar(db.select(PurchaseReceipt)).total, Decimal('7.50'))
        self.post('/purchase-receipts', **data)
        self.assertEqual(self.product.inventory.quantityOnHand, 5)
        data.update(reference='INV-2', product_id=[str(self.product.id)] * 2,
                    quantity=['4', '-1'], unit_cost=['2.50', '2.50'])
        self.post('/purchase-receipts', **data)
        self.assertEqual(self.product.inventory.quantityOnHand, 5)
        self.assertEqual(db.session.scalar(db.select(db.func.count(PurchaseReceipt.id))), 1)
        self.assertIn(b'INV-1', self.client.get('/purchase-receipts').data)

    def test_sales_receipt_saved_prices_and_search(self):
        self.seed()
        user = db.session.scalar(db.select(User).where(User.username == 'admin'))
        sale = Transaction(userId=user.id, paymentMethod='cash', subtotal=6, taxAmount=0,
                           totalAmount=6, status='completed')
        sale.items.append(TransactionItem(productId=self.product.id, quantity=2, unitPrice=3,
                                          unitCost=2, lineTotal=6))
        db.session.add(sale)
        db.session.commit()
        response = self.client.get(f'/receipts/{sale.transactionID}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'$3.00', response.data)
        self.assertIn(b'Test milk', response.data)
        self.assertIn(b'View receipt', self.client.get(f'/receipts?receipt_id={sale.transactionID}').data)
        self.assertIn(b'No receipts found', self.client.get('/receipts?receipt_id=99999').data)
        self.assertEqual(self.client.get('/receipts?receipt_id=abc').status_code, 400)
        self.assertEqual(self.client.get('/receipts/99999').status_code, 404)

    def test_permissions_and_csrf(self):
        for route in ('/receipts', '/purchase-receipts', '/reorder-recommendations'):
            self.assertEqual(self.client.get(route).status_code, 302)
        self.login('cashier')
        for route in ('/receipts', '/receipts/1', '/purchase-receipts', '/reorder-recommendations'):
            self.assertEqual(self.client.get(route).status_code, 403)
        cashier = db.session.scalar(db.select(User).where(User.username == 'cashier'))
        cashier.permissions.append(UserPermission(permission='receipts', allowed=True))
        db.session.commit()
        self.assertEqual(self.client.get('/receipts').status_code, 200)
        self.assertEqual(self.client.get('/purchase-receipts').status_code, 200)
        self.assertEqual(self.post('/purchase-receipts').status_code, 403)
        self.assertEqual(self.client.post('/purchase-receipts').status_code, 400)
