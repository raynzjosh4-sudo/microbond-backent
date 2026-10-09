from sqlmodel import SQLModel, Session, text
from app.core.database import engine
from app.models.group.settings import GroupSettings
from app.models.group.group import Group

def migrate():
    print("Creating GroupSettings table...")
    SQLModel.metadata.create_all(engine)
    
    print("Dropping JSON columns from group table...")
    queries = [
        "ALTER TABLE \"group\" DROP COLUMN IF EXISTS purpose_data;",
        "ALTER TABLE \"group\" DROP COLUMN IF EXISTS admin_settings;"
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

if __name__ == "__main__":
    migrate()
