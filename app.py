import os
from dotenv import load_dotenv


from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from models import db
from models import (User, Category, Product, Transaction, TransactionItem, 
                    Inventory, Supplier, SupplierProduct, InventoryAdjustment, 
                    DemandForecast, LowStockAlert, ReorderRecommendation)

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# -------------------------
# SIGN IN PAGE
# -------------------------
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/pos")
def pos():
    return render_template("pos.html")

# -------------------------
# FORGOT PASSWORD PAGE
# -------------------------
@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


# -------------------------
# PRODUCT ENTRY PAGE
# -------------------------
@app.route("/product-entry", methods=["GET", "POST"])
def product_entry():

    if request.method == "POST":

        barcode = request.form["barcode"]
        quantity = request.form["quantity"]

        print("Barcode:", barcode)
        print("Quantity:", quantity)

    return render_template("product_entry.html")

#--------------------------
# TESTING DATABASE CONNECTION
#--------------------------
@app.route("/test-db")
def test_db():
    try:
        # Attempt to connect to the database
        db.session.execute(db.text('SELECT 1'))
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {e}"



# -------------------------
# RUN FLASK
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        #db.drop_all()
        #print("All tables dropped successfully.")
        db.create_all()
        print("All tables created successfully.")    
    app.run(debug=True)