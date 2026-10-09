from sqlmodel import Session, text
from app.core.database import engine

def migrate_db():
    queries = [
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS full_name VARCHAR;",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS trust_score INTEGER NOT NULL DEFAULT 7;",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS kyc_tier INTEGER NOT NULL DEFAULT 1;",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS guardian_id INTEGER REFERENCES \"user\"(id);",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_dependent_account BOOLEAN NOT NULL DEFAULT FALSE;",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS daily_withdrawal_limit FLOAT NOT NULL DEFAULT 50000.0;"
    ]
    with Session(engine) as session:
        for q in queries:
            try:
                session.execute(text(q))
                session.commit()
                print(f"Executed: {q}")
            except Exception as e:
                session.rollback()
                print(f"Failed: {q} - {e}")
        print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
