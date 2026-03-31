from app.database import SessionLocal
from app.models import User
import datetime

db = SessionLocal()
users = db.query(User).all()

print(f"Total Users: {len(users)}")
print("-" * 50)
for user in users:
    trial_end = user.trial_ends_at
    now = datetime.datetime.utcnow()
    active = user.has_active_trial
    print(f"Email: {user.email}")
    print(f"Created At: {user.created_at}")
    print(f"Trial Ends At: {trial_end}")
    print(f"Now (UTC): {now}")
    print(f"Has Active Trial: {active}")
    print(f"Is Premium: {user.is_premium}")
    print("-" * 50)

db.close()
