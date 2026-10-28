"""Browser playback receivers. Commands are short-lived, acknowledged mailboxes."""
import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, select

from ..db import get_session
from ..models import Category, PlaybackTarget
from .core import profile_id

router = APIRouter(prefix="/playback")
ONLINE_SECONDS = 20
COMMAND_SECONDS = 30


class Registration(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class Heartbeat(BaseModel):
    ack: str = ""
    video_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{11}$")
    paused: bool = True
    position_s: float = Field(default=0, ge=0, le=864000, allow_inf_nan=False)
    error: str = Field(default="", max_length=200)


class Command(BaseModel):
    action: str = Field(pattern=r"^(play|pause|resume|stop)$")
    video_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{11}$")
    category_id: int | None = None


def _public(target):
    return {"id": target.id, "name": target.name,
            "online": time.time() - target.last_seen < ONLINE_SECONDS, "state": target.state}


def _receiver(s, target_id, token):
    target = s.get(PlaybackTarget, target_id)
    digest = hashlib.sha256((token or "").encode()).hexdigest()
    if not target or not hmac.compare_digest(target.token_hash, digest):
        raise HTTPException(403, "Invalid playback receiver credentials")
    return target


@router.get("/targets")
def targets(s: Session = Depends(get_session)):
    return [_public(t) for t in s.exec(select(PlaybackTarget).order_by(PlaybackTarget.name)).all()]


@router.post("/targets")
def register(body: Registration, s: Session = Depends(get_session)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter a screen name")
    token = secrets.token_urlsafe(32)
    target = PlaybackTarget(id=secrets.token_urlsafe(16), name=name,
                            token_hash=hashlib.sha256(token.encode()).hexdigest(), last_seen=time.time())
    s.add(target)
    s.commit()
    return {**_public(target), "token": token}


@router.post("/targets/{target_id}/heartbeat")
def heartbeat(target_id: str, body: Heartbeat, x_receiver_token: str = Header(default=""),
              s: Session = Depends(get_session)):
    target = _receiver(s, target_id, x_receiver_token)
    command = target.command
    # Update only receiver-owned columns; a concurrent sender must not be overwritten.
    s.exec(update(PlaybackTarget).where(PlaybackTarget.id == target_id).values(
        last_seen=time.time(), state=body.model_dump(exclude={"ack"})))
    s.commit()
    pending = command if (command and command["id"] != body.ack
                          and time.time() - command["created_at"] < COMMAND_SECONDS) else None
    return {"command": pending}


@router.post("/targets/{target_id}/commands")
def send_command(target_id: str, body: Command, pid: int = Depends(profile_id),
                 s: Session = Depends(get_session)):
    target = s.get(PlaybackTarget, target_id)
    if not target:
        raise HTTPException(404, "Playback target no longer exists")
    if time.time() - target.last_seen >= ONLINE_SECONDS:
        raise HTTPException(409, "This screen is offline. Open BetterTube on it first.")
    if body.action == "play" and not body.video_id:
        raise HTTPException(422, "Choose a video to play")
    if body.category_id is not None:
        category = s.get(Category, body.category_id)
        if not category or category.profile_id != pid:
            raise HTTPException(404, "Playlist not found")
    command = {**body.model_dump(), "id": secrets.token_urlsafe(16),
               "profile_id": pid, "created_at": time.time()}
    s.exec(update(PlaybackTarget).where(PlaybackTarget.id == target_id).values(command=command))
    s.commit()
    return {"command_id": command["id"]}


@router.delete("/targets/{target_id}")
def unregister(target_id: str, x_receiver_token: str = Header(default=""),
               s: Session = Depends(get_session)):
    target = _receiver(s, target_id, x_receiver_token)
    s.delete(target)
    s.commit()
    return {"ok": True}
