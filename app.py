from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Happy Deli POS</h1><p>POS & Inventory System</p>"

if __name__ == "__main__":
    app.run(debug=True)