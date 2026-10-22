import os
from dotenv import load_dotenv
import secrets
from pathlib import Path

from datetime import datetime
from decimal import Decimal, InvalidOperation   

from models import db, PERMISSIONS, UserPermission, PurchaseReceipt, PurchaseReceiptItem
from sqlalchemy.exc import IntegrityError
from models import (User, Category, Product, Transaction, TransactionItem, 
                    Inventory, Supplier, SupplierProduct, InventoryAdjustment, 
                    DemandForecast, LowStockAlert, ReorderRecommendation)
from datetime import date, timedelta
from functools import wraps

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    SQLALCHEMY_DATABASE_URI=os.environ['DATABASE_URL'],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
if not app.config['SECRET_KEY']:
    os.makedirs(app.instance_path, exist_ok=True)
    key_path = os.path.join(app.instance_path, 'secret_key')
    try:
        with open(key_path, 'x', encoding='utf-8') as key_file:
            key_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    with open(key_path, encoding='utf-8') as key_file:
        app.config['SECRET_KEY'] = key_file.read().strip()

#db = SQLAlchemy(app)
db.init_app(app)

@app.route("/test-db")
def test_db():
    try:
        # Attempt to connect to the database
        db.session.execute(db.text('SELECT 1'))
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {e}"
'''
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    __table_args__ = (db.CheckConstraint("role IN ('admin', 'cashier')"),)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.now()
    )'''
'''
PRODUCT_SEED = [
    ("012345678901", "Whole Milk 1 Gal", 3.99, 40),
    ("012345678902", "Large Eggs 12ct", 4.29, 55),
    ("012345678903", "White Bread Loaf", 2.49, 35),
    ("012345678904", "Butter Unsalted 1 lb", 4.99, 30),
    ("012345678905", "Cheddar Cheese 8 oz", 3.79, 28),
    ("012345678906", "Bananas 1 lb", 0.69, 120),
    ("012345678907", "Gala Apples 1 lb", 1.99, 80),
    ("012345678908", "Chicken Breast 1 lb", 5.49, 25),
    ("012345678909", "Ground Beef 1 lb", 6.99, 22),
    ("012345678910", "Spaghetti Pasta 16 oz", 1.89, 60),
    ("012345678911", "Marinara Sauce 24 oz", 3.29, 45),
    ("012345678912", "Long Grain Rice 2 lb", 2.99, 50),
    ("012345678913", "Orange Juice 52 oz", 4.49, 33),
    ("012345678914", "Bottled Water 24pk", 5.99, 38),
    ("012345678915", "Cola 12pk Cans", 7.49, 42),
    ("012345678916", "Potato Chips 8 oz", 3.49, 65),
    ("012345678917", "Chocolate Bar", 1.49, 100),
    ("012345678918", "Ground Coffee 12 oz", 8.99, 27),
    ("012345678919", "Paper Towels 6 Roll", 9.99, 20),
    ("012345678920", "Dish Soap 20 oz", 3.99, 36),
]'''


def login_required(role=None, permission=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('home'))
            if role is not None and g.user.role != role:
                abort(403)
            if permission and not g.user.has_permission(permission):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def load_user_and_check_csrf():
    g.user = db.session.get(User, session['user_id']) if 'user_id' in session else None
    if g.user and not g.user.isActive:
        session.clear()
        g.user = None
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        if not expected or not secrets.compare_digest(token, expected):
            abort(400, description='Invalid form token. Reload the page and try again.')


@app.route('/', methods=['GET', 'POST'])
def home():
    if g.user:
        return redirect(url_for('admin_dashboard' if g.user.role == 'admin' else 'workspace'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        user = db.session.scalar(db.select(User).where(User.username == username))
        if user and user.isActive and user.check_password(request.form.get('password', '')):
            session.clear()
            session['user_id'] = user.id
            session.permanent = True
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'workspace'))
        error = 'Invalid username or password.'
    return render_template('login.html', error=error), 401 if error else 200


@app.post('/logout')
@login_required()
def logout():
    session.clear()
    return redirect(url_for('home'))

'''@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('dashboard'))'''


@app.route('/admin-dashboard')
@login_required('admin')
def admin_dashboard():
    from datetime import datetime, date, timedelta

    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)

    # Get all completed transactions from the last 7 days
    start_of_week = start_of_day - timedelta(days=6)

    recent_transactions = db.session.scalars(
        db.select(Transaction)
        .where(Transaction.status == 'completed')
        .where(Transaction.transactionDate >= start_of_week)
        .where(Transaction.transactionDate < end_of_day)
        .order_by(Transaction.transactionDate.asc())
    ).all()

    # Today's completed transactions
    todays_transactions_list = [
        t for t in recent_transactions
        if start_of_day <= t.transactionDate < end_of_day
    ]

    todays_sales = round(
        float(sum(t.totalAmount for t in todays_transactions_list)),
        2
    )

    todays_transactions = len(todays_transactions_list)

    # Seven-day sales chart
    sales_labels = []
    sales_data = []

    for days_ago in range(6, -1, -1):
        current_day = today - timedelta(days=days_ago)

        daily_total = sum(
            t.totalAmount for t in recent_transactions
            if t.transactionDate.date() == current_day
        )

        sales_labels.append(current_day.strftime('%a'))
        sales_data.append(round(float(daily_total), 2))

    # Cash vs Card breakdown for the last 7 days
    cash_sales = round(
        float(sum(
            t.totalAmount for t in recent_transactions
            if t.paymentMethod == 'cash'
        )),
        2
    )

    card_sales = round(
        float(sum(
            t.totalAmount for t in recent_transactions
            if t.paymentMethod in ('credit', 'debit')
        )),
        2
    )

    # Inventory alerts
    low_stock_alerts = db.session.scalar(
        db.select(db.func.count(Inventory.id))
        .where(
            Inventory.quantityOnHand <= Inventory.reorderThreshold
        )
    ) or 0

    return render_template(
        'admin_dashboard.html',
        todays_sales=todays_sales,
        todays_transactions=todays_transactions,
        low_stock_alerts=low_stock_alerts,
        profit_margin=None,
        sales_labels=sales_labels,
        sales_data=sales_data,
        cash_sales=cash_sales,
        card_sales=card_sales
    )



@app.route('/pos')
@login_required(permission='pos')
def pos():
    return render_template('pos.html')


@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/product-entry', methods=['GET', 'POST'])
@login_required(permission='products')
def product_entry():
    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    message = None
    message_type = 'success'
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        try:
            barcode = request.form.get('barcode', '').strip()
            product_name = request.form.get('product_name', '').strip()
            category_name = request.form.get('category', '').strip()
            price = Decimal(request.form.get('price', '').strip()).quantize(Decimal('0.01'))
            quantity = int(request.form.get('quantity', ''))

            if not barcode or not product_name or not category_name:
                raise ValueError('Barcode, product name, and category are required.')
            if price < 0:
                raise ValueError('Selling price cannot be negative.')
            if quantity < 1 or quantity > 1_000_000:
                raise ValueError('Quantity must be between 1 and 1,000,000.')

            # Find the entered category, or create it if this is a new category.
            category = db.session.scalar(
                db.select(Category).where(Category.categoryName.ilike(category_name))
            )
            if category is None:
                category = Category(categoryName=category_name)
                db.session.add(category)
                db.session.flush()

            # If the barcode already exists, update its category/price and add stock.
            existing_product = db.session.scalar(
                db.select(Product).where(Product.barcode == barcode)
            )

            if existing_product:
                existing_product.productName = product_name
                existing_product.category = category
                existing_product.sellingPrice = price

                if existing_product.inventory is None:
                    existing_product.inventory = Inventory(
                        quantityOnHand=0,
                        reorderThreshold=5,
                        reorderQuantity=20
                    )
                existing_product.inventory.quantityOnHand += quantity
                existing_product.inventory.lastUpdated = datetime.now()

                message = (
                    f"{existing_product.productName} updated successfully. "
                    f"New quantity: {existing_product.inventory.quantityOnHand}."
                )
            else:
                product = Product(
                    barcode=barcode,
                    productName=product_name,
                    sellingPrice=price,
                    taxRate=Decimal('0.0635'),
                    category=category
                )
                product.inventory = Inventory(
                    quantityOnHand=quantity,
                    reorderThreshold=5,
                    reorderQuantity=20
                )
                db.session.add(product)
                message = f"{product_name} was added successfully."

            db.session.commit()
            form_data = {}

        except (ValueError, InvalidOperation, TypeError) as error:
            db.session.rollback()
            message = str(error) or 'Please enter valid product information.'
            message_type = 'danger'

        except Exception:
            db.session.rollback()
            app.logger.exception('Product entry failed')
            message = 'Could not save the product. Please check the information and try again.'
            message_type = 'danger'

    categories = db.session.scalars(
        db.select(Category).order_by(Category.categoryName)
    ).all()
    return render_template(
        'product_entry.html',
        message=message,
        message_type=message_type,
        categories=categories,
        form_data=form_data
    )

@app.route('/inventory')
@login_required(permission='inventory')
def inventory():
    products = db.session.scalars(db.select(Product).where(Product.isActive.is_(True)).order_by(Product.productName)).all()
    return render_template('inventory.html', products=products)


@app.post('/inventory/receive')
@login_required(permission='inventory')
def receive_inventory_stock():
    from datetime import datetime
    try:
        product_id = int(request.form.get('product_id', ''))
    except ValueError:
        abort(400, description='No product selected.')
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)

    # Server-side validation: never trust the browser's total.
    try:
        units = int(request.form.get('total_units', ''))
    except ValueError:
        abort(400, description='Enter a whole number of units.')
    if units < 1 or units > 1_000_000:
        abort(400, description='Units must be between 1 and 1,000,000.')

    inv = product.inventory
    if inv is None:
        inv = Inventory(productId=product.id, quantityOnHand=0,
                        reorderThreshold=0, reorderQuantity=0)
        db.session.add(inv)

    inv.quantityOnHand += units
    inv.lastUpdated = datetime.now()

    db.session.add(InventoryAdjustment(
        productId=product.id,
        userId=g.user.id,
        quantityChanged=units,
        adjustmentType='addition',
        reason='Stock received via inventory page',
    ))
    db.session.commit()
    return redirect(url_for('inventory', stock_added=1))



@app.route('/product-lookup/<barcode>')
@login_required()
def product_lookup(barcode):
    if not any(g.user.has_permission(p) for p in ('pos', 'inventory', 'products')):
        abort(403)
    product = db.session.scalar(
        db.select(Product).where(Product.barcode == barcode)
    )

    if product:
        return {
            'found': True,
            'name': product.productName,
            'price': float(product.sellingPrice),
            'category': product.category.categoryName if product.category else '',
            'quantity': product.inventory.quantityOnHand if product.inventory else 0
        }

    return {
        'found': False
    }
#no need to delete a product.
@app.post('/delete-product/<int:product_id>')
@login_required(permission='products')
def delete_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        abort(404)

    db.session.delete(product)
    db.session.commit()

    return redirect(url_for('inventory'))

'''@app.cli.command('seed-products')
def seed_products():
    """Insert sample products if the table is empty."""
    if db.session.scalar(db.select(db.func.count(Product.id))) > 0:
        click.echo('Products already exist, skipping.')
        return
    db.session.add_all(
        Product(barcode=b, name=n, price=p, quantity=q)
        for b, n, p, q in PRODUCT_SEED
    )
    db.session.commit()
    click.echo(f'Seeded {len(PRODUCT_SEED)} products.')'''

'''@app.cli.command('init-db')
def init_db():
    """Create missing tables without deleting existing data."""
    db.create_all()
    click.echo('Database initialized.')'''


@app.cli.command('create-user')
@click.argument('username')
@click.option('--role', type=click.Choice(['admin', 'cashier']), default='cashier')
@click.password_option()
def create_user(username, role, password):
    """Create an account with a password prompted without echoing."""
    username = username.strip().lower()
    if not username or len(username) > 50:
        raise click.ClickException('Username must be between 1 and 50 characters.')
    if len(password) < 12:
        raise click.ClickException('Password must be at least 12 characters.')
    if db.session.scalar(db.select(User).where(User.username == username)):
        raise click.ClickException('Username already exists.')
    user = User(username=username, role=role, email=f'{username}@accounts.invalid',
                firstName=username, lastName='')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'Created {role} account: {username}')



@app.post('/complete-sale')
@login_required(permission='pos')
def complete_sale():
    import json
    from datetime import datetime
    from decimal import Decimal, ROUND_HALF_UP

    cents = Decimal('0.01')

    try:
        cart = json.loads(request.form.get('cart', '[]'))
        payment_method = request.form.get(
            'payment_method', ''
        ).strip().lower()

        # The POS currently sends "card"; Transaction stores credit or debit
        if payment_method == 'card':
            payment_method = 'credit'

        if payment_method not in ('cash', 'credit', 'debit'):
            return {
                'success': False,
                'error': 'Please select Cash, Credit or Debit.'
            }, 400

        if not isinstance(cart, list) or not cart:
            return {
                'success': False,
                'error': 'Your cart is empty.'
            }, 400

        quantities = {}

        for item in cart:
            barcode = str(item['barcode'])
            quantity = int(item['quantity'])

            if quantity <= 0:
                return {
                    'success': False,
                    'error': 'Invalid quantity.'
                }, 400

            quantities[barcode] = (
                quantities.get(barcode, 0) + quantity
            )

        subtotal = Decimal('0.00')
        tax_amount = Decimal('0.00')
        items = []

        for barcode, quantity in quantities.items():
            product = db.session.scalar(
                db.select(Product).where(
                    Product.barcode == barcode,
                    Product.isActive.is_(True)
                )
            )

            if product is None:
                db.session.rollback()
                return {
                    'success': False,
                    'error': f'Product {barcode} not found.'
                }, 400

            # Lock the stock row so two registers can't oversell the same item
            stock = db.session.scalar(
                db.select(Inventory)
                .where(Inventory.productId == product.id)
                .with_for_update()
            )

            if stock is None or stock.quantityOnHand < quantity:
                db.session.rollback()
                return {
                    'success': False,
                    'error': f'Not enough stock for {product.productName}.'
                }, 400

            stock.quantityOnHand -= quantity
            stock.lastUpdated = datetime.now()

            # Cost comes from the preferred supplier; 0.00 if none is set up yet
            supplier_product = db.session.scalar(
                db.select(SupplierProduct)
                .where(SupplierProduct.productId == product.id)
                .order_by(SupplierProduct.isPrefered.desc(), SupplierProduct.unitCost)
            )
            unit_cost = supplier_product.unitCost if supplier_product else Decimal('0.00')

            line_total = (product.sellingPrice * quantity).quantize(
                cents, rounding=ROUND_HALF_UP
            )
            subtotal += line_total
            tax_amount += (line_total * product.taxRate).quantize(
                cents, rounding=ROUND_HALF_UP
            )

            items.append(TransactionItem(
                product=product,
                quantity=quantity,
                unitPrice=product.sellingPrice,
                unitCost=unit_cost,
                lineTotal=line_total
            ))

        total = subtotal + tax_amount

        transaction = Transaction(
            userId=g.user.id,
            paymentMethod=payment_method,
            subtotal=subtotal,
            taxAmount=tax_amount,
            totalAmount=total,
            status='completed',
            items=items
        )

        db.session.add(transaction)
        db.session.commit()

        return {
            'success': True,
            'sale_id': transaction.transactionID,
            'total': float(total)
        }

    except (ValueError, TypeError, KeyError):
        db.session.rollback()
        return {
            'success': False,
            'error': 'Invalid transaction data.'
        }, 400

    except Exception:
        db.session.rollback()
        app.logger.exception('Sale failed')

        return {
            'success': False,
            'error': 'Unable to complete sale.'
        }, 500


@app.route('/reports')
@login_required(permission='reports')
def reports():
    transactions = db.session.scalars(
        db.select(Transaction)
        .where(Transaction.status == 'completed')
        .order_by(Transaction.transactionDate.desc())
    ).all()

    total_revenue = sum(t.totalAmount for t in transactions)
    total_transactions = len(transactions)

    cash_sales = sum(
        t.totalAmount for t in transactions
        if t.paymentMethod == 'cash'
    )

    card_sales = sum(
        t.totalAmount for t in transactions
        if t.paymentMethod in ('credit', 'debit')
    )

    return render_template(
        'reports.html',
        sales=transactions,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        cash_sales=cash_sales,
        card_sales=card_sales
    )

   # EMPLOYEE MANAGEMENT
@app.route('/workspace')
@login_required()
def workspace():
    return render_template('workspace.html', permissions=PERMISSIONS)


@app.cli.command('init-db')
def initialize_database():
    """Create missing tables without changing existing accounts or data."""
    db.create_all()
    click.echo('Missing database tables created.')


@app.route('/employee-management', methods=['GET', 'POST'])
@login_required('admin')
def employee_management():
    error = None
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            if action not in ('create', 'update'):
                raise ValueError('Invalid employee action.')
            employee = User() if action == 'create' else db.get_or_404(User, request.form.get('employee_id', type=int))
            username = request.form.get('username', '').strip().lower()
            email = request.form.get('email', '').strip().lower()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            role = request.form.get('role', '')
            active = request.form.get('is_active') == 'on'
            selected = set(request.form.getlist('permissions'))
            password = request.form.get('password', '')
            if not username or len(username) > 50 or any(c.isspace() for c in username):
                raise ValueError('Username must contain 1–50 characters with no spaces.')
            if not email or len(email) > 100 or '@' not in email:
                raise ValueError('Enter an email address of at most 100 characters.')
            if not first_name or not last_name or len(first_name) > 50 or len(last_name) > 50:
                raise ValueError('First and last names are required (50 characters maximum each).')
            if role not in ('admin', 'cashier') or not selected.issubset(PERMISSIONS):
                raise ValueError('Select a valid role and permissions.')
            if (action == 'create' or password) and len(password) < 12:
                raise ValueError('Passwords must be at least 12 characters.')
            if password != request.form.get('confirm_password', ''):
                raise ValueError('Passwords do not match.')
            if employee.id == g.user.id and (role != 'admin' or not active):
                raise ValueError('You cannot deactivate or remove your own administrator access.')
            duplicate = db.session.scalar(db.select(User).where(
                db.or_(db.func.lower(User.username) == username, db.func.lower(User.email) == email),
                User.id != employee.id if employee.id else db.true()))
            if duplicate:
                raise ValueError('That username or email address is already in use.')
            employee.username, employee.email = username, email
            employee.firstName, employee.lastName = first_name, last_name
            employee.role, employee.isActive = role, active
            if password:
                employee.set_password(password)
            overrides = {entry.permission: entry for entry in employee.permissions}
            for permission in PERMISSIONS:
                if permission in overrides:
                    overrides[permission].allowed = permission in selected
                else:
                    employee.permissions.append(UserPermission(permission=permission, allowed=permission in selected))
            db.session.add(employee)
            db.session.commit()
            flash('Employee created.' if action == 'create' else 'Employee updated.', 'success')
            return redirect(url_for('employee_management'))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
        except IntegrityError:
            db.session.rollback()
            error = 'That username or email address is already in use.'
    employees = db.session.scalars(db.select(User).order_by(User.username)).all()
    return render_template('employee_management.html', employees=employees,
                           permissions=PERMISSIONS, error=error), 400 if error else 200


#settings
@app.route('/settings')
@login_required('admin')
def settings():
    return render_template('settings.html')



@app.route('/purchase-receipts', methods=['GET', 'POST'])
@login_required(permission='receipts')
def purchase_receipts():
    if request.method == 'POST':
        if not g.user.has_permission('purchase_receipts'):
            abort(403)
        try:
            supplier = db.get_or_404(Supplier, request.form.get('supplier_id', type=int))
            reference = request.form.get('reference', '').strip()
            if not reference or len(reference) > 100:
                raise ValueError('Enter a supplier receipt reference (100 characters maximum).')
            products = request.form.getlist('product_id')
            quantities = request.form.getlist('quantity')
            costs = request.form.getlist('unit_cost')
            if not products or len(products) > 100 or not len(products) == len(quantities) == len(costs):
                raise ValueError('Enter between 1 and 100 complete receipt lines.')
            receipt_record = PurchaseReceipt(supplier_id=supplier.supplierID, reference=reference, user_id=g.user.id)
            db.session.add(receipt_record)
            for product_id, quantity, cost in zip(products, quantities, costs):
                product = db.get_or_404(Product, int(product_id))
                quantity = int(quantity)
                cost = Decimal(cost)
                if not product.isActive or not 1 <= quantity <= 1_000_000 or not cost.is_finite() or not 0 <= cost <= Decimal('99999999.99') or cost != cost.quantize(Decimal('0.01')):
                    raise ValueError('Use active products, positive whole quantities, and nonnegative costs with at most two decimal places.')
                receipt_record.items.append(PurchaseReceiptItem(product_id=product.id, quantity=quantity, unit_cost=cost))
                stock = db.session.scalar(db.select(Inventory).where(Inventory.productId == product.id).with_for_update())
                if stock is None:
                    stock = Inventory(productId=product.id, quantityOnHand=0, reorderThreshold=0, reorderQuantity=0)
                    db.session.add(stock)
                stock.quantityOnHand += quantity
                stock.lastUpdated = datetime.now()
                db.session.add(InventoryAdjustment(productId=product.id, userId=g.user.id,
                    quantityChanged=quantity, adjustmentType='addition', reason=f'Supplier receipt: {reference}'))
            db.session.commit()
            flash('Supplier receipt saved and inventory updated.', 'success')
            return redirect(url_for('purchase_receipts'))
        except (ValueError, InvalidOperation):
            db.session.rollback()
            flash('Check the receipt reference, product lines, quantities and unit costs. No stock was received.', 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('This supplier receipt reference is already recorded. No stock was received.', 'danger')
    page = db.paginate(db.select(PurchaseReceipt).order_by(PurchaseReceipt.received_at.desc(), PurchaseReceipt.id.desc()), per_page=25)
    return render_template('purchase_receipts.html', page=page,
        suppliers=db.session.scalars(db.select(Supplier).order_by(Supplier.supplierName)).all(),
        products=db.session.scalars(db.select(Product).where(Product.isActive.is_(True)).order_by(Product.productName)).all())


@app.route('/receipts')
@login_required(permission='receipts')
def receipts():
    query = db.select(Transaction).order_by(Transaction.transactionDate.desc(), Transaction.transactionID.desc())
    receipt_id = request.args.get('receipt_id', '').strip()
    if receipt_id:
        try:
            query = query.where(Transaction.transactionID == int(receipt_id))
        except ValueError:
            abort(400, description='Receipt number must be a whole number.')
    page = db.paginate(query, per_page=25, max_per_page=25)
    return render_template('receipts.html', page=page, receipt_id=receipt_id)


@app.route('/receipts/<int:transaction_id>')
@login_required(permission='receipts')
def receipt(transaction_id):
    transaction = db.get_or_404(Transaction, transaction_id)
    return render_template('receipt.html', transaction=transaction)


@app.route('/reorder-recommendations', methods=['GET', 'POST'])
@login_required(permission='reorders')
def reorder_recommendation():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'generate':
            stocks = db.session.scalars(db.select(Inventory).join(Product).where(
                Product.isActive.is_(True),
                Inventory.quantityOnHand <= Inventory.reorderThreshold)).all()
            created = 0
            missing = 0
            for stock in stocks:
                existing = db.session.scalar(db.select(ReorderRecommendation).where(
                    ReorderRecommendation.productId == stock.productId,
                    ReorderRecommendation.status.in_(['pending', 'approved', 'ordered'])))
                if existing:
                    continue
                offer = db.session.scalar(db.select(SupplierProduct).where(
                    SupplierProduct.productId == stock.productId).order_by(
                    SupplierProduct.isPrefered.desc(), SupplierProduct.unitCost,
                    SupplierProduct.id))
                if not offer:
                    missing += 1
                    continue
                quantity = max(stock.reorderQuantity,
                               stock.reorderThreshold + 1 - stock.quantityOnHand,
                               offer.minimumOrderQuantity)
                db.session.add(ReorderRecommendation(
                    productId=stock.productId, supplierId=offer.supplierId,
                    recommendedQuantity=quantity, recommendedOrderDate=datetime.now(),
                    estimatedUnitCost=offer.unitCost, status='pending'))
                created += 1
            db.session.commit()
            flash(f'Created {created} recommendations. {missing} low-stock products need a linked supplier.', 'success')
        elif action in ('approve', 'order', 'complete', 'cancel'):
            recommendation = db.get_or_404(ReorderRecommendation, request.form.get('recommendation_id', type=int))
            transitions = {'approve': ('pending', 'approved'), 'order': ('approved', 'ordered'),
                           'complete': ('ordered', 'completed')}
            if action == 'cancel' and recommendation.status in ('pending', 'approved'):
                recommendation.status = 'cancelled'
            elif action in transitions and recommendation.status == transitions[action][0]:
                recommendation.status = transitions[action][1]
            else:
                abort(400, description='This recommendation cannot make that status change.')
            db.session.commit()
            flash('Recommendation updated.', 'success')
        else:
            abort(400, description='Unknown recommendation action.')
        return redirect(url_for('reorder_recommendation'))
    recommendations = db.session.scalars(db.select(ReorderRecommendation).order_by(
        ReorderRecommendation.createdDate.desc(), ReorderRecommendation.id.desc())).all()
    return render_template('reorder_recommendations.html', recommendations=recommendations)


# SUPPLIER MANAGEMENT

@app.route('/supplier-management', methods=['GET', 'POST'])
@login_required(permission='suppliers')
def supplier_management():

    if request.method == 'POST':
        action = request.form.get('action', '')

        try:
            if action in ('add_supplier', 'edit_supplier'):
                name = request.form.get('supplier_name', '').strip()
                frequency = int(request.form.get('reorder_frequency', '0'))

                if not name or len(name) > 150 or not 1 <= frequency <= 3650:
                    raise ValueError(
                        'Enter a supplier name and reorder frequency between 1 and 3650 days.'
                    )

                fields = {
                    'contactName': request.form.get('contact_name', '').strip(),
                    'phone': request.form.get('phone', '').strip(),
                    'email': request.form.get('email', '').strip(),
                    'address': request.form.get('address', '').strip(),
                    'city': request.form.get('city', '').strip(),
                    'state': request.form.get('state', '').strip(),
                }

                limits = {
                    'contactName': 100,
                    'phone': 30,
                    'email': 100,
                    'address': 255,
                    'city': 100,
                    'state': 50
                }

                if any(len(value) > limits[key] for key, value in fields.items()):
                    raise ValueError('One of the supplier contact fields is too long.')

                if action == 'edit_supplier':
                    supplier = db.get_or_404(
                        Supplier,
                        int(request.form['supplier_id'])
                    )
                    supplier.updateAt = datetime.now()
                else:
                    supplier = Supplier()

                supplier.supplierName = name
                supplier.reorderFreqDays = frequency

                for key, value in fields.items():
                    setattr(supplier, key, value or None)

                db.session.add(supplier)
                flash('Supplier saved successfully.', 'success')

            elif action == 'delete_supplier':
                supplier = db.get_or_404(
                    Supplier,
                    int(request.form['supplier_id'])
                )

                if supplier.supplierProducts or supplier.reorderRecommendations:
                    raise ValueError(
                        'This supplier has linked products or reorder records. '
                        'Remove or resolve those records before deleting.'
                    )

                db.session.delete(supplier)
                flash('Supplier deleted successfully.', 'success')

            elif action in ('add_product', 'edit_product'):
                supplier = db.get_or_404(
                    Supplier,
                    int(request.form['supplier_id'])
                )

                product = db.get_or_404(
                    Product,
                    int(request.form['product_id'])
                )

                link = db.session.scalar(
                    db.select(SupplierProduct).where(
                        SupplierProduct.supplierId == supplier.supplierID,
                        SupplierProduct.productId == product.id
                    )
                )

                if action == 'add_product' and link:
                    raise ValueError(
                        'This product is already linked to the supplier.'
                    )

                if action == 'edit_product' and not link:
                    raise ValueError('Supplier product link not found.')

                cost = Decimal(request.form.get('unit_cost', '').strip())
                minimum = int(request.form.get('minimum_order_quantity', ''))
                lead = int(request.form.get('lead_time_days', ''))

                if (
                    not cost.is_finite()
                    or cost < 0
                    or cost > Decimal('99999999.99')
                    or cost.as_tuple().exponent < -2
                    or minimum < 1
                    or lead < 0
                ):
                    raise ValueError(
                        'Enter a valid cost (two decimal places), '
                        'minimum quantity, and lead time.'
                    )

                preferred = request.form.get('preferred') == 'on'

                if preferred:
                    other_links = db.session.scalars(
                        db.select(SupplierProduct).where(
                            SupplierProduct.productId == product.id
                        )
                    ).all()

                    for other in other_links:
                        other.isPrefered = False

                if not link:
                    link = SupplierProduct(
                        supplierId=supplier.supplierID,
                        productId=product.id
                    )

                link.unitCost = cost
                link.minimumOrderQuantity = minimum
                link.leadTimeDays = lead
                link.isPrefered = preferred
                link.lastPriceUpdate = datetime.now()

                db.session.add(link)
                flash('Supplier product saved.', 'success')

            elif action == 'remove_product':
                supplier_id = int(request.form['supplier_id'])
                product_id = int(request.form['product_id'])

                link = db.session.scalar(
                    db.select(SupplierProduct).where(
                        SupplierProduct.supplierId == supplier_id,
                        SupplierProduct.productId == product_id
                    )
                )

                if not link:
                    raise ValueError('Supplier product link not found.')

                db.session.delete(link)
                flash('Product removed from supplier.', 'success')

            else:
                raise ValueError('Unknown supplier action.')

            db.session.commit()

        except (ValueError, KeyError, InvalidOperation) as exc:
            db.session.rollback()
            flash(str(exc) or 'Invalid supplier information.', 'danger')

        except Exception:
            db.session.rollback()
            app.logger.exception('Supplier management save failed')
            flash(
                'Unable to save changes. Check the server log.',
                'danger'
            )

        return redirect(url_for('supplier_management'))

    # RETRIEVE SUPPLIERS
    suppliers = db.session.scalars(
        db.select(Supplier).order_by(Supplier.supplierName)
    ).all()

    # RETRIEVE PRODUCTS
    products = db.session.scalars(
        db.select(Product).order_by(Product.productName)
    ).all()

    # RETRIEVE SUPPLIER PRODUCT LINKS
    links = db.session.scalars(
        db.select(SupplierProduct).order_by(SupplierProduct.unitCost)
    ).all()

    # RETRIEVE INVENTORY
    inventory_rows = db.session.scalars(
        db.select(Inventory)
    ).all()

    # RETRIEVE REORDER RECOMMENDATIONS
    recommendations = db.session.scalars(
        db.select(ReorderRecommendation).where(
            ReorderRecommendation.status.in_(['pending', 'approved'])
        ).order_by(
            ReorderRecommendation.recommendedOrderDate
        )
    ).all()

    # GROUP PRODUCTS BY SUPPLIER
    links_by_supplier = {}
    comparisons = {}

    for link in links:
        links_by_supplier.setdefault(
            link.supplierId, []
        ).append(link)

        comparisons.setdefault(
            link.productId, []
        ).append(link)

    # ONLY COMPARE PRODUCTS WITH MULTIPLE SUPPLIERS
    comparisons = {
        product_id: offers
        for product_id, offers in comparisons.items()
        if len(offers) >= 2
    }

    # LOW STOCK ALERTS
    low_stock = [
        stock for stock in inventory_rows
        if stock.quantityOnHand <= stock.reorderThreshold
    ]

    # DUE REORDER RECOMMENDATIONS
    today = datetime.now().date()

    due_recommendations = [
        recommendation for recommendation in recommendations
        if recommendation.recommendedOrderDate.date() <= today
    ]

    return render_template(
        'supplier_management.html',
        suppliers=suppliers,
        products=products,
        links_by_supplier=links_by_supplier,
        comparisons=comparisons,
        low_stock=low_stock,
        recommendations=recommendations,
        due_recommendations=due_recommendations,
        today=today,
        linked_products=len(links)
    )



# ---------------------------------------------------------------------------
# TEMPORARY SEED DATA - remove this block (and the calls in __main__) once
# you no longer want the database rebuilt from scratch on startup.
# ---------------------------------------------------------------------------
SEED_USERS = [
    # (email, username, firstName, lastName, role)
    ("admin@example.com", "owner", "Ada", "Admin", "admin"),
    ("cashier@example.com", "cashier", "Casey", "Cashier", "cashier"),
]

SEED_PRODUCTS = [
    # (category, barcode, productName, sellingPrice, quantityOnHand, reorderThreshold, reorderQuantity)
    ("Dairy & Eggs", "012345678901", "Whole Milk 1 Gal",     "3.99", 40, 10, 30),
    ("Dairy & Eggs", "012345678902", "Large Eggs 12ct",      "4.29", 55, 15, 40),
    ("Bakery",       "012345678903", "White Bread Loaf",     "2.49", 35, 10, 30),
    ("Dairy & Eggs", "012345678904", "Butter Unsalted 1 lb", "4.99", 30,  8, 20),
    ("Dairy & Eggs", "012345678905", "Cheddar Cheese 8 oz",  "3.79", 28,  8, 20),
]


def seed_database():
    """Populate a freshly created database with starter users and products."""
    from decimal import Decimal

    password = os.environ.get('SEED_PASSWORD')
    if not password or len(password) < 12:
        raise SystemExit('Set SEED_PASSWORD (12+ characters) in your .env before starting the app.')

    for email, username, first_name, last_name, role in SEED_USERS:
        user = User(
            email=email,
            username=username,
            firstName=first_name,
            lastName=last_name,
            role=role
        )
        user.set_password(password)
        db.session.add(user)

    categories = {}
    for category, barcode, name, price, qty, threshold, reorder_qty in SEED_PRODUCTS:
        if category not in categories:
            categories[category] = Category(categoryName=category)

        product = Product(
            barcode=barcode,
            productName=name,
            sellingPrice=Decimal(price),
            taxRate=Decimal('0.0635'),
            category=categories[category]
        )
        product.inventory = Inventory(
            quantityOnHand=qty,
            reorderThreshold=threshold,
            reorderQuantity=reorder_qty
        )
        db.session.add(product)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        #db.drop_all()
        #print("All table were dropped")
        #db.create_all()
        #print("All tables were created")
        db.create_all()      # TEMPORARY: rebuild tables from the models
        #seed_database()      # TEMPORARY: insert starter data
        print("Tables created and database seeded")
    app.run(debug=True)
