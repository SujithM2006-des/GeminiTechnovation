"""
injury_catalog.py - the possible injuries per body area, with risk, first safety measure
and typical rest / return-to-play time.

Used by gemini_injury.py: Gemini may only pick injuries from this list, and the risk,
safety measure and rest time always come from here (never invented by Gemini).

AI estimate only, not a medical diagnosis. Return to play is always a medical decision.
"""

# (injury, risk, safety measure, typical rest / return to play)
CATALOG = {
    "Head": [
        ("Concussion", "Critical", "Remove from play; medical assessment", "2-4+ weeks"),
        ("Mild traumatic brain injury", "Critical", "Immediate medical evaluation", "2-6+ weeks"),
        ("Scalp laceration", "Medium", "Stop bleeding; clean/dress wound", "1-2 weeks"),
        ("Facial contusion", "Medium", "Ice/protection; assess vision", "1-2 weeks"),
        ("Nasal fracture", "High", "Stop play; medical assessment", "2-6 weeks"),
        ("Orbital fracture", "Critical", "No play; urgent assessment", "4-8+ weeks"),
        ("Jaw fracture", "Critical", "Immobilize/support; emergency care", "6-8+ weeks"),
        ("Dental trauma", "High", "Protect tooth; urgent dental care", "1-4 weeks"),
        ("Cervical strain", "High", "Stop play; medical assessment", "1-6 weeks"),
        ("Whiplash", "High", "Stop activity; medical assessment", "1-6 weeks"),
        ("Skull fracture", "Critical", "Emergency medical care", "6-12+ weeks"),
        ("Post-concussion symptoms", "High", "Avoid contact; medical supervision", "2-8+ weeks"),
        ("Head hematoma", "High", "Medical assessment; monitor symptoms", "1-4+ weeks"),
        ("Dizziness after head impact", "High", "Remove from play immediately", "Until medically cleared"),
        ("Loss of consciousness", "Critical", "Emergency assessment", "Individual"),
    ],
    "Shoulder": [
        ("Shoulder dislocation", "Critical", "Immobilize; emergency/orthopedic assessment", "4-12 weeks"),
        ("Shoulder subluxation", "High", "Stop play; immobilize if painful", "2-6 weeks"),
        ("AC joint sprain", "Medium-High", "Rest, ice, support", "2-8 weeks"),
        ("Rotator cuff strain", "Medium", "Stop painful movement; rehab", "1-6 weeks"),
        ("Rotator cuff tear", "High", "Medical assessment", "6-12+ weeks"),
        ("Shoulder contusion", "Medium", "Ice; rest", "1-2 weeks"),
        ("Labral injury", "High", "Stop overhead/contact activity", "4-12+ weeks"),
        ("Clavicle fracture", "Critical", "Immobilize; medical evaluation", "6-12 weeks"),
        ("Shoulder impingement", "Medium", "Reduce overhead activity", "2-8 weeks"),
        ("Biceps tendon strain", "Medium", "Rest; gradual rehabilitation", "2-6 weeks"),
        ("Biceps tendon tear", "High", "Medical assessment", "6-12+ weeks"),
        ("Deltoid strain", "Medium", "Rest; gradual strengthening", "1-4 weeks"),
        ("Shoulder bursitis", "Medium", "Rest; avoid painful movements", "1-6 weeks"),
        ("Scapular fracture", "Critical", "Immobilization and urgent assessment", "6-12+ weeks"),
        ("AC joint separation", "High", "Support/immobilization; assessment", "2-12 weeks"),
    ],
    "Elbow": [
        ("Elbow sprain", "Medium", "Rest/support", "1-4 weeks"),
        ("Elbow dislocation", "Critical", "Immobilize; emergency assessment", "4-12 weeks"),
        ("Elbow fracture", "Critical", "Immobilize; urgent X-ray", "6-12+ weeks"),
        ("Radial head fracture", "High", "Immobilize; medical assessment", "4-8 weeks"),
        ("Olecranon fracture", "High", "Immobilize; orthopedic assessment", "6-12 weeks"),
        ("UCL injury", "High", "Stop throwing/contact activity", "4-12+ weeks"),
        ("Tendinitis", "Medium", "Rest; gradual rehabilitation", "2-8 weeks"),
        ("Bursitis", "Medium", "Rest; avoid pressure", "1-4 weeks"),
        ("Elbow contusion", "Medium", "Ice/protection", "1-2 weeks"),
        ("Triceps strain", "Medium", "Rest; progressive strengthening", "1-6 weeks"),
        ("Triceps tendon tear", "High", "Medical assessment", "6-16+ weeks"),
        ("Lateral epicondylitis", "Medium", "Reduce painful activity", "2-8+ weeks"),
        ("Medial epicondylitis", "Medium", "Rest/rehab", "2-8+ weeks"),
        ("Nerve injury", "High", "Stop activity; medical assessment", "Variable"),
        ("Olecranon bursitis", "Medium", "Avoid pressure; assessment", "1-6 weeks"),
    ],
    "Wrist / Hand": [
        ("Wrist sprain", "Medium", "Support; rest/ice", "1-6 weeks"),
        ("Wrist fracture", "High", "Immobilize; X-ray", "6-12 weeks"),
        ("Scaphoid fracture", "High", "Immobilize; medical assessment", "6-12+ weeks"),
        ("Colles fracture", "High", "Immobilize; orthopedic care", "6-12 weeks"),
        ("Finger fracture", "Medium-High", "Splint/protect", "3-6 weeks"),
        ("Finger dislocation", "High", "Medical reduction", "2-6 weeks"),
        ("Thumb sprain", "Medium", "Support/splint", "2-6 weeks"),
        ("Thumb ligament injury", "High", "Immobilize; assessment", "4-8+ weeks"),
        ("TFCC injury", "High", "Avoid loading wrist", "4-12+ weeks"),
        ("Tendon strain", "Medium", "Rest; gradual rehab", "1-6 weeks"),
        ("Tendon rupture", "High", "Medical/surgical assessment", "8-16+ weeks"),
        ("Hand contusion", "Low-Medium", "Ice/protection", "1-2 weeks"),
        ("Metacarpal fracture", "High", "Immobilize", "4-8 weeks"),
        ("Wrist tendinitis", "Medium", "Rest; reduce repetitive activity", "2-6 weeks"),
        ("Joint inflammation", "Medium", "Rest; assessment if persistent", "1-4 weeks"),
    ],
    "Hip / Pelvis": [
        ("Hip flexor strain", "Medium", "Stop sprinting/kicking", "1-6 weeks"),
        ("Groin/adductor strain", "Medium-High", "Stop kicking; rehab", "1-8+ weeks"),
        ("Hip contusion", "Medium", "Rest/ice", "1-3 weeks"),
        ("Hip dislocation", "Critical", "Emergency care; immobilization", "8-16+ weeks"),
        ("Femoral neck fracture", "Critical", "No weight bearing; emergency care", "8-16+ weeks"),
        ("Labral tear", "High", "Medical assessment", "4-12+ weeks"),
        ("Hip bursitis", "Medium", "Reduce impact", "1-6 weeks"),
        ("Hip impingement", "Medium-High", "Modify activity; assessment", "2-8+ weeks"),
        ("Gluteal strain", "Medium", "Rest; gradual strengthening", "1-6 weeks"),
        ("Gluteal tendon injury", "Medium-High", "Reduce running; rehab", "4-12 weeks"),
        ("Hamstring origin injury", "High", "Stop sprinting", "2-12+ weeks"),
        ("Pelvic contusion", "Medium", "Rest/protection", "1-3 weeks"),
        ("Pelvic fracture", "Critical", "Emergency assessment", "8-16+ weeks"),
        ("Avulsion injury", "High", "Stop activity; imaging", "6-12+ weeks"),
        ("Sacroiliac joint injury", "Medium-High", "Rest; clinical assessment", "2-8 weeks"),
    ],
    "Knee": [
        ("ACL tear", "Critical", "Stop play; orthopedic assessment", "6-12+ months"),
        ("ACL sprain", "High", "Stop pivoting; assessment", "2-12+ weeks"),
        ("MCL sprain", "Medium-High", "Protect knee; rehab", "1-8 weeks"),
        ("LCL sprain", "High", "Stop play; assessment", "2-12 weeks"),
        ("Meniscus tear", "High", "Avoid twisting; assessment", "2-12+ weeks"),
        ("Patellar dislocation", "High", "Immobilize; medical assessment", "4-12 weeks"),
        ("Patellar tendon strain", "Medium", "Stop jumping/running", "2-8 weeks"),
        ("Patellar tendon rupture", "Critical", "Immobilize; urgent orthopedic care", "6-12+ months"),
        ("Knee contusion", "Medium", "Ice/rest", "1-3 weeks"),
        ("Knee fracture", "Critical", "Immobilize; emergency care", "8-16+ weeks"),
        ("Patellofemoral pain", "Medium", "Reduce running; rehab", "2-8+ weeks"),
        ("IT band syndrome", "Medium", "Reduce running; rehab", "2-6 weeks"),
        ("PCL injury", "High", "Stop activity; assessment", "4-12+ weeks"),
        ("Knee bursitis", "Medium", "Rest/ice; assessment", "1-6 weeks"),
        ("Quadriceps tendon injury", "High", "Stop activity; assessment", "6-16+ weeks"),
    ],
    "Ankle": [
        ("Lateral ankle sprain", "Medium-High", "Protect, rest, compression; assessment if severe", "1-6 weeks"),
        ("High ankle sprain", "High", "Stop play; medical assessment", "4-12 weeks"),
        ("Achilles strain", "High", "Stop running/jumping", "2-12 weeks"),
        ("Achilles rupture", "Critical", "Immobilize; urgent assessment", "6-12+ months"),
        ("Ankle fracture", "Critical", "No weight bearing; emergency/X-ray", "6-12+ weeks"),
        ("Ankle dislocation", "Critical", "Immobilize; emergency care", "8-16+ weeks"),
        ("Peroneal tendon injury", "High", "Stop running; assessment", "4-12 weeks"),
        ("Tibialis anterior strain", "Medium", "Rest; gradual rehab", "1-6 weeks"),
        ("Ankle impingement", "Medium", "Reduce painful activity", "2-8 weeks"),
        ("Achilles tendinopathy", "Medium", "Reduce load; progressive rehab", "4-12+ weeks"),
        ("Ankle contusion", "Medium", "Ice/protection", "1-2 weeks"),
        ("Syndesmotic injury", "High", "Protect ankle; assessment", "4-12 weeks"),
        ("Deltoid ligament sprain", "High", "Support/assessment", "2-8 weeks"),
        ("Osteochondral ankle injury", "High", "Stop impact; imaging/assessment", "6-12+ weeks"),
        ("Tendon subluxation", "High", "Stop activity; assessment", "4-12 weeks"),
    ],
    "Leg / Thigh": [
        ("Hamstring strain", "Medium-High", "Stop sprinting; gradual rehab", "1-8+ weeks"),
        ("Hamstring tear", "High", "Stop play; medical assessment", "4-12+ weeks"),
        ("Quadriceps strain", "Medium", "Stop sprinting/kicking", "1-6 weeks"),
        ("Quadriceps tear", "High", "Stop activity; assessment", "4-12+ weeks"),
        ("Calf strain", "Medium", "Stop running; gradual loading", "1-6 weeks"),
        ("Calf tear", "High", "Stop activity; assessment", "4-12 weeks"),
        ("Shin splints", "Medium", "Reduce impact/running", "2-8+ weeks"),
        ("Tibial stress fracture", "High", "Stop impact; medical assessment", "6-12+ weeks"),
        ("Femur fracture", "Critical", "Immobilize; emergency care", "3-6+ months"),
        ("Thigh contusion", "Medium", "Ice/compression/rest", "1-4 weeks"),
        ("Muscle cramp", "Low-Medium", "Stop play; gentle recovery/hydration", "Hours-days"),
        ("Adductor strain", "Medium-High", "Stop kicking/sprinting", "1-8+ weeks"),
        ("Adductor tear", "High", "Stop activity; medical assessment", "4-12+ weeks"),
        ("Muscle hematoma", "Medium-High", "Stop activity; assessment if severe", "2-8 weeks"),
        ("Compartment syndrome", "Critical", "Emergency medical treatment", "Individual"),
    ],
}

AREAS = list(CATALOG.keys())

# detector region word -> catalog areas worth looking at first (hint only)
REGION_HINTS = {
    "HEAD": ["Head"],
    "NECK": ["Head"],
    "ARM": ["Shoulder", "Elbow", "Wrist / Hand"],
    "TORSO": ["Shoulder", "Hip / Pelvis"],
    "LEG": ["Knee", "Ankle", "Leg / Thigh", "Hip / Pelvis"],
}

RISK_ORDER = ["Low", "Low-Medium", "Medium", "Medium-High", "High", "Critical"]


def _key(text):
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


_BY_NAME = {}
for _area, _rows in CATALOG.items():
    for _name, _risk, _safety, _rest in _rows:
        _BY_NAME.setdefault((_key(_area), _key(_name)), (_area, _name, _risk, _safety, _rest))
        _BY_NAME.setdefault(("", _key(_name)), (_area, _name, _risk, _safety, _rest))


def find(name, area=None):
    """Catalog row for an injury name (area optional). Returns dict or None."""
    hit = _BY_NAME.get((_key(area), _key(name))) or _BY_NAME.get(("", _key(name)))
    if hit is None:
        return None
    area, name, risk, safety, rest = hit
    return {"injury": name, "body_area": area, "risk": risk, "safety_measure": safety, "rest": rest}


def hint_areas(region):
    """Catalog areas that match the detector's region text (e.g. 'LEFT LEG')."""
    text = str(region or "").upper()
    out = []
    for word, areas in REGION_HINTS.items():
        if word in text:
            out += [a for a in areas if a not in out]
    return out


def as_prompt_text():
    """The whole catalog as compact text for the Gemini prompt."""
    lines = []
    for area, rows in CATALOG.items():
        lines.append(area + ":")
        for name, risk, _safety, _rest in rows:
            lines.append("  - " + name + " [" + risk + "]")
    return "\n".join(lines)


def highest_risk(risks):
    best = None
    for r in risks:
        if r in RISK_ORDER and (best is None or RISK_ORDER.index(r) > RISK_ORDER.index(best)):
            best = r
    return best