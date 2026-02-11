import sqlite3

conn = sqlite3.connect('mydatabase.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM blueprint_category_overrides')
count = cursor.fetchone()[0]
print(f'Total overrides: {count}')

cursor.execute('SELECT type_id, category, subcategory FROM blueprint_category_overrides LIMIT 10')
print('\nSample overrides:')
for row in cursor.fetchall():
    print(f'  Type ID {row[0]}: {row[1]} - {row[2]}')

conn.close()
