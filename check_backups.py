import sqlite3
conn = sqlite3.connect('sazon_caribeno.db')
cur = conn.cursor()
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='backups_sistema'")
row = cur.fetchone()
print(row[0] if row else 'NO TABLE')
conn.close()
