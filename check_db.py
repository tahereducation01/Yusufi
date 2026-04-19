import os
import mysql.connector

# Load credentials from environment (or default to local XAMPP/Workbench settings)
db = mysql.connector.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_NAME", "safetyshop")
)

cur = db.cursor(dictionary=True)
cur.execute("SELECT name FROM categories")
print("Categories:", cur.fetchall())

cur.execute("SELECT id, name FROM products WHERE category = %s", ("Ear Plug",))
print("Products with Ear Plug:", cur.fetchall())

cur.close()
db.close()