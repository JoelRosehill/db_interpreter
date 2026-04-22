import sys
sys.path.insert(0, '.')
from db_interpreter_app.core.database_service import DatabaseService

svc = DatabaseService('.')
result = svc.execute('SQL', "CREATE TABLE users (id INTEGER PRIMARY KEY);", autocommit=True)
print('CREATE:', result.get('ok'), result.get('status'))

result = svc.execute('SQL', "ALTER TABLE users ADD COLUMN email TEXT;", autocommit=True)
print('ALTER:', result.get('ok'), result.get('status'))
print('Output:', result.get('output'))

tables = svc.get_tables()
print('Tables:', tables)

conn = svc.conn
cursor = svc.cursor
cursor.execute("PRAGMA table_info(users)")
print('Columns:', [row[1] for row in cursor.fetchall()])