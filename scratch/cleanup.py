from sqlalchemy import text
from app.core.database import engine

with engine.begin() as conn:
    gid = 'a8063299-c66a-4c75-b483-e9e692037335'
    conn.execute(text(f"DELETE FROM groupwallet WHERE group_id = '{gid}'"))
    conn.execute(text(f"DELETE FROM rotatinggroupdetails WHERE group_id = '{gid}'"))
    conn.execute(text(f"DELETE FROM groupmembership WHERE group_id = '{gid}'"))
    conn.execute(text(f"DELETE FROM \"group\" WHERE group_id = '{gid}'"))

print("Cleaned up successfully!")
