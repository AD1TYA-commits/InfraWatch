"""
Seeds one demo analyst account and one demo contractor account so a fresh
clone is immediately explorable without registering first.

These are clearly-labeled demo credentials for local evaluation only — never
reuse them for a real deployment. Idempotent: skips any account whose email
already exists (e.g. because a real user registered the same address, or this
ran before).

Usage:
    python -m scripts.seed_demo_users
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.models import User
from app.auth import hash_password

DEMO_USERS = [
    dict(email="analyst@infrawatch.local", password="demo-analyst-2025",
         role="analyst", full_name="Demo Analyst", organization=None),
    dict(email="contractor@infrawatch.local", password="demo-contractor-2025",
         role="contractor", full_name="Demo Contractor", organization="Demo Construction Co."),
]


def seed():
    db = SessionLocal()
    try:
        for data in DEMO_USERS:
            if db.query(User).filter(User.email == data["email"]).first():
                continue
            db.add(User(
                email=data["email"],
                hashed_password=hash_password(data["password"]),
                role=data["role"],
                full_name=data["full_name"],
                organization=data["organization"],
            ))
            print(f"Seeded demo {data['role']} account: {data['email']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
