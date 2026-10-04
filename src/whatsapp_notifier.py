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
CHAT_LOAD_TIMEOUT = 60   # seconds to wait for the chat box after a URL load
INPAGE_OPEN_TIMEOUT = 12 # seconds to wait for the chat to open without reloading
PREFILL_TIMEOUT = 15     # seconds to wait for URL-prefilled text (fallback mode)
START_ATTEMPTS = 3       # how many times to try launching Chrome
SEND_ATTEMPTS = 2        # attempt 1 = in-page (no reload), attempt 2 = URL fallback

_BOX_SELECTOR = "footer div[contenteditable='true']"
_TEXT_JS = "return (arguments[0].innerText || '').trim();"

# opens the chat inside the already-loaded page (no reload)
_OPEN_CHAT_JS = """
var a = document.createElement('a');
a.href = 'https://api.whatsapp.com/send?phone=' + arguments[0];
a.style.display = 'none';
document.body.appendChild(a);
a.click();
a.remove();
"""

# puts the WHOLE message in the box with one paste (keeps newlines and emoji)
_PASTE_JS = """
var box = arguments[0], text = arguments[1];
box.focus();
var dt = new DataTransfer();
dt.setData('text/plain', text);
box.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
"""


# ============================================
# INTERNAL STATE
# All Selenium work happens on ONE background
# thread, so the detection loop never blocks.
# ============================================

_queue = queue.Queue()
_worker = None
_lock = threading.Lock()
_state = {"chat_open": False}


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
    # keep WhatsApp Web responsive even when the window is behind other windows
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
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
    _state["chat_open"] = False

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


# ============================================
# SENDING
# Attempt 1: open the chat inside the loaded page
#            (NO reload) and paste the message.
# Attempt 2: fallback - old URL method (reloads).
# ============================================

def _box_text(driver, box):
    try:
        return driver.execute_script(_TEXT_JS, box)
    except Exception:
        return ""


def _find_box(driver, timeout):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, _BOX_SELECTOR))
    )


def _check_invalid_number(driver):

    from selenium.webdriver.common.by import By

    try:
        page = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return

    if "invalid" in page and "phone" in page:
        raise RuntimeError("WhatsApp says the phone number is invalid - check WHATSAPP_PHONE")


def _open_inpage(driver):
    """Returns the chat box without reloading the page."""

    if _state["chat_open"]:
        try:
            return _find_box(driver, 5)
        except Exception:
            _state["chat_open"] = False

    driver.execute_script(_OPEN_CHAT_JS, TARGET_PHONE)

    try:
        box = _find_box(driver, INPAGE_OPEN_TIMEOUT)
    except Exception:
        _check_invalid_number(driver)
        raise RuntimeError("chat did not open in-page")

    time.sleep(1)
    return box


def _open_by_url(driver, text):
    """Fallback: full page load with the text prefilled. Returns the chat box."""

    url = "https://web.whatsapp.com/send?phone=" + TARGET_PHONE + "&text=" + quote(text)

    driver.get(url)
    _dismiss_alert(driver)

    try:
        box = _find_box(driver, CHAT_LOAD_TIMEOUT)
    except Exception:
        _check_invalid_number(driver)
        raise RuntimeError("chat box did not appear within " + str(CHAT_LOAD_TIMEOUT) + "s")

    # wait until the prefilled text stops changing
    last_len = -1
    stable_since = None
    deadline = time.time() + PREFILL_TIMEOUT

    while time.time() < deadline:
        current = _box_text(driver, box)

        if current:
            if len(current) == last_len:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= 1.0:
                    break
            else:
                stable_since = None
                last_len = len(current)

        time.sleep(0.3)

    return box


def _send(driver, text, use_url):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait

    _dismiss_alert(driver)

    try:
        if use_url:
            _state["chat_open"] = False
            box = _open_by_url(driver, text)

        else:
            box = _open_inpage(driver)

            # clear any leftover draft, then paste the whole message at once
            box.click()
            box.send_keys(Keys.CONTROL, "a")
            box.send_keys(Keys.DELETE)
            time.sleep(0.3)

            driver.execute_script(_PASTE_JS, box, text)
            time.sleep(0.8)

        typed = _box_text(driver, box)

        _log("[WHATSAPP] Box has", len(typed), "characters; message is", len(text.strip()), "characters")

        if len(typed) < max(1, int(len(text.strip()) * 0.8)):
            raise RuntimeError("full message did not get into the chat box")

        _state["chat_open"] = True

        box.click()
        box.send_keys(Keys.ENTER)

        emptied = False

        try:
            WebDriverWait(driver, 6).until(lambda d: not _box_text(d, box))
            emptied = True
        except Exception:
            pass

        if not emptied:
            try:
                driver.find_element(
                    By.CSS_SELECTOR, "button[aria-label='Send'], span[data-icon='send']"
                ).click()
            except Exception:
                pass

            try:
                WebDriverWait(driver, 8).until(lambda d: not _box_text(d, box))
                emptied = True
            except Exception:
                pass

        if not emptied:
            raise RuntimeError("message stayed in the chat box (not sent)")

        # wait for the clock icon (still sending) to go away
        deadline = time.time() + 20

        while time.time() < deadline:
            try:
                if len(driver.find_elements(By.CSS_SELECTOR, "span[data-icon='msg-time']")) == 0:
                    break
            except Exception:
                break
            time.sleep(0.5)

        time.sleep(1)

    except Exception:
        _state["chat_open"] = False
        raise


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

        for attempt in range(1, SEND_ATTEMPTS + 1):

            try:
                _send(driver, text, use_url=(attempt > 1))
                _log("[WHATSAPP] Message sent to", TARGET_PHONE)
                sent = True
                break

            except Exception as e:
                err = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
                _log("[WHATSAPP] Send attempt", attempt, "of", SEND_ATTEMPTS, "failed:", err)
                _dismiss_alert(driver)
                time.sleep(2)

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