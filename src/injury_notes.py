# ============================================
# AUTOMATIC INJURY NOTE
# Short, plain-language hint based on how hard
# the fall looked (risk) and which body area was
# involved. Always carries a disclaimer: this is
# an AI estimate, never a medical diagnosis.
# ============================================

DISCLAIMER = "AI estimate only, not a medical diagnosis"


def _area(region):

    if region is None:
        return "UNKNOWN"

    region = region.upper()

    if "HEAD" in region:
        return "HEAD"

    if "NECK" in region:
        return "NECK"

    if "LEG" in region:
        return "LEG"

    if "ARM" in region:
        return "ARM"

    if "TORSO" in region:
        return "TORSO"

    return "UNKNOWN"


NOTES = {

    "HIGH": {
        "HEAD": "Possible concussion or head injury — high-impact fall",
        "NECK": "Possible neck/spinal strain — high-impact fall, do not move player",
        "LEG": "Possible fracture or ligament injury — high-impact fall",
        "ARM": "Possible fracture or dislocation — high-impact fall",
        "TORSO": "Possible rib or back injury — high-impact fall",
        "UNKNOWN": "Possible serious injury — high-impact fall",
    },

    "MEDIUM": {
        "HEAD": "Possible head knock — watch for concussion signs",
        "NECK": "Possible neck strain",
        "LEG": "Possible sprain or muscle strain",
        "ARM": "Possible sprain or bruising",
        "TORSO": "Possible bruising or muscle strain",
        "UNKNOWN": "Possible sprain or strain",
    },

    "LOW": {
        "HEAD": "Minor head contact — likely a knock",
        "NECK": "Minor neck movement — likely no injury",
        "LEG": "Likely minor — possible bruise or knock",
        "ARM": "Likely minor — possible bruise or knock",
        "TORSO": "Likely minor — possible bruise",
        "UNKNOWN": "Likely minor — possible bruise or knock",
    },
}


def build_injury_note(event_type, region, risk):

    event_type = (event_type or "").upper()

    if event_type == "COLLISION":
        return "Player contact detected — check both players (" + DISCLAIMER + ")"

    risk = (risk or "LOW").upper()

    if risk not in NOTES:
        risk = "LOW"

    text = NOTES[risk][_area(region)]

    return text + " (" + DISCLAIMER + ")"


# ============================================
# RECOMMENDED SAFETY MEASURES
# First-aid and referral steps based on the body
# area and risk. Shown on the dashboard and added
# to WhatsApp alerts. AI suggestion only: medical
# staff make the final decision.
# Keep this text in sync with SAFETY_MEASURES in
# frontend/src/pages/Dashboard.jsx
# ============================================

SAFETY_DISCLAIMER = "AI suggestion based on body area and risk, medical staff must confirm"

SAFETY_MEASURES = {

    "HIGH": {
        "HEAD": [
            "Remove the player from play immediately",
            "Do not move the player if unconscious or confused",
            "Call emergency medical services",
            "CT scan of the head",
        ],
        "NECK": [
            "Do not move the player",
            "Keep the head and neck still (manual in-line support)",
            "Spinal board and emergency transfer",
            "CT or MRI of the cervical spine",
        ],
        "TORSO": [
            "Check breathing and abdominal pain",
            "Emergency transfer if breathing is difficult",
            "Chest X-ray",
            "Abdominal ultrasound or CT for internal injury",
        ],
        "ARM": [
            "Splint the arm in the position found",
            "Check pulse and colour below the injury",
            "X-ray",
            "Orthopaedic referral",
        ],
        "LEG": [
            "Do not let the player stand",
            "Splint the leg and use a stretcher",
            "X-ray",
            "MRI for ligament (ACL) damage",
            "Orthopaedic referral",
        ],
        "UNKNOWN": [
            "Remove the player from play",
            "Full medical assessment on the pitch",
            "Emergency transfer if any serious sign",
            "Imaging (X-ray / CT) as advised by the doctor",
        ],
    },

    "MEDIUM": {
        "HEAD": [
            "Remove the player from play",
            "Sideline concussion check (SCAT)",
            "No return the same day if any symptom",
            "Doctor review",
        ],
        "NECK": [
            "Remove the player from play",
            "Check for numbness or tingling in the arms",
            "X-ray if pain persists",
        ],
        "TORSO": [
            "Check rib pain and breathing",
            "Chest X-ray if breathing hurts",
        ],
        "ARM": [
            "Support the arm in a sling",
            "X-ray if swelling or deformity",
        ],
        "LEG": [
            "No weight-bearing",
            "Ice and compression",
            "X-ray",
            "Physio review",
        ],
        "UNKNOWN": [
            "Remove the player from play",
            "Medical check before returning",
        ],
    },

    "LOW": {
        "HEAD": [
            "Check for concussion signs (confusion, headache, dizziness)",
            "Monitor for 24 hours",
        ],
        "NECK": [
            "Check neck movement",
            "Stop play if any pain",
        ],
        "TORSO": [
            "Ice",
            "Watch breathing",
        ],
        "ARM": [
            "Rest, ice, compression, elevation (RICE)",
            "Check grip strength",
        ],
        "LEG": [
            "Rest, ice, compression, elevation (RICE)",
            "Must bear weight before returning to play",
        ],
        "UNKNOWN": [
            "Check the player before they continue",
            "Monitor for any pain",
        ],
    },
}

COLLISION_MEASURES = [
    "Check both players",
    "Follow the safety measures for any player who stays down",
]


def build_safety_measures(event_type, region, risk):
    """Returns a list of recommended steps. Never raises."""

    try:
        if (event_type or "").upper().startswith("COLLISION"):
            return list(COLLISION_MEASURES)

        risk = (risk or "LOW").upper()

        if risk not in SAFETY_MEASURES:
            risk = "LOW"

        return list(SAFETY_MEASURES[risk][_area(region)])

    except Exception:
        return []