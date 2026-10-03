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