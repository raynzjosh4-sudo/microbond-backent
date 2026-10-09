from sqlmodel import SQLModel
from app.core.database import engine

# Make sure all models are imported so SQLModel knows about them
import app.models.user.user
import app.models.user.kyc
import app.models.user.invite
import app.models.user.settings
import app.models.user.trust
import app.models.user.linked_account
import app.models.auth.otp
import app.models.group.group
import app.models.group.settings
import app.models.group.rotating
import app.models.group.long_term

if __name__ == "__main__":
    print("WARNING: This will drop all tables in the database!")
    print("Dropping tables...")
    SQLModel.metadata.drop_all(engine)
    print("Tables dropped successfully!")
    print("Now run uvicorn (or init_db()) to recreate them with the new UUIDs.")
