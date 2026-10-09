from app.core.database import engine
from sqlmodel import Session, text

with Session(engine) as session:
    try:
        session.exec(text("ALTER TABLE \"user\" ADD COLUMN first_name VARCHAR;"))
        session.exec(text("ALTER TABLE \"user\" ADD COLUMN last_name VARCHAR;"))
        session.exec(text("ALTER TABLE \"user\" ADD COLUMN nin VARCHAR;"))
        session.exec(text("ALTER TABLE \"user\" ADD COLUMN dob VARCHAR;"))
        session.exec(text("CREATE UNIQUE INDEX ix_user_nin ON \"user\" (nin);"))
        session.commit()
        print("Columns added successfully!")
    except Exception as e:
        print(f"Error: {e}")
