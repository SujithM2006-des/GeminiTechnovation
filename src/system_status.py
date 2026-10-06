# ============================================
# SYSTEM STATUS REPORTER
# Tells the backend what the detector is using (model, tracker, OCR,
# face matching, versions) and that it is still running, so the
# dashboard's System page shows real information.
#
# Safe by design:
#   - every request runs in a background thread with a short timeout,
#     so detection never waits for it
#   - if the backend is down, it prints one warning and carries on
#   - nothing here can stop or crash the detector
# ============================================

import os
import sys
import threading
import time

import requests

API_BASE = "http://127.0.0.1:8000"
HEARTBEAT_SECONDS = 5          # backend marks the detector "stopped" after 30 s of silence
REQUEST_TIMEOUT = 3

_info = {}
_progress = {}
_lock = threading.Lock()
_stop = threading.Event()
_thread = None
_warned = False

# libraries that are only imported when they are actually used
_OCR_LIBRARIES = [
    ("easyocr", "EasyOCR"),
    ("paddleocr", "PaddleOCR"),
    ("rapidocr_onnxruntime", "RapidOCR"),
    ("pytesseract", "Tesseract"),
    ("doctr", "docTR"),
]
_FACE_LIBRARIES = [
    ("insightface", "InsightFace"),
    ("face_recognition", "face_recognition (dlib)"),
    ("deepface", "DeepFace"),
    ("facenet_pytorch", "FaceNet (PyTorch)"),
]


def _send(state, info=None):
    global _warned
    with _lock:
        progress = dict(_progress)
    try:
        requests.post(
            API_BASE + "/system/detector-status",
            json={"state": state, "info": info or {}, "progress": progress},
            timeout=REQUEST_TIMEOUT,
        )
        _warned = False
    except Exception as e:
        if not _warned:
            print("[STATUS] Could not reach the backend for the System page (detection continues):", e)
            _warned = True


def _heartbeat_loop():
    while not _stop.wait(HEARTBEAT_SECONDS):
        _send("running")


def loaded_libraries(candidates):
    """Names of the libraries from the list that this process has actually imported."""
    return [label for module, label in candidates if module in sys.modules]


def library_version(module_name):
    module = sys.modules.get(module_name)
    return getattr(module, "__version__", None) if module is not None else None


def tracker_details(path):
    """Tracker type and whether appearance re-identification is on, read from the tracker .yaml."""
    details = {"tracker_file": os.path.basename(path), "tracker_type": None, "tracker_reid": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                key, _, value = line.split("#", 1)[0].partition(":")
                key, value = key.strip(), value.strip().strip("'\"")
                if key == "tracker_type":
                    details["tracker_type"] = value
                elif key == "with_reid":
                    details["tracker_reid"] = value.lower() == "true"
    except Exception:
        if details["tracker_file"].lower().startswith("botsort"):
            details["tracker_type"] = "botsort"
        elif details["tracker_file"].lower().startswith("bytetrack"):
            details["tracker_type"] = "bytetrack"
    return details


def start(info):
    """Call once when the detector is ready. info = what it is using."""
    global _thread, _info
    try:
        _info = dict(info)
        _info["pid"] = os.getpid()
        threading.Thread(target=_send, args=("starting", _info), daemon=True).start()
        _stop.clear()
        _thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        _thread.start()
        print("[STATUS] Reporting to the dashboard System page every", HEARTBEAT_SECONDS, "s")
    except Exception as e:
        print("[STATUS] Status reporting disabled:", e)


def update(**progress):
    """Cheap: only stores numbers. They are sent with the next heartbeat."""
    with _lock:
        _progress.update(progress)


def add_info(**info):
    """Extra details learned while running (e.g. face recognition switched on)."""
    try:
        _info.update(info)
        threading.Thread(target=_send, args=("running", dict(info)), daemon=True).start()
    except Exception:
        pass


def finish(**progress):
    """Call once at the end of the run."""
    try:
        update(**progress)
        _stop.set()
        _send("finished")
    except Exception:
        pass