import os
import queue
import subprocess
import sys
import threading
import time
from urllib.parse import quote

try:
    from dotenv import load_dotenv
except Exception:          # python-dotenv is optional here
    load_dotenv = None


_HERE = os.path.dirname(os.path.abspath(__file__))

# Lets you keep WHATSAPP_PHONE in src\.env next to GEMINI_API_KEY
if load_dotenv is not None:
    for _p in (os.path.join(_HERE, ".env"), os.path.join(_HERE, "..", ".env")):
        if os.path.isfile(_p):
            load_dotenv(_p)


# ============================================
# CONFIG
# ============================================

ENABLED = True

# Receiving number: country code + number, digits only, no "+" or spaces. e.g. 919876543210
# Set it in src\.env as:  WHATSAPP_PHONE=919876543210
TARGET_PHONE = os.environ.get("WHATSAPP_PHONE", "91XXXXXXXXXX").strip()

PROJECT_ROOT = os.path.dirname(_HERE)

# Dedicated Chrome profile so the WhatsApp Web login (QR scan) is remembered
PROFILE_DIR = os.path.join(PROJECT_ROOT, "output", "whatsapp_profile")

LOGIN_TIMEOUT = 120      # seconds to wait for QR scan / WhatsApp Web load
CHAT_LOAD_TIMEOUT = 45   # seconds to wait for the chat to open
START_ATTEMPTS = 3       # how many times to try launching Chrome


# ============================================
# INTERNAL STATE
# All Selenium work happens on ONE background
# thread, so the detection loop never blocks.
# ============================================

_queue = queue.Queue()
_worker = None
_lock = threading.Lock()


def _log(*parts):
    """print() that can never crash on emoji / odd characters (Windows cp1252 consoles)."""
    text = " ".join(str(p) for p in parts)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def _phone_ok():
    return TARGET_PHONE.isdigit() and len(TARGET_PHONE) >= 8


# ============================================
# CHROME CLEAN-UP (the usual cause of
# "DevToolsActivePort file doesn't exist")
# ============================================

def _kill_profile_chrome():
    """Kill only the Chrome processes that use OUR WhatsApp profile (never your normal Chrome)."""

    if os.name != "nt":
        try:
            subprocess.run(["pkill", "-f", "whatsapp_profile"], capture_output=True, timeout=10)
        except Exception:
            pass
        return

    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -like '*whatsapp_profile*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def _remove_stale_locks(profile_dir):
    for rel in (
        "DevToolsActivePort",
        "lockfile",
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        os.path.join("Default", "LOCK"),
    ):
        path = os.path.join(profile_dir, rel)
        try:
            if os.path.lexists(path):
                os.remove(path)
        except OSError:
            pass


def _build_options(profile_dir):

    from selenium import webdriver

    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=" + profile_dir)
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    return options


def _create_driver():
    """Start Chrome with clean-up and retries. Falls back to a fresh profile as a last resort."""

    from selenium import webdriver

    last_error = None
    profile_dir = PROFILE_DIR

    for attempt in range(1, START_ATTEMPTS + 1):

        # last attempt: the saved profile may be corrupted / from another Chrome version
        if attempt == START_ATTEMPTS and START_ATTEMPTS > 1:
            profile_dir = PROFILE_DIR + "_fresh"
            _log("[WHATSAPP] Trying a fresh profile - you will need to scan the QR code again.")

        _kill_profile_chrome()
        os.makedirs(profile_dir, exist_ok=True)
        _remove_stale_locks(profile_dir)

        try:
            driver = webdriver.Chrome(options=_build_options(profile_dir))
            return driver

        except Exception as e:
            last_error = e
            first_line = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
            _log("[WHATSAPP] Chrome start attempt", attempt, "of", START_ATTEMPTS, "failed:", first_line)
            time.sleep(3)

    raise last_error


def _wait_for_login(driver):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get("https://web.whatsapp.com")

    _log("[WHATSAPP] Opening WhatsApp Web... scan the QR code in Chrome if asked.")

    def logged_in(d):
        return (
            len(d.find_elements(By.ID, "pane-side")) > 0
            or len(d.find_elements(By.CSS_SELECTOR, "div[aria-label='Chat list']")) > 0
        )

    WebDriverWait(driver, LOGIN_TIMEOUT).until(logged_in)

    _log("[WHATSAPP] Logged in and ready.")


def _dismiss_alert(driver):
    """WhatsApp/Chrome can show a 'Leave site?' dialog that blocks the next navigation."""

    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass


def _driver_alive(driver):
    try:
        _ = driver.title
        return True
    except Exception:
        return False


def _start_session():
    """Returns a logged-in driver, or None if it could not be started."""

    driver = None

    try:
        driver = _create_driver()
        _wait_for_login(driver)
        return driver

    except Exception as e:
        first_line = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
        _log("[WHATSAPP] Could not start WhatsApp Web - messages will be retried on the next alert:", first_line)

        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

        return None


def _send(driver, text):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    _dismiss_alert(driver)

    url = "https://web.whatsapp.com/send?phone=" + TARGET_PHONE + "&text=" + quote(text)

    driver.get(url)

    _dismiss_alert(driver)

    try:
        box = WebDriverWait(driver, CHAT_LOAD_TIMEOUT).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "footer div[contenteditable='true']"))
        )
    except Exception:
        page = ""
        try:
            page = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            pass

        if "invalid" in page and "phone" in page:
            raise RuntimeError("WhatsApp says the phone number is invalid - check WHATSAPP_PHONE")

        raise

    time.sleep(1.5)

    try:
        box.send_keys(Keys.ENTER)
    except Exception:
        # fall back to clicking the send button
        driver.find_element(
            By.CSS_SELECTOR, "button[aria-label='Send'], span[data-icon='send']"
        ).click()

    # wait until the clock icon (message still sending) is gone, then a short extra pause
    deadline = time.time() + 15
    time.sleep(1.5)

    while time.time() < deadline:
        try:
            if len(driver.find_elements(By.CSS_SELECTOR, "span[data-icon='msg-time']")) == 0:
                break
        except Exception:
            break
        time.sleep(0.5)

    time.sleep(1.5)


def _worker_loop():

    driver = None

    if not _phone_ok():
        _log("[WHATSAPP] WHATSAPP_PHONE is not set (still '" + TARGET_PHONE + "').")
        _log("[WHATSAPP] Add  WHATSAPP_PHONE=919876543210  (country code + number) to src\\.env")

    else:
        driver = _start_session()

    while True:

        text = _queue.get()

        if text is None:
            break

        first_line = text.splitlines()[0] if text.strip() else "(empty)"

        if not _phone_ok():
            _log("[WHATSAPP] Skipped (no valid phone number):", first_line)
            continue

        # (re)start Chrome if it never started or has died
        if driver is None or not _driver_alive(driver):
            if driver is not None:
                _log("[WHATSAPP] Chrome window was closed - restarting it.")
                try:
                    driver.quit()
                except Exception:
                    pass
            driver = _start_session()

        if driver is None:
            _log("[WHATSAPP] Skipped (not logged in):", first_line)
            continue

        sent = False

        for attempt in range(1, 3):

            try:
                _send(driver, text)
                _log("[WHATSAPP] Message sent to", TARGET_PHONE)
                sent = True
                break

            except Exception as e:
                err = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
                _log("[WHATSAPP] Send attempt", attempt, "failed:", err)
                _dismiss_alert(driver)

        if not sent:
            _log("[WHATSAPP] Gave up on:", first_line)

    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass


# ============================================
# PUBLIC API
# ============================================

def start():
    """Open WhatsApp Web early so the QR scan can happen before detection starts."""

    global _worker

    if not ENABLED:
        return

    with _lock:

        if _worker is None or not _worker.is_alive():

            _worker = threading.Thread(target=_worker_loop, daemon=True)
            _worker.start()


def send_message(text):
    """Queue a message; returns immediately."""

    if not ENABLED:
        return

    start()

    _queue.put(text)


def shutdown(timeout=120):
    """Wait for queued messages to go out, then close Chrome."""

    if _worker is None:
        return

    _log("[WHATSAPP] Sending any remaining messages before exit...")

    _queue.put(None)

    _worker.join(timeout=timeout)


def build_alert_message(player_name, jersey_number, event_type, region, risk,
                        injury_note, match_name, when_text):

    player_line = player_name or "Unidentified"

    if jersey_number is not None:
        player_line += " (#" + str(jersey_number) + ")"

    lines = [
        "\U0001F6A8 AthleteGuard Alert",
        "Event: " + str(event_type),
        "Player: " + player_line,
        "Body area: " + str(region or "Unknown"),
        "Risk: " + str(risk or "-"),
    ]

    if injury_note:
        lines.append("Note: " + injury_note)

    if match_name:
        lines.append("Match: " + match_name)

    lines.append("Time: " + when_text)

    return "\n".join(lines)
