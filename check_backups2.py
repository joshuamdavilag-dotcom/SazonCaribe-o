import sqlite3
conn = sqlite3.connect('data/sazon_caribeno.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backups_sistema'")
row = cur.fetchone()
print(row)
conn.close()
