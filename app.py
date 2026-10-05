import os
import secrets
from datetime import timedelta
from functools import wraps

import click
from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///auth.sqlite3'),
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

db = SQLAlchemy(app)


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
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
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


@app.route('/admin-dashboard')
@login_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')


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
    message = None

    if request.method == 'POST':
        barcode = request.form['barcode'].strip()
        product_name = request.form['product_name'].strip()
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])

        # Check if the barcode is already in inventory
        existing_product = db.session.scalar(
            db.select(Product).where(Product.barcode == barcode)
        )

        if existing_product:
            # Product already exists - add to its quantity
            existing_product.quantity += quantity
            existing_product.price = price

            message = (
                f"{existing_product.name} was added successfully! "
                f"New quantity: {existing_product.quantity}"
            )

        else:
            # This is a brand-new product
            product = Product(
                barcode=barcode,
                name=product_name,
                price=price,
                quantity=quantity
            )

            db.session.add(product)

            message = f"{product_name} was added successfully!"

        db.session.commit()

    return render_template(
        'product_entry.html',
        message=message
    )

@app.route('/inventory')
@login_required('admin')
def inventory():
    products = db.session.scalars(db.select(Product)).all()
    return render_template('inventory.html', products=products)

@app.cli.command('init-db')
def init_db():
    """Create missing tables without deleting existing data."""
    db.create_all()
    click.echo('Database initialized.')


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


if __name__ == '__main__':
    app.run(debug=True)
