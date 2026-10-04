"""
gemini_verifier.py - Gemini second opinion on every saved fall.

Interface used by multi_player_injury.py:
    start(), submit(ids, raw_frames, target_index, target_box, context),
    shutdown(), is_available(), player_changes, deleted_event_ids, stats

What it does for each saved fall (runs in a background thread):
  - Sends the fall-moment frame (target player boxed), a zoomed crop and a few
    surrounding frames to Gemini.
  - Confident false alarm  -> event row (and its clip file) deleted.
  - Confident jersey read that differs from / fills in our player -> event updated.
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
MAX_SEQUENCE_FRAMES = 6         # surrounding frames sent besides the fall frame and the crop
JPEG_QUALITY = 85
MAX_RETRIES = 2
SHUTDOWN_TIMEOUT_SEC = 180

clips_dir = os.path.join(_HERE, "output", "clips")

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

def start():
    global _client, _types, _worker, _models

    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

    if not key:
        print("[GEMINI] No GEMINI_API_KEY found - Gemini check disabled.")
        return

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
        return

    _worker = threading.Thread(target=_worker_loop, daemon=True)
    _worker.start()

    print("[GEMINI] Second-opinion check ON |", mode, "| model:", _models[0])


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
6. reason: one short sentence.

Detector context (may be partial): {ctx}

Reply with JSON only:
{{"real_fall": true, "confidence": 0.0, "jersey_number": null, "jersey_confidence": 0.0, "team": null, "reason": ""}}"""


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


def _ask(images, context, team_names):
    global _models

    types = _types

    contents = []
    for label, data in images:
        contents.append(label)
        contents.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
    contents.append(_prompt(context, team_names))

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
# APPLY THE VERDICT
# ============================================

def _notify(text):
    print("[GEMINI]", text)

    if notify_hook is not None:
        try:
            notify_hook(text)
        except Exception as e:
            print("[GEMINI] notify_hook failed:", e)


def _delete_clip_file(clip_path):
    if not clip_path:
        return

    for folder in (clips_dir, os.path.join(os.getcwd(), "output", "clips")):
        path = os.path.join(folder, clip_path)
        if os.path.isfile(path):
            try:
                os.remove(path)
                return
            except OSError:
                pass


def _process(job):
    from database import SessionLocal
    from models import InjuryEvent, Player, Team

    ids, frames, target_index, box, context = job
    event_id = ids[0]   # the clip's target box belongs to the first event

    db = SessionLocal()

    try:
        ev = db.get(InjuryEvent, event_id)

        if ev is None:
            return

        team_names = [t.name for t in db.query(Team).all()]

        images = _build_images(frames, target_index, box)

        if not images:
            return

        verdict = _ask(images, context, team_names)

        stats["checked"] += 1

        real_fall = _as_bool(verdict.get("real_fall"), True)
        confidence = _as_float(verdict.get("confidence"))
        reason = str(verdict.get("reason") or "")[:200]

        # ---- confident false alarm -> delete ----
        if not real_fall and confidence >= FALSE_ALARM_CONFIDENCE:
            who = ev.player.name if ev.player else "Unidentified"
            clip_path = ev.clip_path

            db.delete(ev)
            db.commit()

            _delete_clip_file(clip_path)

            deleted_event_ids.add(event_id)
            stats["false_alarm_deleted"] += 1

            _notify(
                f"Correction: event #{event_id} ({who}) was a false alarm and was removed "
                f"(confidence {confidence:.2f}). {reason}"
            )
            return

        # ---- jersey read -> fill in / replace the player ----
        jersey = verdict.get("jersey_number")
        jersey_conf = _as_float(verdict.get("jersey_confidence"))
        team_hint = str(verdict.get("team") or "").strip().lower()

        print(f"[GEMINI] #{event_id}: fall={real_fall} ({confidence:.2f}) | "
              f"jersey={jersey} ({jersey_conf:.2f}) | team={team_hint or None} | {reason}")

        try:
            jersey = int(jersey) if jersey is not None else None
        except (TypeError, ValueError):
            jersey = None

        if jersey is None:
            print(f"[GEMINI] #{event_id}: no readable jersey number -> player unchanged")
            return

        if jersey_conf < JERSEY_CONFIDENCE:
            print(f"[GEMINI] #{event_id}: jersey #{jersey} too uncertain "
                  f"({jersey_conf:.2f} < {JERSEY_CONFIDENCE}) -> player unchanged")
            return

        candidates = db.query(Player).filter(Player.jersey_number == jersey).all()

        if not candidates:
            print(f"[GEMINI] #{event_id}: no player with jersey #{jersey} in the roster")
            return

        if len(candidates) > 1:
            teams_by_id = {t.id: t.name.lower() for t in db.query(Team).all()}
            narrowed = [
                p for p in candidates
                if team_hint and (
                    teams_by_id.get(p.team_id, "") == team_hint
                    or team_hint in teams_by_id.get(p.team_id, "")
                    or teams_by_id.get(p.team_id, "") in team_hint
                )
            ]
            if len(narrowed) != 1:
                print(f"[GEMINI] #{event_id}: jersey #{jersey} exists in {len(candidates)} teams "
                      f"and team '{team_hint}' did not pick one -> unchanged")
                return
            candidates = narrowed

        if len(candidates) != 1:
            return

        new_player = candidates[0]

        if ev.player_id == new_player.id:
            return

        old_conf = ev.identification_confidence or ev.id_confidence or 0.0
        old_name = ev.player.name if ev.player else None

        if ev.player_id is not None and old_conf >= jersey_conf:
            return   # our existing read is at least as sure

        ev.player_id = new_player.id
        ev.identification_method = "gemini"
        ev.identified_by = "gemini"
        ev.identification_confidence = jersey_conf
        ev.id_confidence = jersey_conf
        ev.id_detail = f"gemini jersey #{jersey}"
        db.commit()

        player_changes[event_id] = new_player.name

        if old_name is None:
            stats["identified"] += 1
            _notify(f"Event #{event_id} identified by Gemini as {new_player.name} (#{jersey}).")
        else:
            stats["reassigned"] += 1
            _notify(
                f"Correction: event #{event_id} was {old_name}, now {new_player.name} (#{jersey}) "
                f"per Gemini (confidence {jersey_conf:.2f})."
            )

    finally:
        db.close()