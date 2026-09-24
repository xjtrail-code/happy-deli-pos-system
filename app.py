from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def home():
    return "<h1>Happy Deli POS</h1><p>POS & Inventory System</p>"


@app.route("/product-entry")
def product_entry():
    return render_template("product_entry.html")


if __name__ == "__main__":
    app.run(debug=True)