from sqlmodel import Session, text
from app.core.database import engine

def migrate():
    queries = [
        "ALTER TABLE \"user\" DROP COLUMN IF EXISTS first_name;",
        "ALTER TABLE \"user\" DROP COLUMN IF EXISTS last_name;"
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
        print("Dropped columns.")

if __name__ == "__main__":
    migrate()
