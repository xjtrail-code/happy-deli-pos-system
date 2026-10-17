import os
from dotenv import load_dotenv
import secrets
from pathlib import Path

from models import db
from models import (User, Category, Product, Transaction, TransactionItem, 
                    Inventory, Supplier, SupplierProduct, InventoryAdjustment, 
                    DemandForecast, LowStockAlert, ReorderRecommendation)
from datetime import date, timedelta
from functools import wraps

import click
from flask import Flask, abort, g, redirect, render_template, request, session, url_for
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


def login_required(role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('home'))
            if role is not None and g.user.role != role:
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
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        if not expected or not secrets.compare_digest(token, expected):
            abort(400, description='Invalid form token. Reload the page and try again.')


@app.route('/', methods=['GET', 'POST'])
def home():
    if g.user:
        return redirect(url_for('admin_dashboard' if g.user.role == 'admin' else 'pos'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        user = db.session.scalar(db.select(User).where(User.username == username))
        if user and user.isActive and user.check_password(request.form.get('password', '')):
            session.clear()
            session['user_id'] = user.id
            session.permanent = True
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'pos'))
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

    # Get today's completed transactions
    today = date.today()

    transactions = db.session.scalars(
        db.select(Transaction)
        .where(Transaction.status == 'completed')
        .where(Transaction.transactionDate >= datetime.combine(today, datetime.min.time()))
        .where(Transaction.transactionDate < datetime.combine(
            date.fromordinal(today.toordinal() + 1),
            datetime.min.time()
        ))
    ).all()

    # Calculate today's totals
    todays_sales = round(float(sum(t.totalAmount for t in transactions)), 2)
    todays_transactions = len(transactions)
    start_of_day = datetime.combine(
        today, datetime.min.time()
    )
    end_of_day = start_of_day + timedelta(days=1)

    '''# TEMPORARY DEBUGGING
    print("Dashboard date:", today)

    all_sales = db.session.scalars(
        db.select(Sale)
    ).all()

    print("All sales:", [
        (sale.id, sale.created_at, sale.total)
        for sale in all_sales
    ])

    # Retrieve today's sales
    sales = db.session.scalars(
        db.select(Sale)
        .where(Sale.created_at >= start_of_day)
        .where(Sale.created_at < end_of_day)
    ).all()

    # Calculate today's totals
    todays_sales = round(
        sum(sale.total for sale in sales), 2
    )
    todays_transactions = len(sales)
'''
    # Count products at or below their reorder threshold
    low_stock_alerts = db.session.scalar(
        db.select(db.func.count(Inventory.id))
        .where(Inventory.quantityOnHand <= Inventory.reorderThreshold)
    ) or 0

    # Send data to dashboard
    return render_template(
        'admin_dashboard.html',
        todays_sales=todays_sales,
        todays_transactions=todays_transactions,
        low_stock_alerts=low_stock_alerts,
        profit_margin=None
    )


@app.route('/pos')
@login_required()
def pos():
    return render_template('pos.html')


@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/product-entry', methods=['GET', 'POST'])
@login_required('admin')
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
@login_required('admin')
def inventory():
    products = db.session.scalars(db.select(Product).where(Product.isActive.is_(True)).order_by(Product.productName)).all()
    return render_template('inventory.html', products=products)


@app.post('/inventory/receive')
@login_required('admin')
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
@login_required()
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
    if not username or len(username) > 80:
        raise click.ClickException('Username must be between 1 and 80 characters.')
    if len(password) < 12:
        raise click.ClickException('Password must be at least 12 characters.')
    if db.session.scalar(db.select(User).where(User.username == username)):
        raise click.ClickException('Username already exists.')
    db.session.add(User(username=username, role=role, password_hash=generate_password_hash(password)))
    db.session.commit()
    click.echo(f'Created {role} account: {username}')



@app.post('/complete-sale')
@login_required()
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
@login_required('admin')
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
@app.route('/employee-management')
@login_required('admin')
def employee_management():
    return render_template('employee_management.html')


# SUPPLIER MANAGEMENT
@app.route('/supplier-management')
@login_required('admin')
def supplier_management():
    return render_template('supplier_management.html')


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