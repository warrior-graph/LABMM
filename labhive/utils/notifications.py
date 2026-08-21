"""Helpers for creating in-app notifications."""
from labhive.extensions import db
from labhive.models.notification import Notification


def notify(member_ids, type_: str, message: str, link: str | None = None) -> None:
    """Create one notification per member id. Duplicate ids are ignored."""
    seen: set[int] = set()
    for mid in member_ids or []:
        mid = int(mid)
        if mid in seen:
            continue
        seen.add(mid)
        db.session.add(
            Notification(member_id=mid, type=type_, message=message, link=link)
        )
