"""
gemini_verifier.py - Gemini second opinion on every saved fall.

Interface used by multi_player_injury.py:
    start(), submit(ids, raw_frames, target_index, target_box, context),
    shutdown(), is_available(), player_changes, deleted_event_ids, stats
Also used by verify_clips.py (checks clips that are already saved):
    init(), ask(), to_backend(), send_result(), team_names()

What it does for each saved fall (runs in a background thread):
  - Sends the fall-moment frame (target player boxed), a zoomed crop and a few
    surrounding frames to Gemini.
  - Sends Gemini's answer to the backend (PATCH /events/{id}/gemini), which
    stores it so the dashboard shows it, and applies the rules:
      confident false alarm  -> event row (and its clip file) deleted
      confident jersey read that differs from / fills in our player -> event updated
Any error = event left untouched (fails safe).
Only the FIRST event id of a clip is judged (that is the boxed player).

Keys:  AIza... and AQ....  -> Gemini Developer API (AI Studio)
       Vertex AI is opt-in only: set GEMINI_USE_VERTEX=1 (needs billing enabled)
"""

import os
import json
import time
import queue
import threading

import cv2
import requests
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))

for _p in (
    os.path.join(_HERE, ".env"),
    os.path.join(_HERE, "..", ".env"),
    os.path.join(_HERE, "..", "backend", ".env"),
):
    if os.path.isfile(_p):
        load_dotenv(_p)

# ============================================
# SETTINGS
# ============================================

# Force one model without editing code:  $env:GEMINI_MODEL="gemini-3.5-flash-lite"
_ENV_MODEL = os.getenv("GEMINI_MODEL", "").strip()

FALSE_ALARM_CONFIDENCE = 0.85   # delete an event only if Gemini is at least this sure it is NOT a fall
JERSEY_CONFIDENCE = 0.85        # replace/fill the player only if the jersey read is at least this sure
DECIDED_CONFIDENCE = 0.60       # below this the verdict is stored as "unsure"
MAX_SEQUENCE_FRAMES = 6         # surrounding frames sent besides the fall frame and the crop
JPEG_QUALITY = 85
MAX_RETRIES = 2
SHUTDOWN_TIMEOUT_SEC = 180

API_BASE = os.getenv("ATHLETEGUARD_API", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT = 20

# Optional: set to a callable(text) to send a correction message (e.g. WhatsApp)
notify_hook = None

# ============================================
# STATE READ BY multi_player_injury.py
# ============================================

player_changes = {}        # event_id -> new player name
deleted_event_ids = set()  # event ids Gemini removed as false alarms
stats = {
    "checked": 0,
    "false_alarm_deleted": 0,
    "reassigned": 0,
    "identified": 0,
    "errors": 0,
}

_client = None
_types = None
_models = []
_queue = queue.Queue()
_worker = None


def is_available():
    return _client is not None


# ============================================
# LIFECYCLE
# ============================================

def init():
    """Creates the Gemini client. Returns True when Gemini can be used."""
    global _client, _types, _models

    if _client is not None:
        return True

    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

    if not key:
        print("[GEMINI] No GEMINI_API_KEY found - Gemini check disabled.")
        return False

    try:
        from google import genai
        from google.genai import types

        # Vertex AI is opt-in only. AI Studio keys (AIza... AND AQ....) use the normal client.
        use_vertex = os.getenv("GEMINI_USE_VERTEX", "").strip() == "1"

        if use_vertex:
            _client = genai.Client(vertexai=True, api_key=key)
            candidates = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
            mode = "Vertex AI express"
        else:
            _client = genai.Client(api_key=key)
            candidates = [
                "gemini-3.5-flash-lite",
                "gemini-3.8-flash",
                "gemini-3.5-flash",
                "gemini-3.1-flash-lite",
                "gemini-flash-latest",
            ]
            mode = "Gemini API"

        _types = types
        _models = [_ENV_MODEL] if _ENV_MODEL else candidates

    except Exception as e:
        print("[GEMINI] Could not start (pip install google-genai):", e)
        _client = None
        return False

    print("[GEMINI] Second-opinion check ON |", mode, "| model:", _models[0])
    return True


def start():
    global _worker

    if not init():
        return

    _worker = threading.Thread(target=_worker_loop, daemon=True)
    _worker.start()


def submit(ids, raw_frames, target_index, target_box, context):
    if _client is None:
        return

    ids = [i for i in (ids or []) if i is not None]

    if not ids or not raw_frames:
        return

    _queue.put((ids, list(raw_frames), int(target_index), target_box, dict(context or {})))


def shutdown():
    if _worker is None:
        return

    pending = _queue.qsize()

    if pending:
        print("[GEMINI] Waiting for", pending, "pending check(s) to finish...")

    _queue.put(None)
    _worker.join(timeout=SHUTDOWN_TIMEOUT_SEC)

    if _worker.is_alive():
        print("[GEMINI] Timed out waiting for remaining checks - leaving them unchecked.")


def _worker_loop():
    while True:
        job = _queue.get()

        if job is None:
            break

        try:
            _process(job)
        except Exception as e:
            stats["errors"] += 1
            print("[GEMINI] Check failed (event kept as is):", e)


# ============================================
# IMAGES
# ============================================

def _jpeg(img):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return buf.tobytes() if ok else None


def _build_images(frames, target_index, box):
    """Returns [(label, jpeg_bytes), ...]"""

    n = len(frames)
    ti = max(0, min(target_index, n - 1))
    out = []

    h, w = frames[ti].shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, x2 = max(0, min(x1, w - 1)), max(0, min(x2, w - 1))
    y1, y2 = max(0, min(y1, h - 1)), max(0, min(y2, h - 1))

    # 1) fall-moment frame with the flagged player boxed
    annotated = frames[ti].copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
    cv2.putText(annotated, "TARGET", (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    data = _jpeg(annotated)
    if data:
        out.append(("Image 1 - fall-moment frame, flagged player in the green TARGET box:", data))

    # 2) zoomed crop of that player (raw, no overlay) for jersey reading
    pad_x = int((x2 - x1) * 0.25)
    pad_y = int((y2 - y1) * 0.25)
    cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)

    if cx2 - cx1 > 8 and cy2 - cy1 > 8:
        crop = frames[ti][cy1:cy2, cx1:cx2]
        scale = min(4.0, max(1.0, 640.0 / crop.shape[1]))
        if scale > 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        data = _jpeg(crop)
        if data:
            out.append(("Image 2 - zoomed crop of the flagged player:", data))

    # 3) a few chronological frames around the event (no boxes)
    if n <= MAX_SEQUENCE_FRAMES:
        picks = list(range(n))
    else:
        step = (n - 1) / float(MAX_SEQUENCE_FRAMES - 1)
        picks = sorted({int(round(i * step)) for i in range(MAX_SEQUENCE_FRAMES)} | {ti})

    for k, idx in enumerate(picks, start=1):
        data = _jpeg(frames[idx])
        if data:
            when = "FALL MOMENT" if idx == ti else ("before" if idx < ti else "after")
            out.append((f"Sequence frame {k}/{len(picks)} ({when}):", data))

    return out


# ============================================
# GEMINI CALL
# ============================================

def _prompt(context, team_names):
    teams = ", ".join(team_names) if team_names else "unknown"
    ctx = json.dumps(context, default=str)[:600] if context else "none"

    return f"""You are verifying an automatic fall detector on football (soccer) broadcast footage.
The detector flagged the player inside the green TARGET box in image 1 as having fallen / being on the ground.
Image 2 is a zoomed crop of that player. The remaining images are chronological frames around the event (no boxes).

Decide:
1. real_fall: true if the boxed player is genuinely on the ground from a fall, tackle, collision or injury.
   false for a FALSE ALARM: player upright/running/jumping, bending or tying boots, celebrating, a routine
   intentional slide or dive where the player immediately gets up, a referee / coach / ball boy / spectator,
   the wrong person boxed, or nothing visibly wrong. If the images are too unclear to judge, use low confidence.
2. confidence: 0.0-1.0 for that judgment (below 0.6 when unclear).
3. jersey_number: shirt number of the boxed player ONLY if clearly readable in the images, else null. Never guess.
4. jersey_confidence: 0.0-1.0 for the number read (0 if null).
5. team: the boxed player's team from [{teams}] judged from kit colours, else null.
6. description: one short sentence describing what happens to the player (e.g. "tackled from behind, lands on the left knee and stays down").
7. reason: one short sentence explaining your real_fall decision.

Detector context (may be partial): {ctx}

Reply with JSON only:
{{"real_fall": true, "confidence": 0.0, "jersey_number": null, "jersey_confidence": 0.0, "team": null, "description": "", "reason": ""}}"""


def _make_config():
    types = _types

    kwargs = dict(
        response_mime_type="application/json",
        temperature=0.0,
    )

    # Silences the harmless "automatic function calling" warning (skipped if this
    # version of google-genai doesn't have the option).
    afc_cls = getattr(types, "AutomaticFunctionCallingConfig", None)
    if afc_cls is not None:
        try:
            kwargs["automatic_function_calling"] = afc_cls(disable=True)
        except Exception:
            pass

    return types.GenerateContentConfig(**kwargs)


def _ask(images, context, team_names, prompt=None):
    global _models

    types = _types

    contents = []
    for label, data in images:
        contents.append(label)
        contents.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
    contents.append(prompt or _prompt(context, team_names))

    config = _make_config()

    last_error = None

    for attempt in range(MAX_RETRIES + 1):

        for model in list(_models):
            try:
                resp = _client.models.generate_content(model=model, contents=contents, config=config)
                text = (resp.text or "").strip()

                if text.startswith("```"):
                    text = text.strip("`")
                    if text.lower().startswith("json"):
                        text = text[4:]

                data = json.loads(text)

                if isinstance(data, list) and data:
                    data = data[0]

                # remember the model that worked
                if _models and _models[0] != model:
                    _models = [model] + [m for m in _models if m != model]

                return data

            except Exception as e:
                last_error = e
                msg = str(e)

                if any(s in msg for s in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")):
                    continue   # model missing, overloaded or rate-limited - try the next one

                break          # other errors: wait and retry

        time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Gemini request failed: {last_error}")


def _as_bool(v, default=True):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "no", "0")
    return default


def _as_float(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


# ============================================
# APPLY THE VERDICT (through the backend, so it is stored and shown in the dashboard)
# ============================================

def ask(images, prompt):
    """Public wrapper for verify_clips.py."""
    return _ask(images, None, None, prompt=prompt)


def to_backend(raw):
    """Gemini's JSON -> body for PATCH /events/{id}/gemini."""

    real_fall = _as_bool(raw.get("real_fall"), True)
    confidence = _as_float(raw.get("confidence"))

    if confidence < DECIDED_CONFIDENCE:
        verdict = "unsure"
    else:
        verdict = "real_fall" if real_fall else "false_alarm"

    try:
        jersey = int(raw.get("jersey_number")) if raw.get("jersey_number") is not None else None
    except (TypeError, ValueError):
        jersey = None

    team = str(raw.get("team") or "").strip() or None

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": str(raw.get("reason") or "")[:300] or None,
        "description": str(raw.get("description") or "")[:300] or None,
        "team": team,
        "jersey_number": jersey,
        "jersey_confidence": _as_float(raw.get("jersey_confidence")) if jersey is not None else None,
    }


def send_result(event_id, body, keep_false_alarm=False, min_jersey_confidence=JERSEY_CONFIDENCE):
    """Stores the verdict through the backend. Returns the backend's answer ({"action": ...})."""

    params = {"min_jersey_confidence": min_jersey_confidence}
    if keep_false_alarm:
        params["keep_false_alarm"] = "true"

    r = requests.patch(API_BASE + "/events/" + str(event_id) + "/gemini", json=body, params=params, timeout=API_TIMEOUT)

    if r.status_code == 404:
        return {"action": "missing"}

    r.raise_for_status()
    return r.json()


def team_names():
    try:
        from database import SessionLocal
        from models import Team
        db = SessionLocal()
        try:
            return [t.name for t in db.query(Team).order_by(Team.id).all()]
        finally:
            db.close()
    except Exception as e:
        print("[GEMINI] Could not read team names:", e)
        return []


def _notify(text):
    print("[GEMINI]", text)

    if notify_hook is not None:
        try:
            notify_hook(text)
        except Exception as e:
            print("[GEMINI] notify_hook failed:", e)


def apply_answer(event_id, body, answer, previous_player=None):
    """Updates the counters and prints/notifies what the backend did."""

    action = answer.get("action")
    event = answer.get("event") or {}
    conf = body.get("confidence") or 0.0

    if action == "deleted":
        deleted_event_ids.add(event_id)
        stats["false_alarm_deleted"] += 1
        _notify(
            f"Correction: event #{event_id} ({previous_player or 'Unidentified'}) was a false alarm and was removed "
            f"(confidence {conf:.2f}). {body.get('reason') or ''}"
        )

    elif action in ("identified", "reassigned"):
        name = event.get("player_name")
        player_changes[event_id] = name
        if action == "identified":
            stats["identified"] += 1
            _notify(f"Event #{event_id} identified by Gemini as {name} (#{body.get('jersey_number')}).")
        else:
            stats["reassigned"] += 1
            _notify(
                f"Correction: event #{event_id} was {previous_player}, now {name} (#{body.get('jersey_number')}) "
                f"per Gemini (confidence {(body.get('jersey_confidence') or 0):.2f})."
            )

    return action


def _process(job):
    ids, frames, target_index, box, context = job
    event_id = ids[0]   # the clip's target box belongs to the first event

    images = _build_images(frames, target_index, box)

    if not images:
        return

    raw = _ask(images, context, team_names())
    stats["checked"] += 1

    body = to_backend(raw)

    print(f"[GEMINI] #{event_id}: {body['verdict']} ({body['confidence']:.2f}) | "
          f"jersey={body['jersey_number']} ({(body['jersey_confidence'] or 0):.2f}) | "
          f"team={body['team']} | {body['reason']}")

    previous = (context or {}).get("player")

    # false alarms are removed only when Gemini is at least FALSE_ALARM_CONFIDENCE sure
    keep = body["verdict"] == "false_alarm" and body["confidence"] < FALSE_ALARM_CONFIDENCE

    answer = send_result(event_id, body, keep_false_alarm=keep, min_jersey_confidence=JERSEY_CONFIDENCE)
    apply_answer(event_id, body, answer, previous_player=previous)