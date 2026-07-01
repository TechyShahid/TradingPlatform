import database
import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

conn = database.get_db_connection()
conn.row_factory = dict_factory
cur = conn.cursor()
# Find stocks with multiple 'BUY' deals in bulk/block
query = """
SELECT symbol, security_name, COUNT(*) as buy_count, SUM(quantity_traded) as total_bought
FROM (
    SELECT symbol, security_name, quantity_traded FROM bulk_deals WHERE buy_sell LIKE 'BUY%'
    UNION ALL
    SELECT symbol, security_name, quantity_traded FROM block_deals WHERE buy_sell LIKE 'BUY%'
)
GROUP BY symbol, security_name
HAVING buy_count > 1
ORDER BY buy_count DESC, total_bought DESC
LIMIT 10
"""
cur.execute(query)
rows = cur.fetchall()
conn.close()

import pprint
pprint.pprint(rows)
