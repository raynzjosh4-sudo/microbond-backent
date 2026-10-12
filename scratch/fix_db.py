from sqlalchemy import text
from app.core.database import engine

with engine.begin() as conn:
    conn.execute(text('ALTER TABLE "group" ALTER COLUMN "health_grade" DROP NOT NULL;'))
    conn.execute(text("ALTER TABLE \"group\" ALTER COLUMN \"health_grade\" SET DEFAULT 'A+';"))
    conn.execute(text('ALTER TABLE "group" ALTER COLUMN "on_time_repayment_rate_pct" DROP NOT NULL;'))
    conn.execute(text('ALTER TABLE "group" ALTER COLUMN "on_time_repayment_rate_pct" SET DEFAULT 100.0;'))
    conn.execute(text('ALTER TABLE "group" ALTER COLUMN "active_default_rate_pct" DROP NOT NULL;'))
    conn.execute(text('ALTER TABLE "group" ALTER COLUMN "active_default_rate_pct" SET DEFAULT 0.0;'))

print("Health columns updated with defaults successfully!")
