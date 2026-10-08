from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    passwordHash = db.Column(db.String(255), nullable=False)
    firstName = db.Column(db.String(50), nullable=False)
    lastName = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    isActive = db.Column(db.Boolean, default=True, nullable=False, index=True)
    dateCreated = db.Column(db.DateTime, nullable=False, default=datetime.now)

    inventoryAdjustments = db.relationship('InventoryAdjustment', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def set_password(self, password):
        self.passwordHash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passwordHash, password)

    def __repr__(self):
        return self.firstName + ' ' + self.lastName + ': ' + self.role


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    categoryName = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return self.categoryName


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    categoryId = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    barcode = db.Column(db.String(50), unique=True, nullable=False, index=True)
    productName = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    sellingPrice = db.Column(db.Numeric(10, 2), nullable=False)
    taxRate = db.Column(db.Numeric(5, 4), nullable=False)
    isActive = db.Column(db.Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint('"sellingPrice" >= 0', name='check_selling_price_positive'),
        CheckConstraint('"taxRate" >= 0', name='check_tax_rate_positive'),
    )

    inventory = db.relationship('Inventory', backref='product', uselist=False, lazy=True)
    inventoryAdjustments = db.relationship('InventoryAdjustment', backref='product', lazy=True)
    transactionItems = db.relationship('TransactionItem', backref='product', lazy=True)
    supplierProducts = db.relationship('SupplierProduct', backref='product', lazy=True)
    demandForecasts = db.relationship('DemandForecast', backref='product', lazy=True)
    reorderRecommendations = db.relationship('ReorderRecommendation', backref='product', lazy=True)
    lowStockAlerts = db.relationship('LowStockAlert', backref='product', lazy=True)

    def __repr__(self):
        return self.productName


class Inventory(db.Model):
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), unique=True, nullable=False)
    quantityOnHand = db.Column(db.Integer, nullable=False, index=True)
    reorderThreshold = db.Column(db.Integer, nullable=False, index=True)
    reorderQuantity = db.Column(db.Integer, nullable=False)
    lastUpdated = db.Column(db.DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint('"quantityOnHand" >= 0', name='check_quantity_on_hand_positive'),
        CheckConstraint('"reorderThreshold" >= 0', name='check_reorder_threshold_positive'),
        CheckConstraint('"reorderQuantity" >= 0', name='check_reorder_quantity_positive'),
    )


class InventoryAdjustment(db.Model):
    __tablename__ = 'inventory_adjustments'

    adjustmentID = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    userId = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quantityChanged = db.Column(db.Integer, nullable=False)
    adjustmentType = db.Column(db.Enum('addition', 'removal', 'correction', 'damage', 'loss', 'expiration', name='adjustment_type'), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)
    createdDate = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)


class Transaction(db.Model):
    __tablename__ = 'transactions'

    transactionID = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    transactionDate = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    paymentMethod = db.Column(db.Enum('cash', 'credit', 'debit', name='payment_method'), nullable=False, index=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    taxAmount = db.Column(db.Numeric(10, 2), nullable=False)
    totalAmount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum('completed', 'voided', 'refunded', name='transaction_status'), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint('subtotal >= 0', name='check_subtotal_positive'),
        CheckConstraint('"taxAmount" >= 0', name='check_tax_amount_positive'),
        CheckConstraint('"totalAmount" >= 0', name='check_total_amount_positive'),
    )

    items = db.relationship('TransactionItem', backref='transaction', lazy=True)


class TransactionItem(db.Model):
    __tablename__ = 'transactions_items'

    id = db.Column(db.Integer, primary_key=True)
    transactionId = db.Column(db.Integer, db.ForeignKey('transactions.transactionID'), nullable=False, index=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unitPrice = db.Column(db.Numeric(10, 2), nullable=False)
    unitCost = db.Column(db.Numeric(10, 2), nullable=False)
    lineTotal = db.Column(db.Numeric(10, 2), nullable=False)

    __table_args__ = (
        CheckConstraint('quantity >= 1', name='check_transaction_quantity'),
        CheckConstraint('"unitPrice" >= 0', name='check_unit_price_positive'),
        CheckConstraint('"unitCost" >= 0', name='check_unit_cost_positive'),
        CheckConstraint('"lineTotal" >= 0', name='check_line_total_positive'),
    )


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    supplierID = db.Column(db.Integer, primary_key=True)
    supplierName = db.Column(db.String(150), nullable=False, index=True)
    contactName = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(30), nullable=True, index=True)
    email = db.Column(db.String(100), nullable=True, index=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    reorderFreqDays = db.Column(db.Integer, nullable=False)
    createdDate = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updateAt = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint('"reorderFreqDays" >= 0', name='check_reorder_frequency'),
    )

    supplierProducts = db.relationship('SupplierProduct', backref='supplier', lazy=True)
    reorderRecommendations = db.relationship('ReorderRecommendation', backref='supplier', lazy=True)

    def __repr__(self):
        return self.supplierName


class SupplierProduct(db.Model):
    __tablename__ = 'supplier_products'

    id = db.Column(db.Integer, primary_key=True)
    supplierId = db.Column(db.Integer, db.ForeignKey('suppliers.supplierID'), nullable=False, index=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    unitCost = db.Column(db.Numeric(10, 2), nullable=False)
    minimumOrderQuantity = db.Column(db.Integer, nullable=False)
    leadTimeDays = db.Column(db.Integer, nullable=False)
    isPrefered = db.Column(db.Boolean, default=False, nullable=False)
    lastPriceUpdate = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint('"unitCost" >= 0', name='check_supplier_unit_cost'),
        CheckConstraint('"minimumOrderQuantity" >= 1', name='check_minimum_order_quantity'),
        CheckConstraint('"leadTimeDays" >= 0', name='check_lead_time_days'),
    )


class DemandForecast(db.Model):
    __tablename__ = 'demand_forecasts'

    id = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    forecastDate = db.Column(db.DateTime, nullable=False, index=True)
    predictedDemand = db.Column(db.Numeric(10, 2), nullable=False)
    predictedDaysUntilLow = db.Column(db.Numeric(10, 2), nullable=False)
    confidenceScore = db.Column(db.Numeric(4, 3), nullable=False)
    generatedAt = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    __table_args__ = (
        CheckConstraint('"predictedDemand" >= 0', name='check_predicted_demand'),
        CheckConstraint('"predictedDaysUntilLow" >= 0', name='check_predicted_days'),
        CheckConstraint('"confidenceScore" >= 0 AND "confidenceScore" <= 1', name='check_confidence_score'),
    )


class ReorderRecommendation(db.Model):
    __tablename__ = 'reorder_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    supplierId = db.Column(db.Integer, db.ForeignKey('suppliers.supplierID'), nullable=False, index=True)
    recommendedQuantity = db.Column(db.Integer, nullable=False)
    recommendedOrderDate = db.Column(db.DateTime, nullable=False, index=True)
    estimatedUnitCost = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum('pending', 'approved', 'ordered', 'completed', 'cancelled', name='reorder_status'), nullable=False, index=True)
    createdDate = db.Column(db.DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint('"recommendedQuantity" >= 1', name='check_recommended_quantity'),
        CheckConstraint('"estimatedUnitCost" >= 0', name='check_estimated_unit_cost'),
    )


class LowStockAlert(db.Model):
    __tablename__ = 'low_stock_alerts'

    id = db.Column(db.Integer, primary_key=True)
    productId = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantityAtAlert = db.Column(db.Integer, nullable=False)
    threshold = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum('active', 'resolved', name='low_stock_status'), nullable=False, index=True)
    createdDate = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    resolvedAt = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint('"quantityAtAlert" >= 0', name='check_quantity_at_alert'),
        CheckConstraint('"threshold" >= 0', name='check_threshold'),
    )