from sqlmodel import SQLModel, Session, text
from app.core.database import engine
from app.models.user import User
from app.models.settings import UserSettings, NotificationSettings
from app.models.linked_account import LinkedAccount
from app.models.invite import Invite

def migrate():
    # 1. Create all new tables (SQLModel handles this automatically if they don't exist)
    print("Creating new tables...")
    SQLModel.metadata.create_all(engine)
    
    # 2. Add missing columns to existing user table
    queries = [
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS hashed_pin VARCHAR;"
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
    migrate()
