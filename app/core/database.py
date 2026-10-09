from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)

def init_db():
    # Import all models to ensure SQLModel registers them before create_all
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
    
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
