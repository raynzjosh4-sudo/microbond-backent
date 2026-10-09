from sqlmodel import Session, text
from app.core.database import engine

def drop_tables():
    queries = [
        "DROP TABLE IF EXISTS groupsettings CASCADE;",
        "DROP TABLE IF EXISTS targetsavingsgroupdetails CASCADE;",
        "DROP TABLE IF EXISTS rotatinggroupdetails CASCADE;",
        "DROP TABLE IF EXISTS memberobligation CASCADE;",
        "DROP TABLE IF EXISTS groupmembership CASCADE;",
        "DROP TABLE IF EXISTS \"group\" CASCADE;"
    ]
    with Session(engine) as session:
        for q in queries:
            session.execute(text(q))
        session.commit()
    print("Tables dropped successfully.")

if __name__ == "__main__":
    drop_tables()
