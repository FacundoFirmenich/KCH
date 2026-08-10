import json
import sqlite3
import sys

path = sys.argv[1]
connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(json.dumps({name: connection.execute(f"PRAGMA table_info({name})").fetchall() for name in tables}, indent=2))
print("COUNTS", [(name, connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in tables if not name.startswith("sqlite_")])
connection.close()
