from sqlmodel import Session, text
from app.core.database import engine

def migrate():
    with Session(engine) as session:
        session.execute(text("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;"))
        session.commit()
        print('Added is_verified column.')

if __name__ == "__main__":
    migrate()
