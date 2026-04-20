import os
import mysql.connector 
from datetime import datetime
from functools import wraps

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
# SESSION_SECRET is set in Replit Secrets; falls back to dev value
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-prod")

BASE_DIR = os.path.dirname(__file__)
DATABASE = os.path.join(BASE_DIR, "safetyshop.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "safetyshop")
        )
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().cursor(dictionary=True)
    cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    cur.close()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Initialise & seed database
# ---------------------------------------------------------------------------

def init_db():
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    table_queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin TINYINT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS brands (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(255) NOT NULL,
            brand VARCHAR(255),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            stock_quantity INT NOT NULL DEFAULT 0,
            image_url TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            full_name VARCHAR(255) NOT NULL,
            address TEXT NOT NULL,
            phone VARCHAR(50) NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )""",
        """CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            price_at_purchase DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )""",
        """CREATE TABLE IF NOT EXISTS bids (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            user_id INT,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            offered_price DECIMAL(10,2),
            note TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )""",
        """CREATE TABLE IF NOT EXISTS contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'Unread',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )"""
    ]

    for q in table_queries:
        cur.execute(q)
    db.commit()

    # Seed products only if the table is empty
    cur.execute("SELECT COUNT(*) as count FROM products")
    count = cur.fetchone()['count']
    
    if count == 0:
        products = [
            ("Helmet", "Karam", "Karam Safety Helmet PN521", "High impact ABS material with 6-point plastic suspension.", 145.00, 150, "https://images.unsplash.com/photo-1504307651254-35680f356dfd?q=80&w=800&auto=format&fit=crop"),
            ("Jacket", "Udyogi", "Reflective Safety Jacket", "High visibility green reflective jacket for night construction.", 120.00, 200, "https://images.unsplash.com/photo-1614177487786-45dfbe94e57b?q=80&w=800&auto=format&fit=crop"),
            ("Engineering Hand Gloves", "Allen Cooper", "Cotton Knitted Hand Gloves", "Seamless knitted cotton gloves for general handling.", 35.00, 500, "https://images.unsplash.com/photo-1607619056574-7b8d3ee536b2?q=80&w=800&auto=format&fit=crop"),
            ("Goggles", "3M", "3M Chemical Splash Goggles", "Polycarbonate lens, anti-fog for lab and chemical use.", 110.00, 300, "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=800&auto=format&fit=crop"),
            ("Glass", "Karam", "Clear Safety Spectacles", "Clear safety glass for basic eye protection and grinding work.", 45.00, 400, "https://images.unsplash.com/photo-1572630534839-2b84eb4db789?q=80&w=800&auto=format&fit=crop"),
            ("Ear Plug", "3M", "3M Corded Ear Plugs", "Polyurethane foam, noise reduction.", 15.00, 1000, "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?q=80&w=800&auto=format&fit=crop"),
            ("Mask", "Venus", "Venus N95 Particulate Mask", "NIOSH approved N95 particulate respirator.", 65.00, 500, "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?q=80&w=800&auto=format&fit=crop"),
            ("Shoes", "Allen Cooper", "Steel Toe Safety Shoes", "Steel toe, oil and acid resistant slip-proof sole.", 1250.00, 80, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=800&auto=format&fit=crop"),
            ("Apron", "Udyogi", "PVC Heavy Duty Apron", "Chemical and splash resistant PVC apron for industrial use.", 180.00, 60, "https://images.unsplash.com/photo-1583337222485-6111e138a202?q=80&w=800&auto=format&fit=crop"),
            ("Fire Extinguisher", "Safex", "ABC Powder Fire Extinguisher", "6kg ABC dry powder extinguisher, ISI marked.", 1150.00, 40, "https://images.unsplash.com/photo-1563212036-7c152ce8a35e?q=80&w=800&auto=format&fit=crop")
        ]
        cur.executemany(
            "INSERT INTO products (category, brand, name, description, price, stock_quantity, image_url) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            products,
        )
        db.commit()

    # Seed category and brand lookup tables
    cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND TRIM(category) <> ''")
    categories = [row['category'] for row in cur.fetchall()]
    for category_name in categories:
        cur.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", [category_name])

    cur.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND TRIM(brand) <> ''")
    brands = [row['brand'] for row in cur.fetchall()]
    for brand_name in brands:
        cur.execute("INSERT IGNORE INTO brands (name) VALUES (%s)", [brand_name])

    # Create a default admin user if none exists
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@safetyshop.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    cur.execute("SELECT id FROM users WHERE email = %s", [admin_email])
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (name, email, password_hash, is_admin) VALUES (%s, %s, %s, 1)",
            ["Admin", admin_email, generate_password_hash(admin_password)],
        )

    db.commit()
    cur.close()

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        user = query_db("SELECT is_admin FROM users WHERE id = %s", [session["user_id"]], one=True)
        if not user or user["is_admin"] != 1:
            flash("Admin access is required to view that page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_image_file(image_file):
    if image_file and image_file.filename and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        unique_name = f"{int(datetime.utcnow().timestamp())}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
        image_file.save(file_path)
        return url_for("static", filename=f"uploads/{unique_name}")
    return None


# ---------------------------------------------------------------------------
# Cart helpers  (stored in Flask session)
# ---------------------------------------------------------------------------

def get_cart():
    return session.get("cart", {})


def cart_count():
    return sum(item["qty"] for item in get_cart().values())


def cart_total():
    return sum(item["qty"] * item["price"] for item in get_cart().values())


app.jinja_env.globals["cart_count"] = cart_count
app.jinja_env.globals["cart_total"] = cart_total


@app.context_processor
def inject_nav_data():
    categories = query_db("SELECT name AS category FROM categories ORDER BY name")
    brands = query_db("SELECT name AS brand FROM brands ORDER BY name")
    return dict(nav_categories=categories, nav_brands=brands)


# ---------------------------------------------------------------------------
# Routes - Home
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    # Fetch category names along with the image of the first product in that category
    categories = query_db("""
        SELECT c.name AS category,
               (SELECT p.image_url FROM products p WHERE p.category = c.name LIMIT 1) AS image_url
        FROM categories c 
        ORDER BY c.name
    """)
    brands = query_db("SELECT name AS brand FROM brands ORDER BY name")
    return render_template("index.html", categories=categories, brands=brands)


@app.route("/brand/<brand_name>")
def brand(brand_name):
    products = query_db(
        "SELECT * FROM products WHERE brand = %s ORDER BY name",
        [brand_name],
    )
    categories = query_db("SELECT name AS category FROM categories ORDER BY name")
    return render_template(
        "brand.html",
        products=products,
        brand_name=brand_name,
        categories=categories,
    )


# ---------------------------------------------------------------------------
# Routes - Category
# ---------------------------------------------------------------------------

@app.route("/category/<category_name>")
def category(category_name):
    print(f"Category name: {repr(category_name)}")
    products = query_db(
        "SELECT * FROM products WHERE category = %s ORDER BY name",
        [category_name],
    )
    print(f"Products found: {len(products)}")
    if products:
        print(f"First product: {dict(products[0])}")
    categories = query_db("SELECT name AS category FROM categories ORDER BY name")
    print(f"Categories found: {len(categories)}")
    return render_template(
        "category.html",
        products=products,
        category_name=category_name,
        categories=categories,
    )


@app.route("/brands")
def brands_list():
    brands = query_db("SELECT name AS brand FROM brands ORDER BY name")
    return render_template("brands.html", brands=brands)


@app.route("/categories")
def categories_list():
    categories = query_db("""
        SELECT c.name AS category,
               (SELECT p.image_url FROM products p WHERE p.category = c.name LIMIT 1) AS image_url
        FROM categories c 
        ORDER BY c.name
    """)
    return render_template("categories.html", categories=categories)


@app.route("/blogs")
def blogs():
    return render_template("blogs.html")


@app.route("/flash-sale")
def flash_sale():
    products = query_db("SELECT * FROM products WHERE price <= 120 ORDER BY price")
    return render_template("flash_sale.html", products=products)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("search.html", query="", products=[], categories=[])

    # Search products by name, description, category, brand
    products = query_db("""
        SELECT * FROM products
        WHERE name LIKE %s OR description LIKE %s OR category LIKE %s OR brand LIKE %s
        ORDER BY name
    """, [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])

    # Search categories
    categories = query_db("""
        SELECT DISTINCT category FROM products
        WHERE category LIKE %s
        ORDER BY category
    """, [f"%{query}%"])

    return render_template("search.html", query=query, products=products, categories=categories)


# ---------------------------------------------------------------------------
# Routes - Product Detail
# ---------------------------------------------------------------------------

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = query_db("SELECT * FROM products WHERE id = %s", [product_id], one=True)
    if product is None:
        flash("Product not found.", "danger")
        return redirect(url_for("index"))

    current_user = None
    if "user_id" in session:
        current_user = query_db("SELECT name, email FROM users WHERE id = %s", [session["user_id"]], one=True)

    return render_template("product_detail.html", product=product, current_user=current_user)


# ---------------------------------------------------------------------------
# Routes - Cart
# ---------------------------------------------------------------------------

@app.route("/cart")
def cart():
    cart = get_cart()
    items = []
    for pid, info in cart.items():
        items.append({
            "id": pid,
            "name": info["name"],
            "price": info["price"],
            "qty": info["qty"],
            "subtotal": info["qty"] * info["price"],
            "image_url": info.get("image_url", ""),
            "category": info.get("category", ""),
        })
    total = cart_total()
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = query_db("SELECT * FROM products WHERE id = %s", [product_id], one=True)
    if product is None:
        return jsonify({"success": False, "message": "Product not found"}), 404

    qty = int(request.form.get("quantity", 1))
    cart = session.get("cart", {})
    pid = str(product_id)
    if pid in cart:
        cart[pid]["qty"] += qty
    else:
        cart[pid] = {
            "name": product["name"],
            "price": product["price"],
            "qty": qty,
            "image_url": product["image_url"],
            "category": product["category"],
        }
    session["cart"] = cart
    session.modified = True
    flash(f'"{product["name"]}" added to cart.', "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/remove/<product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(product_id, None)
    session["cart"] = cart
    session.modified = True
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/cart/update", methods=["POST"])
def update_cart():
    """AJAX endpoint - update quantity for a single item."""
    product_id = request.form.get("product_id")
    qty = int(request.form.get("quantity", 1))
    cart = session.get("cart", {})
    if product_id in cart:
        if qty <= 0:
            cart.pop(product_id)
        else:
            cart[product_id]["qty"] = qty
    session["cart"] = cart
    session.modified = True

    items_total = cart_total()
    return jsonify({"success": True, "cart_total": round(items_total, 2), "cart_count": cart_count()})


# ---------------------------------------------------------------------------
# Routes - Checkout
# ---------------------------------------------------------------------------

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = get_cart()
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()

        if not (full_name and address and phone):
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("checkout"))

        total = cart_total()
        user_id = session.get("user_id")

        order_id = execute_db(
            "INSERT INTO orders (user_id, full_name, address, phone, total_amount, status) VALUES (%s,%s,%s,%s,%s,%s)",
            [user_id, full_name, address, phone, total, "Confirmed"],
        )

        for pid, info in cart.items():
            execute_db(
                "INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase) VALUES (%s,%s,%s,%s)",
                [order_id, int(pid), info["qty"], info["price"]],
            )
            # Decrement stock
            execute_db(
                "UPDATE products SET stock_quantity = GREATEST(0, stock_quantity - %s) WHERE id = %s",
                [info["qty"], int(pid)],
            )

        session.pop("cart", None)
        flash(f"Order #{order_id} placed successfully! Thank you, {full_name}.", "success")
        return redirect(url_for("order_confirmation", order_id=order_id))

    items = []
    for pid, info in cart.items():
        items.append({
            "id": pid,
            "name": info["name"],
            "price": info["price"],
            "qty": info["qty"],
            "subtotal": info["qty"] * info["price"],
        })
    total = cart_total()
    return render_template("checkout.html", items=items, total=total)


@app.route("/order/confirmation/<int:order_id>")
def order_confirmation(order_id):
    order = query_db("SELECT * FROM orders WHERE id = %s", [order_id], one=True)
    return render_template("order_confirmation.html", order=order)


# ---------------------------------------------------------------------------
# Routes - Auth
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not (name and email and password):
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        existing = query_db("SELECT id FROM users WHERE email = %s", [email], one=True)
        if existing:
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        pw_hash = generate_password_hash(password)
        user_id = execute_db(
            "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)",
            [name, email, pw_hash],
        )
        session["user_id"] = user_id
        session["user_name"] = name
        session["is_admin"] = 0
        flash(f"Welcome, {name}! Your account has been created.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query_db("SELECT * FROM users WHERE email = %s", [email], one=True)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["is_admin"] = user["is_admin"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("is_admin", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = query_db("SELECT * FROM users WHERE id = ?", [user_id], one=True)
    orders = query_db(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        [user_id],
    )
    orders_with_items = []
    for order in orders:
        items = query_db(
            """SELECT oi.*, p.name as product_name
               FROM order_items oi JOIN products p ON oi.product_id = p.id
               WHERE oi.order_id = ?""",
            [order["id"]],
        )
        orders_with_items.append({"order": order, "items": items})
    return render_template("dashboard.html", user=user, orders=orders_with_items)


# ---------------------------------------------------------------------------
# Admin routes

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_db("SELECT * FROM users WHERE email = ? AND is_admin = 1", [email], one=True)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["is_admin"] = 1
            flash("Welcome back, admin!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
        return redirect(url_for("admin_login"))
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("is_admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "products": query_db("SELECT COUNT(*) AS count FROM products", one=True)["count"],
        "orders": query_db("SELECT COUNT(*) AS count FROM orders", one=True)["count"],
        "bids": query_db("SELECT COUNT(*) AS count FROM bids", one=True)["count"],
        "brands": query_db("SELECT COUNT(*) AS count FROM brands", one=True)["count"],
        "categories": query_db("SELECT COUNT(*) AS count FROM categories", one=True)["count"],
    }
    recent_orders = query_db(
        "SELECT o.*, u.name AS customer_name FROM orders o LEFT JOIN users u ON u.id = o.user_id ORDER BY created_at DESC LIMIT 5"
    )
    recent_bids = query_db(
        "SELECT b.*, p.name AS product_name FROM bids b LEFT JOIN products p ON p.id = b.product_id ORDER BY created_at DESC LIMIT 5"
    )
    return render_template("admin/dashboard.html", stats=stats, recent_orders=recent_orders, recent_bids=recent_bids)


@app.route("/admin/brands")
@admin_required
def admin_brands():
    brands = query_db("SELECT * FROM brands ORDER BY name")
    return render_template("admin/brands.html", brands=brands)


@app.route("/admin/brands/new", methods=["GET", "POST"])
@admin_required
def admin_brand_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Brand name is required.", "danger")
            return redirect(url_for("admin_brand_new"))
        execute_db("INSERT IGNORE INTO brands (name, description) VALUES (%s, %s)", [name, description])
        flash("Brand created successfully.", "success")
        return redirect(url_for("admin_brands"))
    return render_template("admin/brand_form.html", action="Create", brand=None)


@app.route("/admin/brands/<int:brand_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_brand_edit(brand_id):
    brand = query_db("SELECT * FROM brands WHERE id = ?", [brand_id], one=True)
    if brand is None:
        flash("Brand not found.", "danger")
        return redirect(url_for("admin_brands"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Brand name is required.", "danger")
            return redirect(url_for("admin_brand_edit", brand_id=brand_id))
        execute_db("UPDATE brands SET name = %s, description = %s WHERE id = %s", [name, description, brand_id])
        execute_db("UPDATE products SET brand = %s WHERE brand = %s", [name, brand["name"]])
        flash("Brand updated successfully.", "success")
        return redirect(url_for("admin_brands"))
    return render_template("admin/brand_form.html", action="Edit", brand=brand)


@app.route("/admin/brands/<int:brand_id>/delete", methods=["POST"])
@admin_required
def admin_brand_delete(brand_id):
    brand = query_db("SELECT * FROM brands WHERE id = %s", [brand_id], one=True)
    if brand:
        execute_db("DELETE FROM brands WHERE id = %s", [brand_id])
        execute_db("UPDATE products SET brand = NULL WHERE brand = %s", [brand["name"]])
        flash("Brand deleted and linked products cleared.", "success")
    else:
        flash("Brand not found.", "danger")
    return redirect(url_for("admin_brands"))


@app.route("/admin/categories")
@admin_required
def admin_categories():
    categories = query_db("SELECT * FROM categories ORDER BY name")
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/new", methods=["GET", "POST"])
@admin_required
def admin_category_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Category name is required.", "danger")
            return redirect(url_for("admin_category_new"))
        execute_db("INSERT IGNORE INTO categories (name, description) VALUES (%s, %s)", [name, description])
        flash("Category created successfully.", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/category_form.html", action="Create", category=None)


@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_category_edit(category_id):
    category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], one=True)
    if category is None:
        flash("Category not found.", "danger")
        return redirect(url_for("admin_categories"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Category name is required.", "danger")
            return redirect(url_for("admin_category_edit", category_id=category_id))
        execute_db("UPDATE categories SET name = %s, description = %s WHERE id = %s", [name, description, category_id])
        execute_db("UPDATE products SET category = %s WHERE category = %s", [name, category["name"]])
        flash("Category updated successfully.", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/category_form.html", action="Edit", category=category)


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_category_delete(category_id):
    category = query_db("SELECT * FROM categories WHERE id = %s", [category_id], one=True)
    if category:
        execute_db("DELETE FROM categories WHERE id = %s", [category_id])
        execute_db("INSERT IGNORE INTO categories (name) VALUES (%s)", ["Uncategorized"])
        execute_db("UPDATE products SET category = 'Uncategorized' WHERE category = %s", [category["name"]])
        flash("Category deleted. Products have been moved to Uncategorized.", "success")
    else:
        flash("Category not found.", "danger")
    return redirect(url_for("admin_categories"))


@app.route("/admin/products")
@admin_required
def admin_products():
    products = query_db("SELECT * FROM products ORDER BY name")
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    categories = query_db("SELECT * FROM categories ORDER BY name")
    brands = query_db("SELECT * FROM brands ORDER BY name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        price = request.form.get("price", "").strip()
        stock_quantity = request.form.get("stock_quantity", 0)
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        image_file = request.files.get("image_file")
        upload_url = save_image_file(image_file)
        if upload_url:
            image_url = upload_url
        if not (name and category and price):
            flash("Name, category, and price are required.", "danger")
            return redirect(url_for("admin_product_new"))
        execute_db(
            "INSERT INTO products (category, brand, name, description, price, stock_quantity, image_url) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [category, brand, name, description, float(price), int(stock_quantity), image_url],
        )
        execute_db("INSERT IGNORE INTO categories (name) VALUES (%s)", [category])
        execute_db("INSERT IGNORE INTO brands (name) VALUES (%s)", [brand])
        flash("Product created successfully.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", action="Create", product=None, categories=categories, brands=brands)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = query_db("SELECT * FROM products WHERE id = %s", [product_id], one=True)
    if product is None:
        flash("Product not found.", "danger")
        return redirect(url_for("admin_products"))
    categories = query_db("SELECT * FROM categories ORDER BY name")
    brands = query_db("SELECT * FROM brands ORDER BY name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        price = request.form.get("price", "").strip()
        stock_quantity = request.form.get("stock_quantity", 0)
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        image_file = request.files.get("image_file")
        upload_url = save_image_file(image_file)
        if upload_url:
            image_url = upload_url
        if not (name and category and price):
            flash("Name, category, and price are required.", "danger")
            return redirect(url_for("admin_product_edit", product_id=product_id))
        execute_db(
            "UPDATE products SET category = %s, brand = %s, name = %s, description = %s, price = %s, stock_quantity = %s, image_url = %s WHERE id = %s",
            [category, brand, name, description, float(price), int(stock_quantity), image_url, product_id],
        )
        execute_db("INSERT IGNORE INTO categories (name) VALUES (%s)", [category])
        execute_db("INSERT IGNORE INTO brands (name) VALUES (%s)", [brand])
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", action="Edit", product=product, categories=categories, brands=brands)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_product_delete(product_id):
    product = query_db("SELECT * FROM products WHERE id = %s", [product_id], one=True)
    if product:
        execute_db("DELETE FROM products WHERE id = %s", [product_id])
        flash("Product deleted successfully.", "success")
    else:
        flash("Product not found.", "danger")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = query_db(
        "SELECT o.*, u.name AS customer_name, u.email AS customer_email FROM orders o LEFT JOIN users u ON u.id = o.user_id ORDER BY created_at DESC"
    )
    orders_with_items = []
    for order in orders:
        items = query_db(
            "SELECT oi.*, p.name AS product_name FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?",
            [order["id"]],
        )
        orders_with_items.append({"order": order, "items": items})
    return render_template("admin/orders.html", orders=orders_with_items)


@app.route("/admin/bids")
@admin_required
def admin_bids():
    bids = query_db(
        "SELECT b.*, p.name AS product_name, u.name AS user_name, u.email AS user_email FROM bids b LEFT JOIN products p ON p.id = b.product_id LEFT JOIN users u ON u.id = b.user_id ORDER BY created_at DESC"
    )
    return render_template("admin/bids.html", bids=bids)


@app.route("/admin/bids/<int:bid_id>/status", methods=["POST"])
@admin_required
def admin_bid_status(bid_id):
    status = request.form.get("status", "Pending")
    execute_db("UPDATE bids SET status = ? WHERE id = ?", [status, bid_id])
    flash("Bid status updated.", "success")
    return redirect(url_for("admin_bids"))


# ---------------------------------------------------------------------------
# Routes - Bid (stub - records interest)
# ---------------------------------------------------------------------------

@app.route("/bid/<int:product_id>", methods=["POST"])
def bid(product_id):
    product = query_db("SELECT name FROM products WHERE id = ?", [product_id], one=True)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("index"))

    bid_name = request.form.get("bid_name", "").strip()
    bid_email = request.form.get("bid_email", "").strip()
    offered_price = request.form.get("offered_price", "").strip()
    note = request.form.get("note", "").strip()
    user_id = session.get("user_id")

    if not bid_name and user_id:
        user_info = query_db("SELECT name, email FROM users WHERE id = ?", [user_id], one=True)
        if user_info:
            bid_name = user_info["name"]
            bid_email = user_info["email"]

    if not bid_name:
        bid_name = "Guest"
    if not bid_email:
        bid_email = "guest@example.com"

    try:
        offered_price_value = float(offered_price) if offered_price else None
    except ValueError:
        offered_price_value = None

    execute_db(
        "INSERT INTO bids (product_id, user_id, name, email, offered_price, note, status) VALUES (?,?,?,?,?,?,?)",
        [product_id, user_id, bid_name, bid_email, offered_price_value, note, "Pending"],
    )

    flash(
        f'Your bid request for "{product["name"]}" has been received. Our team will contact you within 24 hours.',
        "success",
    )
    return redirect(url_for("product_detail", product_id=product_id))


# ---------------------------------------------------------------------------
# Routes - Contact Page
# ---------------------------------------------------------------------------

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        user_id = session.get("user_id")

        if not (name and email and phone and subject and message):
            flash("All fields are required.", "danger")
            return redirect(url_for("contact"))

        execute_db(
            "INSERT INTO contacts (user_id, name, email, phone, subject, message, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [user_id, name, email, phone, subject, message, "Unread"],
        )

        flash("Your message has been sent successfully! We will get back to you soon.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/admin/contacts")
@admin_required
def admin_contacts():
    contacts = query_db(
        "SELECT c.*, u.name AS user_name FROM contacts c LEFT JOIN users u ON u.id = c.user_id ORDER BY created_at DESC"
    )
    return render_template("admin/contacts.html", contacts=contacts)


@app.route("/admin/contacts/<int:contact_id>/status", methods=["POST"])
@admin_required
def admin_contact_status(contact_id):
    status = request.form.get("status", "Unread")
    execute_db("UPDATE contacts SET status = ? WHERE id = ?", [status, contact_id])
    flash("Contact status updated.", "success")
    return redirect(url_for("admin_contacts"))


@app.route("/admin/contacts/<int:contact_id>/delete", methods=["POST"])
@admin_required
def admin_contact_delete(contact_id):
    execute_db("DELETE FROM contacts WHERE id = ?", [contact_id])
    flash("Contact deleted.", "success")
    return redirect(url_for("admin_contacts"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
