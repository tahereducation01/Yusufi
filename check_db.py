import sqlite3
db = sqlite3.connect('safetyshop.db')
print('Categories:', db.execute('SELECT name FROM categories').fetchall())
print('Products with Ear Plug:', db.execute('SELECT id, name FROM products WHERE category = ?', ('Ear Plug',)).fetchall())
db.close()