from sqlmodel import SQLModel, Session
from app.core.database import engine
from app.models.group.group import Group
from app.models.group.rotating import RotatingGroupDetails

def migrate():
    print("Creating RotatingGroupDetails table...")
    SQLModel.metadata.create_all(engine)
    print("Table created.")

if __name__ == "__main__":
    migrate()
