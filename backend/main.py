import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from database import get_db, SessionLocal, Base
from models import User, Player, InjuryEvent, Team, MatchSession
from auth import verify_password, create_access_token, decode_access_token


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS_DIR = os.path.join(PROJECT_ROOT, "output", "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

app.mount("/clips", StaticFiles(directory=CLIPS_DIR), name="clips")


# ============================================
# STARTUP BOOTSTRAP (replaces create_tables, migrate_v2,
# seed_match_2006, ensure_users, create_admin, add_players)
# Only adds what is missing. Never deletes anything and
# never changes an existing password.
# ============================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MIGRATIONS = [
    "ALTER TABLE match_sessions ADD COLUMN IF NOT EXISTS name VARCHAR",
    "ALTER TABLE match_sessions ADD COLUMN IF NOT EXISTS video_source VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS region VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS risk VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS movement DOUBLE PRECISION",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS note VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS source VARCHAR NOT NULL DEFAULT 'ai'",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS resolved BOOLEAN DEFAULT FALSE",
    'ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS "timestamp" TIMESTAMPTZ DEFAULT now()',
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS match_session_id INTEGER REFERENCES match_sessions(id)",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS injury_note VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS clip_path VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS identified_at TIMESTAMPTZ",
    "ALTER TABLE injury_events ALTER COLUMN player_id DROP NOT NULL",
    # v3 — how and where the player was identified
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS track_id INTEGER",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS video_time_sec DOUBLE PRECISION",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS identified_by VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS id_detail VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS id_confidence DOUBLE PRECISION",
    # v4 — Gemini second opinion
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_verdict VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_confidence DOUBLE PRECISION",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_reason VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_description VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_jersey INTEGER",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_team VARCHAR",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_jersey_confidence DOUBLE PRECISION",
    "ALTER TABLE injury_events ADD COLUMN IF NOT EXISTS gemini_checked_at TIMESTAMPTZ",
]

# ============================================
# GEMINI RULES
# false alarm with at least this confidence -> event is deleted (clip too)
# Gemini's jersey read replaces ours only if it is at least this sure
# AND more confident than our own identification
# ============================================

GEMINI_DELETE_MIN_CONFIDENCE = 0.75
GEMINI_JERSEY_MIN_CONFIDENCE = 0.60

# ============================================
# DUPLICATE FALLS
# Running the detector on the same video again creates a new match session
# and would save every fall a second time. Two AI events are the SAME fall when:
#   - they come from DIFFERENT runs (match sessions) of the SAME video file
#   - same event type
#   - their times in the video are within DUPLICATE_WINDOW_SEC
#   - same player if both are identified; otherwise same track id or same body area
# Falls inside one run are never merged (two players can fall at the same moment).
# ============================================

DUPLICATE_WINDOW_SEC = 3.0

ROSTERS = {
    "Portugal": [
        (1, "Ricardo"),
        (5, "Fernando Meira"),
        (6, "Costinha"),
        (7, "Lu\u00eds Figo"),
        (8, "Petit"),
        (9, "Pauleta"),
        (11, "Sim\u00e3o"),
        (13, "Miguel"),
        (14, "Nuno Valente"),
        (16, "Ricardo Carvalho"),
        (17, "Cristiano Ronaldo"),
        (18, "Maniche"),
        (19, "Tiago"),
        (20, "Deco"),
    ],
    "Netherlands": [
        (1, "Edwin van der Sar"),
        (3, "Khalid Boulahrouz"),
        (4, "Joris Mathijsen"),
        (5, "Giovanni van Bronckhorst"),
        (7, "Dirk Kuyt"),
        (8, "Phillip Cocu"),
        (10, "Rafael van der Vaart"),
        (11, "Arjen Robben"),
        (13, "Andr\u00e9 Ooijer"),
        (14, "John Heitinga"),
        (17, "Robin van Persie"),
        (18, "Mark van Bommel"),
        (19, "Jan Vennegoor of Hesselink"),
        (20, "Wesley Sneijder"),
    ],
}

PLACEHOLDER_TEAMS = {"Portugal": "Team A", "Netherlands": "Team B"}

# (username, team, password used only when the account does not exist yet)
COACH_ACCOUNTS = [
    ("coach1", "Netherlands", "coach1pass"),
    ("coach2", "Portugal", "coach2pass"),
]


def bootstrap_data():

    probe = SessionLocal()
    engine = probe.get_bind()
    probe.close()

    # 1. tables + columns
    Base.metadata.create_all(bind=engine)

    for sql in MIGRATIONS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as e:
            print("[BOOTSTRAP] migration skipped:", sql[:60], "|", e)

    db = SessionLocal()

    try:
        # 2. teams + players
        teams = {}

        for team_name, roster in ROSTERS.items():

            team = db.query(Team).filter(Team.name == team_name).first()

            if team is None:
                placeholder = db.query(Team).filter(Team.name == PLACEHOLDER_TEAMS[team_name]).first()
                if placeholder is not None:
                    placeholder.name = team_name
                    team = placeholder

            if team is None:
                team = Team(name=team_name)
                db.add(team)
                db.flush()

            teams[team_name] = team

            existing = {}
            for p in db.query(Player).filter(Player.team_id == team.id).all():
                existing.setdefault(p.jersey_number, p)

            for number, name in roster:
                if number not in existing:
                    db.add(Player(team_id=team.id, name=name, jersey_number=number))
                    print("[BOOTSTRAP] added player:", team_name, "#" + str(number), name)

        db.flush()

        # 3. coach accounts
        for username, team_name, password in COACH_ACCOUNTS:

            user = db.query(User).filter(User.username == username).first()

            if user is None:
                db.add(User(
                    username=username,
                    password_hash=pwd_context.hash(password),
                    role="coach",
                    team_id=teams[team_name].id,
                ))
                print("[BOOTSTRAP] created", username, "->", team_name, "| password:", password)

            elif user.team_id != teams[team_name].id or user.role != "coach":
                user.role = "coach"
                user.team_id = teams[team_name].id
                print("[BOOTSTRAP] assigned", username, "->", team_name)

        # 4. admin (only if none exists)
        if db.query(User).filter(User.role == "admin").first() is None:
            db.add(User(
                username="admin1",
                password_hash=pwd_context.hash("admin1pass"),
                role="admin",
                team_id=None,
            ))
            print("[BOOTSTRAP] created admin1 | password: admin1pass")

        db.commit()

        print("[BOOTSTRAP] done:", db.query(Player).count(), "players,", db.query(User).count(), "users")

    except Exception as e:
        db.rollback()
        print("[BOOTSTRAP] failed:", e)

    finally:
        db.close()


def _video_key(match):
    """Same video file = same key (case and slash direction ignored)."""
    if match is None or not match.video_source:
        return None
    return str(match.video_source).strip().replace("\\", "/").lower()


def _same_fall(a, b, key_a=None):
    """True if events a and b are the same fall from two runs of the same video.
    key_a: video key of a, when a is not saved yet (no .match loaded)."""

    if a.match_session_id is None or b.match_session_id is None:
        return False
    if a.match_session_id == b.match_session_id:
        return False
    if (a.source or "ai") != "ai" or (b.source or "ai") != "ai":
        return False
    if a.video_time_sec is None or b.video_time_sec is None:
        return False
    if key_a is None:
        key_a = _video_key(a.match)
    if key_a is None or key_a != _video_key(b.match):
        return False
    if (a.event_type or "").upper() != (b.event_type or "").upper():
        return False
    if abs(a.video_time_sec - b.video_time_sec) > DUPLICATE_WINDOW_SEC:
        return False

    if a.player_id is not None and b.player_id is not None:
        return a.player_id == b.player_id

    same_track = a.track_id is not None and a.track_id == b.track_id
    same_area = bool(a.region) and (a.region or "").upper() == (b.region or "").upper()
    return same_track or same_area


def _keep_score(e):
    """Which copy of a duplicate to keep: staff pick > identified (by confidence) > has clip > oldest."""
    return (
        1 if e.identified_by == "manual" else 0,
        1 if e.player_id is not None else 0,
        e.id_confidence or 0.0,
        1 if e.clip_path else 0,
        -e.id,
    )


def _clip_exists(clip_path):
    return bool(clip_path) and os.path.exists(os.path.join(CLIPS_DIR, clip_path))


def _remove_clip_file(clip_path):
    if not clip_path:
        return
    try:
        os.remove(os.path.join(CLIPS_DIR, clip_path))
    except OSError:
        pass


def remove_duplicate_events(db, dry_run=False):
    """
    Keeps one event per fall and deletes the extra copies (and their clip files).
    Returns a list of {"kept": id, "removed": [ids]}.
    """

    events = (
        db.query(InjuryEvent)
        .filter(InjuryEvent.match_session_id.isnot(None), InjuryEvent.video_time_sec.isnot(None))
        .all()
    )
    events = [e for e in events if (e.source or "ai") == "ai" and _video_key(e.match)]
    events.sort(key=_keep_score, reverse=True)

    clusters = []   # each: {"keeper": event, "members": [events], "sessions": set()}

    for e in events:
        home = None
        for c in clusters:
            if e.match_session_id in c["sessions"]:
                continue
            if _same_fall(c["keeper"], e):
                home = c
                break
        if home is None:
            clusters.append({"keeper": e, "members": [e], "sessions": {e.match_session_id}})
        else:
            home["members"].append(e)
            home["sessions"].add(e.match_session_id)

    report = []

    for c in clusters:
        if len(c["members"]) < 2:
            continue

        keeper = c["keeper"]
        extras = [m for m in c["members"] if m.id != keeper.id]

        report.append({"kept": keeper.id, "removed": [m.id for m in extras]})

        if dry_run:
            continue

        # the kept event takes a working clip from a copy if its own is missing
        if not _clip_exists(keeper.clip_path):
            for m in extras:
                if _clip_exists(m.clip_path):
                    keeper.clip_path = m.clip_path
                    break

        for m in extras:
            if m.clip_path and m.clip_path != keeper.clip_path:
                _remove_clip_file(m.clip_path)
            db.delete(m)

    if not dry_run and report:
        db.commit()

    return report


def _cleanup_duplicates_on_startup():
    db = SessionLocal()
    try:
        report = remove_duplicate_events(db)
        removed = sum(len(r["removed"]) for r in report)
        if removed:
            print("[DUPLICATES] Removed", removed, "duplicate event(s):", report)
        else:
            print("[DUPLICATES] No duplicate events found")
    except Exception as e:
        db.rollback()
        print("[DUPLICATES] Cleanup skipped:", e)
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    bootstrap_data()
    _cleanup_duplicates_on_startup()


# ============================================
# REQUEST SCHEMAS
# ============================================

class LoginRequest(BaseModel):
    username: str
    password: str


class EventCreateRequest(BaseModel):
    player_id: Optional[int] = None          # None = Unidentified
    match_session_id: Optional[int] = None
    event_type: str
    region: Optional[str] = None
    risk: Optional[str] = None
    movement: Optional[float] = None
    injury_note: Optional[str] = None
    clip_path: Optional[str] = None
    source: str = "ai"
    track_id: Optional[int] = None
    video_time_sec: Optional[float] = None
    identified_by: Optional[str] = None      # jersey / jersey_name / jersey_history / jersey_handoff / face
    id_detail: Optional[str] = None          # e.g. "jersey #17", "face match (3 frames)"
    id_confidence: Optional[float] = None    # 0..1


class EventAIUpdateRequest(BaseModel):
    player_id: Optional[int] = None
    clip_path: Optional[str] = None
    injury_note: Optional[str] = None
    identified_by: Optional[str] = None
    id_detail: Optional[str] = None
    id_confidence: Optional[float] = None


class AssignPlayerRequest(BaseModel):
    player_id: int


class GeminiResultRequest(BaseModel):
    verdict: str                                  # real_fall / false_alarm / unsure / error
    confidence: Optional[float] = None            # 0..1, confidence in the verdict
    reason: Optional[str] = None
    description: Optional[str] = None
    team: Optional[str] = None                    # "Portugal" / "Netherlands" / "unknown"
    jersey_number: Optional[int] = None
    jersey_confidence: Optional[float] = None     # 0..1


class ManualEventRequest(BaseModel):
    player_id: int
    event_type: str
    note: str
    risk: Optional[str] = "MEDIUM"
    match_session_id: Optional[int] = None


class MatchCreateRequest(BaseModel):
    name: Optional[str] = None
    video_source: Optional[str] = None


# ============================================
# AUTH DEPENDENCY
# ============================================

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == payload.get("user_id")).first()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# ============================================
# SERIALIZER
# ============================================

def event_to_dict(e: InjuryEvent):

    return {
        "id": e.id,
        "player_id": e.player_id,
        "player_name": e.player.name if e.player is not None else "Unidentified",
        "jersey_number": e.player.jersey_number if e.player is not None else None,
        "team_name": (e.player.team.name if e.player is not None and e.player.team is not None else None),
        "identified": e.player_id is not None,
        "identified_at": e.identified_at,
        "identified_by": e.identified_by,
        "id_detail": e.id_detail,
        "id_confidence": e.id_confidence,
        "track_id": e.track_id,
        "video_time_sec": e.video_time_sec,
        "gemini_verdict": e.gemini_verdict,
        "gemini_confidence": e.gemini_confidence,
        "gemini_reason": e.gemini_reason,
        "gemini_description": e.gemini_description,
        "gemini_jersey": e.gemini_jersey,
        "gemini_team": e.gemini_team,
        "gemini_jersey_confidence": e.gemini_jersey_confidence,
        "gemini_checked_at": e.gemini_checked_at,
        "match_session_id": e.match_session_id,
        "match_name": (e.match.name if e.match is not None and e.match.name else
                       ("Match #" + str(e.match_session_id) if e.match_session_id else None)),
        "event_type": e.event_type,
        "region": e.region,
        "risk": e.risk,
        "movement": e.movement,
        "note": e.note,
        "injury_note": e.injury_note,
        "clip_url": ("/clips/" + e.clip_path) if e.clip_path else None,
        "source": e.source,
        "resolved": e.resolved,
        "timestamp": e.timestamp,
    }


# ============================================
# LOGIN
# ============================================

@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.username == request.username).first()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({
        "user_id": user.id,
        "role": user.role,
        "team_id": user.team_id
    })

    return {
        "access_token": token,
        "role": user.role,
        "team_id": user.team_id,
        "username": user.username
    }


# ============================================
# MATCHES
# ============================================

@app.post("/matches")
def create_match(request: MatchCreateRequest, db: Session = Depends(get_db)):

    match = MatchSession(name=request.name, video_source=request.video_source)

    db.add(match)
    db.commit()
    db.refresh(match)

    return {"message": "Match created", "match_session_id": match.id}


@app.get("/matches")
def get_matches(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    matches = db.query(MatchSession).order_by(MatchSession.date.desc()).all()

    return [
        {
            "id": m.id,
            "name": m.name or ("Match #" + str(m.id)),
            "video_source": m.video_source,
            "date": m.date,
        }
        for m in matches
    ]


# ============================================
# EVENTS — AI SCRIPT POSTS HERE (saved even without a player)
# ============================================

@app.post("/events")
def create_event(request: EventCreateRequest, db: Session = Depends(get_db)):

    if request.player_id is not None:
        player = db.query(Player).filter(Player.id == request.player_id).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

    if request.match_session_id is not None:
        match = db.query(MatchSession).filter(MatchSession.id == request.match_session_id).first()
        if match is None:
            raise HTTPException(status_code=404, detail="Match session not found")

    event = InjuryEvent(
        player_id=request.player_id,
        match_session_id=request.match_session_id,
        event_type=request.event_type,
        region=request.region,
        risk=request.risk,
        movement=request.movement,
        injury_note=request.injury_note,
        clip_path=request.clip_path,
        source=request.source,
        track_id=request.track_id,
        video_time_sec=request.video_time_sec,
    )

    if request.player_id is not None:
        event.identified_at = func.now()
        event.identified_by = request.identified_by
        event.id_detail = request.id_detail
        event.id_confidence = request.id_confidence

    # Same fall already saved by an earlier run of this video? Reuse that event.
    existing = _find_duplicate(db, event)

    if existing is not None:

        # fill in the player if the earlier copy never got one (never overrides staff)
        if existing.player_id is None and event.player_id is not None:
            existing.player_id = event.player_id
            existing.identified_at = func.now()
            existing.identified_by = event.identified_by
            existing.id_detail = event.id_detail
            existing.id_confidence = event.id_confidence
            db.commit()

        return {
            "message": "Duplicate of an event from an earlier run of this video",
            "event_id": existing.id,
            "duplicate": True,
        }

    db.add(event)
    db.commit()
    db.refresh(event)

    return {"message": "Event recorded", "event_id": event.id, "duplicate": False}


def _find_duplicate(db, new_event):
    """Closest matching event from an earlier run of the same video, or None."""

    if new_event.match_session_id is None or new_event.video_time_sec is None:
        return None
    if (new_event.source or "ai") != "ai":
        return None

    match = db.query(MatchSession).filter(MatchSession.id == new_event.match_session_id).first()
    key = _video_key(match)

    if key is None:
        return None

    candidates = (
        db.query(InjuryEvent)
        .join(MatchSession, InjuryEvent.match_session_id == MatchSession.id)
        .filter(
            InjuryEvent.match_session_id != new_event.match_session_id,
            InjuryEvent.video_time_sec.isnot(None),
            InjuryEvent.video_time_sec >= new_event.video_time_sec - DUPLICATE_WINDOW_SEC,
            InjuryEvent.video_time_sec <= new_event.video_time_sec + DUPLICATE_WINDOW_SEC,
        )
        .all()
    )

    matches = [c for c in candidates if _same_fall(new_event, c, key_a=key)]

    if not matches:
        return None

    matches.sort(key=lambda c: abs(c.video_time_sec - new_event.video_time_sec))
    return matches[0]


# ============================================
# EVENTS — AI SCRIPT FILLS IN PLAYER / CLIP LATER
# ============================================

@app.patch("/events/{event_id}/ai-update")
def ai_update_event(event_id: int, request: EventAIUpdateRequest, db: Session = Depends(get_db)):

    event = db.query(InjuryEvent).filter(InjuryEvent.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if request.player_id is not None:

        player = db.query(Player).filter(Player.id == request.player_id).first()

        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        # never overwrite a staff decision, and only replace a Gemini answer with a surer one
        keep_existing = (
            event.player_id is not None
            and (
                event.identified_by == "manual"
                or (
                    event.identified_by == "gemini"
                    and (request.id_confidence or 0) <= (event.id_confidence or 0)
                )
            )
        )

        if not keep_existing:
            event.player_id = request.player_id
            event.identified_at = func.now()
            event.identified_by = request.identified_by
            event.id_detail = request.id_detail
            event.id_confidence = request.id_confidence

    if request.clip_path is not None:
        # A re-run of the same video sends a second clip for the same fall:
        # keep the clip that already works and delete the new copy.
        if event.clip_path and event.clip_path != request.clip_path and _clip_exists(event.clip_path):
            _remove_clip_file(request.clip_path)
        else:
            event.clip_path = request.clip_path

    if request.injury_note is not None:
        event.injury_note = request.injury_note

    db.commit()
    db.refresh(event)

    return {"message": "Event updated", "event": event_to_dict(event)}


# ============================================
# EVENTS — GEMINI SECOND OPINION (sent by src/gemini_verifier.py)
# - confident false alarm  -> event and its clip are deleted
# - confident jersey read  -> replaces our player if Gemini is surer
# ============================================

@app.patch("/events/{event_id}/gemini")
def gemini_result(event_id: int, request: GeminiResultRequest, db: Session = Depends(get_db)):

    event = db.query(InjuryEvent).filter(InjuryEvent.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    verdict = (request.verdict or "unsure").lower()
    confidence = request.confidence if request.confidence is not None else 0.0

    # 1) confident false alarm -> delete
    if verdict == "false_alarm" and confidence >= GEMINI_DELETE_MIN_CONFIDENCE and event.identified_by != "manual":

        clip_path = event.clip_path

        db.delete(event)
        db.commit()

        if clip_path:
            try:
                os.remove(os.path.join(CLIPS_DIR, clip_path))
            except OSError:
                pass

        return {"action": "deleted", "event_id": event_id, "reason": request.reason}

    # 2) store the second opinion
    event.gemini_verdict = verdict
    event.gemini_confidence = request.confidence
    event.gemini_reason = request.reason
    event.gemini_description = request.description
    event.gemini_team = request.team
    event.gemini_jersey = request.jersey_number
    event.gemini_jersey_confidence = request.jersey_confidence
    event.gemini_checked_at = func.now()

    action = "stored"

    # 3) Gemini's jersey read -> player, if it is surer than ours
    jersey_conf = request.jersey_confidence or 0.0

    if (
        request.jersey_number is not None
        and request.team
        and request.team.lower() != "unknown"
        and jersey_conf >= GEMINI_JERSEY_MIN_CONFIDENCE
        and event.identified_by != "manual"
    ):

        player = (
            db.query(Player)
            .join(Team, Team.id == Player.team_id)
            .filter(Team.name.ilike(request.team.strip()), Player.jersey_number == request.jersey_number)
            .first()
        )

        if player is not None and player.id != event.player_id:

            ours = event.id_confidence or 0.0

            if event.player_id is None or jersey_conf > ours:

                previous = (
                    event.player.name + " (" + str(round(ours * 100)) + "%)"
                    if event.player is not None else "Unidentified"
                )

                event.player_id = player.id
                event.identified_at = func.now()
                event.identified_by = "gemini"
                event.id_detail = (
                    "Gemini read #" + str(request.jersey_number) + " (" + player.team.name + ")"
                    + " - model said: " + previous
                )
                event.id_confidence = jersey_conf

                action = "reassigned" if previous != "Unidentified" else "identified"

    db.commit()
    db.refresh(event)

    return {"action": action, "event": event_to_dict(event)}


# ============================================
# EVENTS — ASSIGN / CORRECT THE PLAYER
# Used from the dashboard after watching the clip.
# - Unidentified event: ANY logged-in user (admin, medical, coach)
#   can pick the player.
# - Already identified event: only medical staff or admin can change it.
# The AI never overwrites a manual choice (see /ai-update and /gemini).
# ============================================

@app.patch("/events/{event_id}/assign")
def assign_player(
    event_id: int,
    request: AssignPlayerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    event = db.query(InjuryEvent).filter(InjuryEvent.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    is_staff = current_user.role in ("medical", "admin")

    if not is_staff:

        if current_user.role != "coach":
            raise HTTPException(status_code=403, detail="Unknown role")

        if event.player_id is not None:
            current = event.player.name if event.player is not None else "a player"
            raise HTTPException(
                status_code=409,
                detail="Already identified as " + current + ". Only medical staff or admin can change it."
            )

    player = db.query(Player).filter(Player.id == request.player_id).first()

    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    previous = event.player.name if event.player is not None else "Unidentified"

    event.player_id = player.id
    event.identified_at = func.now()
    event.identified_by = "manual"
    event.id_detail = (
        "chosen from clip by " + current_user.username + " (" + current_user.role + ")"
        + " - was: " + previous
    )
    event.id_confidence = None

    db.commit()
    db.refresh(event)

    return {"message": "Player assigned", "event": event_to_dict(event)}


# ============================================
# EVENTS — MEDICAL STAFF MANUAL LOGGING
# ============================================

@app.post("/events/manual")
def create_manual_event(
    request: ManualEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role != "medical":
        raise HTTPException(status_code=403, detail="Only medical staff can log manual events")

    player = db.query(Player).filter(Player.id == request.player_id).first()

    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    event = InjuryEvent(
        player_id=request.player_id,
        match_session_id=request.match_session_id,
        event_type=request.event_type,
        note=request.note,
        risk=request.risk,
        source="manual",
        identified_by="manual",
        id_detail="logged by " + current_user.username,
    )

    event.identified_at = func.now()

    db.add(event)
    db.commit()
    db.refresh(event)

    return {"message": "Manual event recorded", "event_id": event.id}


# ============================================
# GET EVENTS — medical/admin: all. coach: own team + Unidentified
# ============================================

@app.get("/events")
def get_events(
    match_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    query = db.query(InjuryEvent).outerjoin(Player, InjuryEvent.player_id == Player.id)

    if current_user.role in ("medical", "admin"):
        pass

    elif current_user.role == "coach":
        query = query.filter(
            or_(
                Player.team_id == current_user.team_id,
                InjuryEvent.player_id.is_(None)
            )
        )

    else:
        raise HTTPException(status_code=403, detail="Unknown role")

    if match_id is not None:
        query = query.filter(InjuryEvent.match_session_id == match_id)

    events = query.order_by(InjuryEvent.timestamp.desc()).all()

    return [event_to_dict(e) for e in events]


# ============================================
# GET PLAYERS — all players, both teams, for every role
# ============================================

# Every role gets BOTH teams: an Unidentified fall can be any player,
# so coaches need the full roster to pick from when reviewing a clip.

@app.get("/players")
def get_players(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    players = (
        db.query(Player)
        .order_by(Player.team_id, Player.jersey_number)
        .all()
    )

    return [
        {
            "id": p.id,
            "name": p.name,
            "jersey_number": p.jersey_number,
            "team_id": p.team_id,
            "team_name": p.team.name if p.team is not None else None,
        }
        for p in players
    ]


# ============================================
# GET TEAMS — admin/medical: both teams. coach: own team only.
# ============================================

@app.get("/teams")
def get_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if current_user.role in ("medical", "admin"):
        teams = db.query(Team).order_by(Team.id).all()

    elif current_user.role == "coach":
        teams = db.query(Team).filter(Team.id == current_user.team_id).all()

    else:
        raise HTTPException(status_code=403, detail="Unknown role")

    result = []

    for t in teams:

        players = (
            db.query(Player)
            .filter(Player.team_id == t.id)
            .order_by(Player.jersey_number)
            .all()
        )

        coaches = db.query(User).filter(User.role == "coach", User.team_id == t.id).all()

        rows = []
        team_total = 0
        team_high = 0

        for p in players:

            total = (
                db.query(func.count(InjuryEvent.id))
                .filter(InjuryEvent.player_id == p.id)
                .scalar()
            ) or 0

            high = (
                db.query(func.count(InjuryEvent.id))
                .filter(InjuryEvent.player_id == p.id, InjuryEvent.risk == "HIGH")
                .scalar()
            ) or 0

            team_total += total
            team_high += high

            rows.append({
                "id": p.id,
                "name": p.name,
                "jersey_number": p.jersey_number,
                "injury_events": total,
                "high_risk_events": high,
            })

        result.append({
            "id": t.id,
            "name": t.name,
            "coaches": [c.username for c in coaches],
            "player_count": len(rows),
            "injury_events": team_total,
            "high_risk_events": team_high,
            "players": rows,
        })

    return result


# ============================================
# MARK EVENT RESOLVED
# ============================================

@app.patch("/events/{event_id}/resolve")
def resolve_event(event_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    event = db.query(InjuryEvent).filter(InjuryEvent.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event.resolved = True
    db.commit()

    return {"message": "Event marked as resolved"}


# ============================================
# ADMIN — REMOVE DUPLICATE EVENTS
# Also runs automatically every time the backend starts.
# ?dry_run=true only lists what would be removed.
# ============================================

@app.post("/admin/events/remove-duplicates")
def admin_remove_duplicates(
    dry_run: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")

    report = remove_duplicate_events(db, dry_run=dry_run)

    return {
        "dry_run": dry_run,
        "groups": report,
        "removed_events": sum(len(r["removed"]) for r in report),
    }


# ============================================
# ADMIN — CLEAR ALL INJURY EVENTS (players are kept)
# ============================================

@app.delete("/admin/players/clear")
def clear_all_injury_events(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")

    deleted = db.query(InjuryEvent).delete()
    db.commit()

    return {"message": "All injury events deleted. Players were kept.", "deleted_events": deleted}