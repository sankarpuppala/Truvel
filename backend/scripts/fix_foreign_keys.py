import sqlite3

con = sqlite3.connect("backend/truvel.db")
cur = con.cursor()

# Check row counts just in case
print("medialike rows:", cur.execute("SELECT COUNT(*) FROM medialike").fetchone()[0])
print("mediaview rows:", cur.execute("SELECT COUNT(*) FROM mediaview").fetchone()[0])

# Fix medialike table
cur.execute("PRAGMA foreign_keys = OFF;")
cur.execute("DROP TABLE IF EXISTS medialike;")
cur.execute("""
CREATE TABLE medialike (
    id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    media_id INTEGER NOT NULL, 
    at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_medialike UNIQUE (user_id, media_id), 
    FOREIGN KEY(user_id) REFERENCES user (id), 
    FOREIGN KEY(media_id) REFERENCES media (id)
);
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_medialike_user_id ON medialike (user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS ix_medialike_media_id ON medialike (media_id);")

# Fix mediaview table
cur.execute("DROP TABLE IF EXISTS mediaview;")
cur.execute("""
CREATE TABLE mediaview (
    id INTEGER NOT NULL, 
    user_id INTEGER, 
    media_id INTEGER NOT NULL, 
    started_at DATETIME NOT NULL, 
    watched_s FLOAT NOT NULL, 
    completed BOOLEAN NOT NULL, 
    engaged BOOLEAN NOT NULL, 
    invalid_reason VARCHAR, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES user (id), 
    FOREIGN KEY(media_id) REFERENCES media (id)
);
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_mediaview_user_id ON mediaview (user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS ix_mediaview_media_id ON mediaview (media_id);")
cur.execute("CREATE INDEX IF NOT EXISTS ix_mediaview_started_at ON mediaview (started_at);")
cur.execute("CREATE INDEX IF NOT EXISTS ix_mediaview_invalid_reason ON mediaview (invalid_reason);")

con.commit()
cur.execute("PRAGMA foreign_keys = ON;")
print("Successfully recreated medialike and mediaview referencing media(id)!")
