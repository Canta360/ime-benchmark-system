"""Sets TEKITO's japanese_live_conversion (0/1) in user.db and prints the old value."""
import os, sqlite3, sys
db = sqlite3.connect(os.path.expandvars(r"%LOCALAPPDATA%\TEKITO\user.db"))
old = db.execute("select value from settings where key='japanese_live_conversion'").fetchone()
db.execute("update settings set value=? where key='japanese_live_conversion'", (int(sys.argv[1]),))
db.commit()
print(old[0] if old else "")
