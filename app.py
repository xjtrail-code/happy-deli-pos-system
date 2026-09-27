import os
import secrets
from functools import wraps

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///happy_deli.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY to a long random value before starting the app.")
    db.init_app(app)

    @app.before_request
    def load_user():
        g.user = db.session.get(User, session["user_id"]) if "user_id" in session else None
        if g.user is None or not g.user.is_active:
            session.pop("user_id", None)
            g.user = None

    def allowed_roles(*roles):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if g.user is None:
                    return redirect(url_for("home"))
                if g.user.role not in roles:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    def valid_csrf():
        expected = session.get("csrf_token")
        supplied = request.form.get("csrf_token")
        return bool(expected and supplied) and secrets.compare_digest(expected, supplied)

    @app.route("/", methods=["GET", "POST"])
    def home():
        if request.method == "POST":
            if not valid_csrf():
                abort(400)
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = db.session.scalar(select(User).where(User.username == username))
            if user and user.is_active and check_password_hash(user.password_hash, password):
                session.clear()
                session["user_id"] = user.id
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("admin_dashboard" if user.role == "admin" else "pos"))
            flash("Invalid username or password.")
        elif g.user:
            return redirect(url_for("admin_dashboard" if g.user.role == "admin" else "pos"))
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return render_template("login.html")

    @app.post("/logout")
    @allowed_roles("admin", "cashier")
    def logout():
        if not valid_csrf():
            abort(400)
        session.clear()
        return redirect(url_for("home"))

    @app.route("/admin-dashboard")
    @allowed_roles("admin")
    def admin_dashboard():
        return render_template("admin_dashboard.html")

    @app.route("/pos")
    @allowed_roles("admin", "cashier")
    def pos():
        return render_template("pos.html")

    @app.route("/forgot-password")
    def forgot_password():
        return render_template("forgot_password.html")

    @app.route("/product-entry", methods=["GET", "POST"])
    @allowed_roles("admin")
    def product_entry():
        if request.method == "POST":
            abort(501, description="Product storage is not implemented yet.")
        return render_template("product_entry.html")

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", type=click.Choice(["admin", "cashier"]), required=True)
    @click.password_option()
    def create_user(username, role, password):
        username = username.strip()
        if not username or db.session.scalar(select(User).where(User.username == username)):
            raise click.ClickException("Username is empty or already exists.")
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role=role))
        db.session.commit()
        click.echo(f"Created {role} account: {username}")

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
