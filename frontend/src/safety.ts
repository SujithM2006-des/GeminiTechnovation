import type { RiskLevel } from './types'

// Recommended safety measures by risk + body area.
// Same text as SAFETY_MEASURES in src/injury_notes.py (used in the WhatsApp alerts).
// AI suggestion only: medical staff make the final decision.

export const SAFETY_DISCLAIMER = "AI suggestion based on body area and risk, medical staff must confirm"

type Area = 'HEAD' | 'NECK' | 'TORSO' | 'ARM' | 'LEG' | 'UNKNOWN'

const SAFETY_MEASURES: Record<RiskLevel, Record<Area, string[]>> = {
  HIGH: {
    HEAD: [
      "Remove the player from play immediately",
      "Do not move the player if unconscious or confused",
      "Call emergency medical services",
      "CT scan of the head",
    ],
    NECK: [
      "Do not move the player",
      "Keep the head and neck still (manual in-line support)",
      "Spinal board and emergency transfer",
      "CT or MRI of the cervical spine",
    ],
    TORSO: [
      "Check breathing and abdominal pain",
      "Emergency transfer if breathing is difficult",
      "Chest X-ray",
      "Abdominal ultrasound or CT for internal injury",
    ],
    ARM: [
      "Splint the arm in the position found",
      "Check pulse and colour below the injury",
      "X-ray",
      "Orthopaedic referral",
    ],
    LEG: [
      "Do not let the player stand",
      "Splint the leg and use a stretcher",
      "X-ray",
      "MRI for ligament (ACL) damage",
      "Orthopaedic referral",
    ],
    UNKNOWN: [
      "Remove the player from play",
      "Full medical assessment on the pitch",
      "Emergency transfer if any serious sign",
      "Imaging (X-ray / CT) as advised by the doctor",
    ],
  },
  MEDIUM: {
    HEAD: [
      "Remove the player from play",
      "Sideline concussion check (SCAT)",
      "No return the same day if any symptom",
      "Doctor review",
    ],
    NECK: [
      "Remove the player from play",
      "Check for numbness or tingling in the arms",
      "X-ray if pain persists",
    ],
    TORSO: [
      "Check rib pain and breathing",
      "Chest X-ray if breathing hurts",
    ],
    ARM: [
      "Support the arm in a sling",
      "X-ray if swelling or deformity",
    ],
    LEG: [
      "No weight-bearing",
      "Ice and compression",
      "X-ray",
      "Physio review",
    ],
    UNKNOWN: [
      "Remove the player from play",
      "Medical check before returning",
    ],
  },
  LOW: {
    HEAD: [
      "Check for concussion signs (confusion, headache, dizziness)",
      "Monitor for 24 hours",
    ],
    NECK: [
      "Check neck movement",
      "Stop play if any pain",
    ],
    TORSO: [
      "Ice",
      "Watch breathing",
    ],
    ARM: [
      "Rest, ice, compression, elevation (RICE)",
      "Check grip strength",
    ],
    LEG: [
      "Rest, ice, compression, elevation (RICE)",
      "Must bear weight before returning to play",
    ],
    UNKNOWN: [
      "Check the player before they continue",
      "Monitor for any pain",
    ],
  },
}

const COLLISION_MEASURES = [
  "Check both players",
  "Follow the safety measures for any player who stays down",
]

/** HEAD / NECK / LEG / ARM / TORSO / UNKNOWN, same rules as injury_notes._area */
export function bodyArea(region: string | null): Area {
  if (!region) return 'UNKNOWN'
  const r = region.toUpperCase()
  if (r.includes('HEAD')) return 'HEAD'
  if (r.includes('NECK')) return 'NECK'
  if (r.includes('LEG')) return 'LEG'
  if (r.includes('ARM')) return 'ARM'
  if (r.includes('TORSO')) return 'TORSO'
  return 'UNKNOWN'
}

export function safetyMeasures(eventType: string, region: string | null, risk: RiskLevel | null): string[] {
  if ((eventType || '').toUpperCase().startsWith('COLLISION')) return COLLISION_MEASURES
  return SAFETY_MEASURES[risk ?? 'LOW'][bodyArea(region)]
}