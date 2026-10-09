from sqlmodel import Session, text
from app.core.database import engine

def migrate():
    queries = [
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS total_expected_pool_per_cycle FLOAT DEFAULT 0.0;",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS minimum_kyc_tier INTEGER DEFAULT 1;",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS require_guarantor BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS guarantor_default_action VARCHAR DEFAULT 'Charge guarantor after 48h';",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS allow_partial_payments BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS allow_advance_deposits BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE rotatinggroupdetails ADD COLUMN IF NOT EXISTS enforce_payout_holds BOOLEAN DEFAULT TRUE;"
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
