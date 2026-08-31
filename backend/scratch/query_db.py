import sqlite3

conn = sqlite3.connect('database/app_metadata.db')
cursor = conn.cursor()
cursor.execute('SELECT run_id, count(*) FROM cognos_test_cases GROUP BY run_id ORDER BY run_id DESC LIMIT 5')
print('Recent runs:', cursor.fetchall())

cursor.execute("SELECT test_case_id, category, source_field, source_column, validation_sql FROM cognos_test_cases WHERE run_id = 210 AND test_case_id LIKE '%DBRE%'")
rows = cursor.fetchall()
print('Run 210 DBRE rows:', len(rows))
for r in rows:
    print(r[0], '|', r[1], '|', r[2], '|', r[3], '| SQL:\n', r[4])
