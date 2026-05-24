import os
import pandas as pd
from azure.storage.blob import BlobServiceClient
from sqlalchemy import create_engine, text
import urllib

# ===============================
# CONFIG
# ===============================

STORAGE_ACCOUNT = "omstd"
CONTAINER_NAME = "raw-data"

BLOB_KEY = os.environ.get("AZURE_BLOB_KEY")

SQL_SERVER = "otc-sql-server-01.database.windows.net"
SQL_DB = "otc_analytics_db"
SQL_USER = "sqladmin"
SQL_PASSWORD = os.environ.get("AZURE_SQL_PASSWORD")

if not BLOB_KEY:
    raise RuntimeError("AZURE_BLOB_KEY environment variable not set")

if not SQL_PASSWORD:
    raise RuntimeError("AZURE_SQL_PASSWORD environment variable not set")

# ===============================
# CONNECTIONS
# ===============================

blob_service = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.blob.core.windows.net",
    credential=BLOB_KEY
)

container_client = blob_service.get_container_client(CONTAINER_NAME)

params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DB};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PASSWORD}"
)

engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# ===============================
# EXTRACTION
# ===============================

def read_csv_from_blob(blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    csv_bytes = blob_client.download_blob().readall()
    return pd.read_csv(pd.io.common.BytesIO(csv_bytes))


# ===============================
# DATABASE CLEANUP (FK SAFE)
# ===============================

def clear_tables():
    print("Clearing tables in FK-safe order")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM payments"))
        conn.execute(text("DELETE FROM invoices"))
        conn.execute(text("DELETE FROM shipments"))
        conn.execute(text("DELETE FROM orders"))
        conn.execute(text("DELETE FROM customers"))

    print("All tables cleared")


# ===============================
# VALIDATION – CUSTOMERS
# ===============================

def validate_customers(df):
    errors = []

    # customer_id checks
    if df["customer_id"].isnull().any():
        errors.append("customer_id contains NULL values")

    if df["customer_id"].duplicated().any():
        errors.append("duplicate customer_id values found")

    # region check
    allowed_regions = ["North", "South", "East", "West"]
    if not df["region"].isin(allowed_regions).all():
        errors.append("invalid region values detected")

    # onboarding_date check
    df["onboarding_date"] = pd.to_datetime(df["onboarding_date"], errors="coerce")
    if df["onboarding_date"].isnull().any():
        errors.append("invalid onboarding_date values")

    if errors:
        raise ValueError(f"Customer validation failed: {errors}")

    return df

# ===============================
# VALIDATION – ORDERS
# ===============================

def validate_orders(df, customers_df):
    errors = []

    # order_id checks
    if df["order_id"].isnull().any():
        errors.append("order_id contains NULL values")

    if df["order_id"].duplicated().any():
        errors.append("duplicate order_id values found")

    # customer_id checks
    if df["customer_id"].isnull().any():
        errors.append("customer_id contains NULL values")

    # customer_id FK check
    if not df["customer_id"].isin(customers_df["customer_id"]).all():
        errors.append("customer_id present in orders but missing in customers")

    # order_date validity
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    if df["order_date"].isnull().any():
        errors.append("invalid order_date values")

    # promised_ship_date validity
    df["promised_ship_date"] = pd.to_datetime(df["promised_ship_date"], errors="coerce")

    invalid_promised = df[
        (df["order_status"] == "Completed") &
        (df["promised_ship_date"].isnull())
    ]

    if not invalid_promised.empty:
        errors.append("Completed orders missing promised_ship_date")

    # order_value check
    if (df["order_value"] <= 0).any():
        errors.append("order_value must be greater than 0")

    # order_status check
    allowed_status = ["Completed", "Cancelled"]
    if not df["order_status"].isin(allowed_status).all():
        errors.append("invalid order_status values detected")

    if errors:
        raise ValueError(f"Orders validation failed: {errors}")

    return df


# ===============================
# VALIDATION – SHIPMENTS
# ===============================

def validate_shipments(df, orders_df):
    errors = []

    # shipment_id checks
    if df["shipment_id"].isnull().any():
        errors.append("shipment_id contains NULL values")

    if df["shipment_id"].duplicated().any():
        errors.append("duplicate shipment_id values found")

    # order_id FK checks
    if df["order_id"].isnull().any():
        errors.append("order_id contains NULL values")

    if not df["order_id"].isin(orders_df["order_id"]).all():
        errors.append("order_id present in shipments but missing in orders")

    # ship_date validity check
    df["ship_date"] = pd.to_datetime(df["ship_date"], errors="coerce")
    if df["ship_date"].isnull().any():
        errors.append("invalid ship_date values")

    # delivery_date validity check
    df["delivery_date"] = pd.to_datetime(df["delivery_date"], errors="coerce")

    invalid_delivery = df[
        (df["shipment_status"] == "Delivered") &
        (df["delivery_date"].isnull())
    ]
    if not invalid_delivery.empty:
        errors.append("Delivered shipments missing delivery_date")

    # delivery_date must be >= ship_date
    invalid_dates = df[
        (df["delivery_date"].notnull()) &
        (df["delivery_date"] < df["ship_date"])
    ]
    if not invalid_dates.empty:
        errors.append("delivery_date earlier than ship_date")

    # normalize shipment_status
    df["shipment_status"] = df["shipment_status"].str.strip().str.title()

    status_mapping = {
        "Delivered": "Delivered",
        "Shipped": "Shipped",
        "In Transit": "In Transit",
        "Intransit": "In Transit",
        "Delayed": "In Transit",   # normalize delayed shipments
        "Cancelled": "Cancelled",
        "Canceled": "Cancelled"
    }

    df["shipment_status"] = df["shipment_status"].map(status_mapping)

    # shipment_status checks
    allowed_status = ["Shipped", "In Transit", "Delivered", "Cancelled"]
    if not df["shipment_status"].isin(allowed_status).all():
        errors.append("invalid shipment_status values detected")

    if errors:
        raise ValueError(f"Shipments validation failed: {errors}")

    return df

# ===============================
# VALIDATION – INVOICES
# ===============================

def validate_invoices(df, orders_df):
    errors = []

    # invoice_id checks
    if df["invoice_id"].isnull().any():
        errors.append("invoice_id contains NULL values")

    if df["invoice_id"].duplicated().any():
        errors.append("duplicate invoice_id values found")

    # order_id FK check
    if df["order_id"].isnull().any():
        errors.append("order_id contains NULL values")

    if not df["order_id"].isin(orders_df["order_id"]).all():
        errors.append("order_id present in invoices but missing in orders")

    # invoice_date validity
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    if df["invoice_date"].isnull().any():
        errors.append("invalid invoice_date values")

    # invoice_amount check
    if (df["invoice_amount"] <= 0).any():
        errors.append("invoice_amount must be greater than 0")

    # ===============================
    # invoice_status normalization
    # ===============================
    df["invoice_status"] = (
        df["invoice_status"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    status_mapping = {
        "issued": "Issued",
        "pending": "Pending",
        "paid": "Paid",
        "settled": "Paid",
        "unpaid": "Unpaid",
        "overdue": "Overdue",
        "partial": "Partial",
        "partially paid": "Partial"
    }

    df["invoice_status"] = df["invoice_status"].map(status_mapping)

    allowed_status = [
        "Issued",
        "Pending",
        "Paid",
        "Unpaid",
        "Partial",
        "Overdue"
    ]

    if not df["invoice_status"].isin(allowed_status).all():
        errors.append("invalid invoice_status values detected")

    if errors:
        raise ValueError(f"Invoices validation failed: {errors}")

    return df

# ===============================
# VALIDATION – PAYMENTS
# ===============================

def validate_payments(df, invoices_df):
    errors = []

    # payment_id checks
    if df["payment_id"].isnull().any():
        errors.append("payment_id contains NULL values")

    if df["payment_id"].duplicated().any():
        errors.append("duplicate payment_id values found")

    # invoice_id FK checks
    if df["invoice_id"].isnull().any():
        errors.append("invoice_id contains NULL values")

    if not df["invoice_id"].isin(invoices_df["invoice_id"]).all():
        errors.append("invoice_id present in payments but missing in invoices")

    # payment_date validity
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    if df["payment_date"].isnull().any():
        errors.append("invalid payment_date values")

    # payment_amount check
    if (df["payment_amount"] <= 0).any():
        errors.append("payment_amount must be greater than 0")

    # normalize payment_status
    df["payment_status"] = df["payment_status"].str.strip().str.title()

    status_mapping = {
        "Paid": "Paid",
        "Completed": "Paid",
        "Partial": "Partial",
        "Partially Paid": "Partial",
        "Pending": "Pending",
        "Failed": "Failed",
        "Cancelled": "Cancelled",
        "Canceled": "Cancelled"
    }

    df["payment_status"] = df["payment_status"].map(status_mapping)

    allowed_status = ["Paid", "Partial", "Pending", "Failed", "Cancelled"]
    if not df["payment_status"].isin(allowed_status).all():
        errors.append("invalid payment_status values detected")

    if errors:
        raise ValueError(f"Payments validation failed: {errors}")

    return df


# ===============================
# LOAD – CUSTOMERS
# ===============================

def load_customers():
    print("Reading customers_raw.csv from Blob Storage")
    df = read_csv_from_blob("customers_raw.csv")

    print("Validating customers data")
    df = validate_customers(df)

    print("Clearing existing customers table")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM customers"))

    print("Loading customers into Azure SQL")
    df.to_sql("customers", engine, if_exists="append", index=False)

    print("Customers load completed successfully")

# ===============================
# LOAD – ORDERS
# ===============================

def load_orders():
    # extract
    print("Reading orders_raw.csv from Blob Storage")
    orders_df = read_csv_from_blob("orders_raw.csv")

    # debug – inspect raw data
    print("Unique order_status values:")
    print(orders_df["order_status"].unique())

    print("Rows with invalid promised_ship_date:")
    print(orders_df[orders_df["promised_ship_date"].isnull()])

    # reference data for FK validation
    print("Reading customers table for FK validation")
    customers_df = pd.read_sql(
        "SELECT customer_id FROM customers",
        engine
    )

    # validate
    print("Validating orders data")
    orders_df = validate_orders(orders_df, customers_df)

    # load
    print("Loading orders into Azure SQL")
    orders_df.to_sql("orders", engine, if_exists="append", index=False)

    print("Orders load completed successfully")


# ===============================
# LOAD – SHIPMENTS
# ===============================

def load_shipments():
    # extract
    print("Reading shipments_raw.csv from Blob Storage")
    shipments_df = read_csv_from_blob("shipments_raw.csv")

    # DEBUG – mandatory inspection
    print("Unique shipment_status values:")
    print(shipments_df["shipment_status"].unique())

    print("Reading orders table for FK validation")
    orders_df = pd.read_sql(
        "SELECT order_id FROM orders",
        engine
    )

    # validate
    print("Validating shipments data")
    shipments_df = validate_shipments(shipments_df, orders_df)

    # load
    print("Loading shipments into Azure SQL")
    shipments_df.to_sql(
        "shipments",
        engine,
        if_exists="append",
        index=False
    )

    print("Shipments load completed successfully")

# ===============================
# LOAD – INVOICES
# ===============================

def load_invoices():
    print("Reading invoices_raw.csv from Blob Storage")
    invoices_df = read_csv_from_blob("invoices_raw.csv")

    print("Unique invoice_status values:")
    print(invoices_df["invoice_status"].unique())

    print("Reading orders table for FK validation")
    orders_df = pd.read_sql(
        "SELECT order_id FROM orders",
        engine
    )

    print("Validating invoices data")
    invoices_df = validate_invoices(invoices_df, orders_df)

    print("Loading invoices into Azure SQL")
    invoices_df.to_sql(
        "invoices",
        engine,
        if_exists="append",
        index=False
    )

    print("Invoices load completed successfully")

# ===============================
# LOAD – PAYMENTS
# ===============================

def load_payments():
    print("Reading payments_raw.csv from Blob Storage")
    payments_df = read_csv_from_blob("payments_raw.csv")

    print("Unique payment_status values:")
    print(payments_df["payment_status"].unique())

    print("Reading invoices table for FK validation")
    invoices_df = pd.read_sql(
        "SELECT invoice_id FROM invoices",
        engine
    )

    print("Validating payments data")
    payments_df = validate_payments(payments_df, invoices_df)

    print("Loading payments into Azure SQL")
    payments_df.to_sql("payments", engine, if_exists="append", index=False)

    print("Payments load completed successfully")


# ===============================
# MAIN
# ===============================

if __name__ == "__main__":
    clear_tables()
    load_customers()
    load_orders()
    load_shipments()
    load_invoices()
    load_payments()




