"""
test_whatsapp.py - checks the WhatsApp alert on its own, without running the detector.

Run from the src folder:   python test_whatsapp.py
Chrome opens; scan the QR code if asked. A test message is sent to WHATSAPP_PHONE.
"""

import whatsapp_notifier as w

print("Phone configured:", w._phone_ok())
print("Profile folder  :", w.PROFILE_DIR)

w.start()
w.send_message("AthleteGuard test message - if you can read this, WhatsApp alerts work.")
w.shutdown(timeout=240)

print("Done. Check your phone.")
