from flask import Flask, render_template, request

app = Flask(__name__)


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


# -------------------------
# RUN FLASK
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)