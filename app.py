#!/usr/bin/env python3
"""
Basic Shop
Based on Zero-Fees Payment Collection System
"""

from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    url_for,
    redirect,
    session,
    send_from_directory,
)
from flask_cors import CORS
import requests
import os
import json
import logging
import secrets
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # take environment variables


# Parse required environment variables from .env.example
def get_required_env_vars():
    required_vars = []
    try:
        with open(".env.example", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    var_name = line.split("=")[0]
                    required_vars.append(var_name)
    except FileNotFoundError:
        print("ERROR: .env.example file not found")
        exit(1)
    return required_vars


# Check for missing environment variables
required_vars = get_required_env_vars()
missing_vars = []
for var in required_vars:
    if os.getenv(var) is None:
        missing_vars.append(var)

if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print(
        "Please check your .env file and ensure all variables from .env.example are set"
    )
    exit(1)

log = logging.getLogger()
handler = logging.StreamHandler()  # sys.stderr will be used by default

PYTHON_LOG_LEVEL = os.getenv("PYTHON_LOG_LEVEL", logging.DEBUG)
PERSONAL_ACCESS_TOKEN = os.getenv("PERSONAL_ACCESS_TOKEN")
BANK_ACCOUNT_ID = os.getenv("BANK_ACCOUNT_ID")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER")
BANK_ACCOUNT_SORTCODE = os.getenv("BANK_ACCOUNT_SORTCODE")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
SUPPORT_CONTACT_NUMBER = os.getenv("SUPPORT_CONTACT_NUMBER")
SECRET_KEY = os.getenv("SECRET_KEY")
SERVER_NAME = os.getenv("SERVER_NAME")
GOOGLE_TAG_ACCOUNT_ID = os.getenv("GOOGLE_TAG_ACCOUNT_ID")
STATIC_ROOT_DIR = os.getenv("STATIC_ROOT_DIR")

# Setup logging
log.setLevel(PYTHON_LOG_LEVEL)
handler.setLevel(PYTHON_LOG_LEVEL)
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)-8s %(message)s %(funcName)s %(pathname)s:%(lineno)d"  # noqa: E501
    )
)
log.addHandler(handler)

headers = {
    "Authorization": PERSONAL_ACCESS_TOKEN,
    "accept": "application/json",
}
# End Setup logging


app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SERVER_NAME"] = SERVER_NAME
CORS(app)


@app.context_processor
def inject_global_vars():
    """Inject global variables into all templates"""
    return dict(
        GOOGLE_TAG_ACCOUNT_ID=GOOGLE_TAG_ACCOUNT_ID,
        SUPPORT_EMAIL=SUPPORT_EMAIL,
        SUPPORT_CONTACT_NUMBER=SUPPORT_CONTACT_NUMBER,
        SERVER_NAME=SERVER_NAME,
    )


def generate_payment_reference(length=8):
    """Generate a human-friendly payment reference avoiding confusing characters"""
    # Avoid confusing characters: 0, O, I, 1, S, 5, Z, 2
    safe_chars = "ABCDEFGHJKLMNPQRTUVWXY346789"
    return "".join(secrets.choice(safe_chars) for _ in range(length))


# Jinja template filter for price formatting
@app.template_filter("price_format")
def price_format(value_in_pence):
    """Convert pence to pounds and format as currency"""
    if value_in_pence is None:
        return "N/A"
    try:
        pounds = float(value_in_pence) / 100
        return f"{pounds:.2f}"
    except (ValueError, TypeError):
        return "N/A"


@app.route("/pay")
def pay():
    # Generate payment reference if not already in session
    if "expected_payment_reference" not in session:
        session["expected_payment_reference"] = generate_payment_reference()

    return render_template(
        "pay.html",
        BANK_ACCOUNT_NAME=BANK_ACCOUNT_NAME,
        BANK_ACCOUNT_NUMBER=BANK_ACCOUNT_NUMBER,
        BANK_ACCOUNT_SORTCODE=BANK_ACCOUNT_SORTCODE,
        SUPPORT_EMAIL=SUPPORT_EMAIL,
        SUPPORT_CONTACT_NUMBER=SUPPORT_CONTACT_NUMBER,
        SERVER_NAME=SERVER_NAME,
        expected_payment_reference=session["expected_payment_reference"],
    )


@app.route("/")
def index():
    expected_payment_reference = None
    if request.args.get("expected_payment_reference"):
        expected_payment_reference = request.args.get(
            "expected_payment_reference"
        )  # noqa: E501

    # Get product price from environment variable
    product_code = "T253X7002T0C101"  # Current product code
    price_env_var = f"PRODUCT_SELL_PRICE_{product_code}"
    sell_price = os.getenv(price_env_var)

    return render_template(
        "products.html",
        expected_payment_reference=expected_payment_reference,
        sell_price=sell_price,
    )


@app.route("/address", methods=["GET", "POST"])
def get_address():
    if request.method == "POST":
        # Get form data
        email = request.form.get("email")
        addr_line_1 = request.form.get("addr_line_1")
        addr_line_2 = request.form.get("addr_line_2")
        city = request.form.get("city")
        postcode = request.form.get("postcode")
        product_code = request.form.get("product_code")

        # Get product price from environment variable
        price_env_var = f"PRODUCT_SELL_PRICE_{product_code}"
        sell_price = os.getenv(price_env_var)

        # Generate payment reference if not already in session
        if "expected_payment_reference" not in session:
            session["expected_payment_reference"] = generate_payment_reference()

        # Create address data object
        address_data = {
            "email": email,
            "addr_line_1": addr_line_1,
            "addr_line_2": addr_line_2,
            "city": city,
            "postcode": postcode,
            "product_code": product_code,
            "sell_price": sell_price,
            "payment_status": "NOT_PAID",
            "created_at": datetime.now().isoformat(),
            "expected_payment_reference": session["expected_payment_reference"],
        }

        try:
            # Create customer_data directory if it doesn't exist
            os.makedirs("customer_data", exist_ok=True)

            # Save to JSON file using timestamp as filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"customer_data/{timestamp}.json"

            with open(filename, "w") as f:
                json.dump(address_data, f, indent=2)

            log.info(f"Address saved for customer: {email}")

            # Only redirect to payment if data was successfully saved
            return redirect(url_for("pay", amount=sell_price))

        except Exception as e:
            log.error(f"Failed to save customer data: {e}")
            # Return to form with error message
            return render_template(
                "address.html", error="Failed to save your details. Please try again."
            )
    return render_template("address.html")


@app.route("/check-payment-status")
def check_payment_status() -> bool:
    bool_located_payment_reference = False
    expected_payment_reference = session.get("expected_payment_reference")
    assert expected_payment_reference is not None

    # startDate = "yyyy-mm-dd"
    # endDate = "yyyy-mm-dd"
    todayFormatted = datetime.now().strftime("%Y-%m-%d")
    minTransactionTimestamp = f"{todayFormatted}T00:00:00.000Z"
    maxTransactionTimestamp = f"{todayFormatted}T23:59:59.000Z"
    host = f"https://api.starlingbank.com/api/v2/feed/account/{BANK_ACCOUNT_ID}/settled-transactions-between"  # noqa: E501
    host += f"?minTransactionTimestamp={minTransactionTimestamp}"
    host += f"&maxTransactionTimestamp={maxTransactionTimestamp}"

    headers["accept"] = "application/json"
    req = requests.get(host, headers=headers)
    resp = req.json()

    for feedItem in resp["feedItems"]:
        bank_transaction_reference = feedItem.get("reference")
        log.info(
            f'Looking for payment reference "{expected_payment_reference}"'
        )  # noqa: E501
        if bank_transaction_reference == expected_payment_reference:
            bool_located_payment_reference = True
            # Store payment timestamp in session
            session["payment_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session["payment_amount"] = request.args.get("amount")
            log.info(
                "Found matching payment reference "
                f'"{expected_payment_reference}"'  # noqa: E501
            )  # noqa E501

    resp = {"msg": {"located_payment_status": bool_located_payment_reference}}
    return jsonify(resp)


@app.route("/thank-you")
def thank_you():
    return render_template(
        "thank-you.html",
        timestamp=session.get("payment_timestamp"),
        amount=session.get("payment_amount"),
        SUPPORT_EMAIL=SUPPORT_EMAIL,
        SUPPORT_CONTACT_NUMBER=SUPPORT_CONTACT_NUMBER,
    )


@app.route("/returns")
def returns():
    return render_template("returns.html")


@app.route("/<path:filename>")
def custom_static(filename):
    assert filename != '.env'
    return send_from_directory("/home/karma/shop/static/pages/", filename)
