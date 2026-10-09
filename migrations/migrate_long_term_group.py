from sqlmodel import SQLModel, Session
from app.core.database import engine
from app.models.group.group import Group
from app.models.group.long_term import TargetSavingsGroupDetails

def migrate():
    print("Creating TargetSavingsGroupDetails table...")
    SQLModel.metadata.create_all(engine)
    print("Table created.")

if __name__ == "__main__":
    migrate()
