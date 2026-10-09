from sqlmodel import SQLModel, Session, text
from app.core.database import engine
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership, MemberObligation

def migrate():
    print("Creating new group tables...")
    SQLModel.metadata.create_all(engine)
    print("Group Migration complete.")

if __name__ == "__main__":
    migrate()
