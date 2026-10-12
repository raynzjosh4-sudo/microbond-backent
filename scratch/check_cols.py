from sqlalchemy import text
from app.core.database import engine

with engine.connect() as conn:
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'groupcommunicationsettings'")).fetchall()
    cols = [r[0] for r in res]
    print("enable_automated_audit_dispatch in DB:", "enable_automated_audit_dispatch" in cols)
    print("All cols in groupcommunicationsettings:", cols)
