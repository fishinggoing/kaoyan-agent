from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserProfile
from app.utils.exceptions import NotFoundError


def create_profile(db: Session, data: dict, client_id: str) -> UserProfile:
    data["client_id"] = client_id
    profile = UserProfile(**data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def list_profiles(db: Session, client_id: str) -> list[UserProfile]:
    return list(
        db.execute(
            select(UserProfile)
            .where(UserProfile.client_id == client_id)
            .order_by(UserProfile.created_at.desc())
        ).scalars().all()
    )


def get_profile(db: Session, profile_id: int, client_id: str) -> UserProfile:
    profile = db.get(UserProfile, profile_id)
    if not profile or profile.client_id != client_id:
        raise NotFoundError(f"UserProfile {profile_id} not found")
    return profile


def update_profile(db: Session, profile_id: int, data: dict, client_id: str) -> UserProfile:
    profile = get_profile(db, profile_id, client_id)
    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile_id: int, client_id: str) -> None:
    profile = get_profile(db, profile_id, client_id)
    db.delete(profile)
    db.commit()
