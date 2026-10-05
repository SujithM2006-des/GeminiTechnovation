import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import "../App.css";

const API_BASE = api.defaults.baseURL;

// ── Helpers ────────────────────────────────────────────────────────────────

/** Return initials for the navbar avatar */
function initials(name) {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

/** Derive stats from the events array */
function deriveStats(events) {
  const total = events.length;
  const high = events.filter((e) => e.risk === "HIGH").length;
  const unidentified = events.filter((e) => !e.identified).length;
  const open = events.filter((e) => !e.resolved).length;
  return { total, high, unidentified, open };
}

/** How the player was identified, e.g. "Face · 91%" */
const METHOD_LABELS = {
  jersey: "Jersey number",
  jersey_name: "Name on shirt",
  jersey_history: "Jersey (before fall)",
  jersey_handoff: "Jersey (tracked)",
  face: "Face",
  gemini: "Gemini (jersey)",
  manual: "Manual",
};

/** Gemini second-opinion badge */
function geminiBadge(ev) {
  const v = ev.gemini_verdict;
  if (!v) return null;
  const pct =
    ev.gemini_confidence !== null && ev.gemini_confidence !== undefined
      ? ` · ${Math.round(ev.gemini_confidence * 100)}%`
      : "";
  if (v === "real_fall") {
    return { text: `Gemini ✓ real fall${pct}`, color: "var(--success-text)", bg: "var(--success-bg)" };
  }
  if (v === "false_alarm") {
    return { text: `Gemini: false alarm?${pct}`, color: "var(--risk-high-text)", bg: "var(--risk-high-bg)" };
  }
  if (v === "unsure") {
    return { text: `Gemini: unsure${pct}`, color: "var(--text-secondary)", bg: "rgba(100,116,139,0.15)" };
  }
  return { text: "Gemini: not checked", color: "var(--text-muted)", bg: "rgba(100,116,139,0.10)" };
}

/** Gemini read a different number than the stored player (and we kept ours) */
function geminiDisagrees(ev) {
  if (ev.gemini_jersey === null || ev.gemini_jersey === undefined) return false;
  if (ev.identified_by === "gemini") return false;
  if (!ev.identified) return true;
  return ev.gemini_jersey !== ev.jersey_number;
}

function identificationText(ev) {
  if (!ev.identified) return null;
  if (!ev.identified_by) return null;
  let text = METHOD_LABELS[ev.identified_by] || ev.identified_by;
  if (ev.id_confidence !== null && ev.id_confidence !== undefined) {
    text += ` · ${Math.round(ev.id_confidence * 100)}%`;
  }
  return text;
}

/** Seconds into the video -> "0:12:05" */
function formatVideoTime(seconds) {
  if (seconds === null || seconds === undefined) return null;
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

const methodBadge = (method) => ({
  display: "inline-block",
  marginTop: 4,
  padding: "1px 8px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
  background:
    method === "face" ? "rgba(139, 92, 246, 0.15)"
    : method === "gemini" ? "rgba(16, 185, 129, 0.15)"
    : "rgba(59, 130, 246, 0.12)",
  color:
    method === "face" ? "#a78bfa"
    : method === "gemini" ? "#34d399"
    : "var(--brand-primary)",
  border:
    method === "face" ? "1px solid rgba(139, 92, 246, 0.35)"
    : method === "gemini" ? "1px solid rgba(16, 185, 129, 0.35)"
    : "1px solid rgba(59, 130, 246, 0.3)",
});

const smallLinkButton = {
  marginTop: 6,
  padding: "2px 10px",
  fontSize: 12,
  borderRadius: 6,
  cursor: "pointer",
  background: "transparent",
  color: "var(--brand-primary)",
  border: "1px solid rgba(59, 130, 246, 0.35)",
};

const unidentifiedBadge = {
  display: "inline-block",
  padding: "2px 10px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  background: "#fff7ed",
  color: "#c2410c",
  border: "1px solid #fed7aa",
};

// ── Recommended safety measures ────────────────────────────────────────────
// Same text as SAFETY_MEASURES in src/injury_notes.py (used in WhatsApp alerts).
// Chosen from the body area + risk. AI suggestion only: medical staff decide.

const SAFETY_DISCLAIMER = "AI suggestion based on body area and risk, medical staff must confirm";

const SAFETY_MEASURES = {
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
};

const COLLISION_MEASURES = ["Check both players", "Follow the safety measures for any player who stays down"];

/** HEAD / NECK / LEG / ARM / TORSO / UNKNOWN, same rules as injury_notes._area */
function bodyArea(region) {
  if (!region) return "UNKNOWN";
  const r = String(region).toUpperCase();
  if (r.includes("HEAD")) return "HEAD";
  if (r.includes("NECK")) return "NECK";
  if (r.includes("LEG")) return "LEG";
  if (r.includes("ARM")) return "ARM";
  if (r.includes("TORSO")) return "TORSO";
  return "UNKNOWN";
}

function safetyMeasures(ev) {
  if (String(ev.event_type || "").toUpperCase().startsWith("COLLISION")) return COLLISION_MEASURES;
  let risk = String(ev.risk || "LOW").toUpperCase();
  if (!SAFETY_MEASURES[risk]) risk = "LOW";
  return SAFETY_MEASURES[risk][bodyArea(ev.region)];
}

const SAFETY_COLORS = {
  HIGH: { bg: "var(--risk-high-bg)", border: "var(--risk-high-border)", text: "var(--risk-high-text)" },
  MEDIUM: { bg: "var(--risk-medium-bg)", border: "var(--risk-medium-border)", text: "var(--risk-medium-text)" },
  LOW: { bg: "var(--risk-low-bg)", border: "var(--risk-low-border)", text: "var(--risk-low-text)" },
};

/** Box listing the recommended steps for one event */
function SafetyMeasures({ ev }) {
  const steps = safetyMeasures(ev);
  if (!steps || steps.length === 0) return null;
  const c = SAFETY_COLORS[String(ev.risk || "").toUpperCase()] || SAFETY_COLORS.LOW;

  return (
    <div
      style={{
        fontSize: 13,
        padding: "8px 10px",
        borderRadius: "var(--radius-sm)",
        background: c.bg,
        border: "1px solid " + c.border,
        color: "var(--text-primary)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: c.text,
          marginBottom: 4,
        }}
      >
        Recommended safety measures
      </div>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {steps.map((step) => (
          <li key={step} style={{ marginBottom: 2 }}>
            {step}
          </li>
        ))}
      </ul>
      <div style={{ fontSize: 11, opacity: 0.65, marginTop: 4 }}>{SAFETY_DISCLAIMER}</div>
    </div>
  );
}

// ── Player history dropdown ────────────────────────────────────────────────
// Opens under a player's row: every fall for that player with the possible
// injury, body area, risk and the video clip.

function PlayerHistory({ playerId, playerName, events }) {
  const list = events
    .filter((e) => e.player_id === playerId)
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  const high = list.filter((e) => e.risk === "HIGH").length;

  if (list.length === 0) {
    return (
      <div className="player-history">
        <div className="player-history-empty">No injury events recorded for {playerName}.</div>
      </div>
    );
  }

  return (
    <div className="player-history">
      <div className="player-history-summary">
        <strong>{playerName}</strong>
        <span>
          {list.length} {list.length === 1 ? "event" : "events"}
          {high > 0 && <span className="player-history-high"> · {high} high risk</span>}
          {" · latest "}
          {new Date(list[0].timestamp).toLocaleString()}
        </span>
      </div>

      <div className="player-history-grid">
        {list.map((ev) => (
          <div key={ev.id} className="player-history-card">
            <div className="player-history-card-head">
              <span className="event-type-chip">{ev.event_type}</span>
              {ev.risk && <span className={`risk-badge ${ev.risk}`}>{ev.risk}</span>}
              <span className="player-history-area">{ev.region || "Body area not recorded"}</span>
            </div>

            <div className="player-history-injury">
              <div className="player-history-label">Possible injury</div>
              <div>{ev.injury_note || ev.note || "No injury note"}</div>
            </div>

            <SafetyMeasures ev={ev} />

            {ev.clip_url ? (
              <video
                className="player-history-video"
                src={API_BASE + ev.clip_url}
                controls
                preload="metadata"
              />
            ) : (
              <div className="player-history-noclip">
                {ev.source === "manual" ? "Logged by staff — no video" : "No clip saved for this event"}
              </div>
            )}

            <div className="player-history-meta">
              <span>{ev.match_name || "No match"}</span>
              {formatVideoTime(ev.video_time_sec) && <span>at {formatVideoTime(ev.video_time_sec)} in video</span>}
              <span>{new Date(ev.timestamp).toLocaleString()}</span>
              {identificationText(ev) && (
                <span title={ev.id_detail || ""}>Identified by: {identificationText(ev)}</span>
              )}
              {ev.gemini_verdict && geminiBadge(ev) && <span>{geminiBadge(ev).text}</span>}
              <span>{ev.resolved ? "✓ Resolved" : "Pending"}</span>
            </div>

            {ev.clip_url && (
              <a className="player-history-download" href={API_BASE + ev.clip_url} download>
                Download clip
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [players, setPlayers] = useState([]);
  const [matches, setMatches] = useState([]);
  const [selectedMatch, setSelectedMatch] = useState("");
  const [clipEvent, setClipEvent] = useState(null);

  // Player dropdowns: all events (every match) for player histories,
  // which player is open in Team Details, which event row is open in Injury Events
  const [allEvents, setAllEvents] = useState([]);
  const [openTeamPlayer, setOpenTeamPlayer] = useState(null);
  const [openEventRow, setOpenEventRow] = useState(null);
  const [teams, setTeams] = useState([]);
  const [activeTeam, setActiveTeam] = useState(0);

  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Assign / correct the player from the events table
  // (any role for Unidentified events, medical + admin for identified ones)
  const [assigningId, setAssigningId] = useState(null);
  const [assignChoice, setAssignChoice] = useState("");
  const [assignSaving, setAssignSaving] = useState(false);
  const [assignError, setAssignError] = useState("");

  // Identify the player while watching the clip (any role, for Unidentified events)
  const [reviewChoice, setReviewChoice] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const [reviewDone, setReviewDone] = useState("");

  const [playerId, setPlayerId] = useState("");
  const [eventType, setEventType] = useState("");
  const [note, setNote] = useState("");
  const [risk, setRisk] = useState("MEDIUM");

  const navigate = useNavigate();
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");
  // Medical + admin can change any event's player.
  // Everyone (coaches too) can pick the player for an Unidentified event.
  const canChangeAny = role === "medical" || role === "admin";

  function canAssignEvent(ev) {
    return canChangeAny || !ev.identified;
  }

  function loadEvents(matchId) {
    api
      .get("/events", { params: matchId ? { match_id: matchId } : {} })
      .then((res) => {
        setEvents(res.data);
        setError("");
      })
      .catch(() => setError("Failed to load events. Try logging in again."));
  }

  function loadAllEvents() {
    api
      .get("/events")
      .then((res) => setAllEvents(res.data))
      .catch(() => {});
  }

  function loadTeams() {
    api
      .get("/teams")
      .then((res) => setTeams(res.data))
      .catch(() => {});
  }

  function loadMatches() {
    api
      .get("/matches")
      .then((res) => setMatches(res.data))
      .catch(() => {});
  }

  // Players list, both teams (manual form + identifying players) — once
  useEffect(() => {
    api
      .get("/players")
      .then((res) => setPlayers(res.data))
      .catch(() => setError("Failed to load players."));
  }, []);

  // Events + matches + teams — poll every 3 s, restart when the match filter changes
  useEffect(() => {
    function refresh() {
      loadEvents(selectedMatch);
      loadAllEvents();
      loadMatches();
      loadTeams();
    }

    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [selectedMatch]);

  function handleLogout() {
    localStorage.clear();
    navigate("/");
  }

  function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");

    if (!playerId || !eventType || !note) {
      setFormError("Player, event type, and note are all required.");
      return;
    }

    setSubmitting(true);

    api
      .post("/events/manual", {
        player_id: Number(playerId),
        event_type: eventType,
        note: note,
        risk: risk,
        match_session_id: selectedMatch ? Number(selectedMatch) : null,
      })
      .then(() => {
        setFormSuccess("Event logged successfully.");
        setPlayerId("");
        setEventType("");
        setNote("");
        setRisk("MEDIUM");
        loadEvents(selectedMatch);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        setFormError(detail || "Failed to log event.");
      })
      .finally(() => setSubmitting(false));
  }

  function teamNameOf(player) {
    return player.team_name || teams.find((t) => t.id === player.team_id)?.name || "";
  }

  const playersForSelect = [...players].sort(
    (a, b) => a.team_id - b.team_id || a.jersey_number - b.jersey_number
  );

  // Players grouped by team for <optgroup> in the pickers
  const playersByTeam = playersForSelect.reduce((groups, p) => {
    const name = teamNameOf(p) || "Team " + p.team_id;
    const group = groups.find((g) => g.name === name);
    if (group) group.players.push(p);
    else groups.push({ name, players: [p] });
    return groups;
  }, []);

  function playerOptions() {
    return playersByTeam.map((g) => (
      <optgroup key={g.name} label={g.name}>
        {g.players.map((p) => (
          <option key={p.id} value={p.id}>
            #{p.jersey_number} {p.name}
          </option>
        ))}
      </optgroup>
    ));
  }

  function describePlayer(playerId) {
    const p = players.find((x) => String(x.id) === String(playerId));
    if (!p) return "the player";
    const team = teamNameOf(p);
    return `${p.name} (#${p.jersey_number}${team ? ", " + team : ""})`;
  }

  // ── Clip viewer: open, and identify the player while watching ──
  function openClip(ev) {
    setClipEvent(ev);
    setReviewChoice(ev.player_id ? String(ev.player_id) : "");
    setReviewError("");
    setReviewDone("");
  }

  function closeClip() {
    setClipEvent(null);
    setReviewChoice("");
    setReviewError("");
    setReviewDone("");
  }

  function saveReview() {
    if (!clipEvent) return;

    if (!reviewChoice) {
      setReviewError("Pick a player first.");
      return;
    }

    setReviewSaving(true);
    setReviewError("");
    setReviewDone("");

    api
      .patch(`/events/${clipEvent.id}/assign`, { player_id: Number(reviewChoice) })
      .then((res) => {
        const updated = res.data?.event;
        if (updated) setClipEvent(updated);
        setReviewDone(`Saved: ${describePlayer(reviewChoice)}`);
        loadEvents(selectedMatch);
        loadTeams();
      })
      .catch((err) => {
        setReviewError(err?.response?.data?.detail || "Could not save the player.");
        loadEvents(selectedMatch);   // someone else may have identified it already
      })
      .finally(() => setReviewSaving(false));
  }

  function startAssign(ev) {
    setAssigningId(ev.id);
    setAssignChoice(ev.player_id ? String(ev.player_id) : "");
    setAssignError("");
  }

  function cancelAssign() {
    setAssigningId(null);
    setAssignChoice("");
    setAssignError("");
  }

  function saveAssign(eventId) {
    if (!assignChoice) {
      setAssignError("Pick a player first.");
      return;
    }

    setAssignSaving(true);
    setAssignError("");

    api
      .patch(`/events/${eventId}/assign`, { player_id: Number(assignChoice) })
      .then(() => {
        cancelAssign();
        loadEvents(selectedMatch);
        loadTeams();
      })
      .catch((err) => {
        setAssignError(err?.response?.data?.detail || "Could not assign player.");
        loadEvents(selectedMatch);   // someone else may have identified it already
      })
      .finally(() => setAssignSaving(false));
  }

  function handleClearAllEvents() {
    if (
      !window.confirm(
        "Delete ALL injury events? Players and teams will be kept. This cannot be undone."
      )
    ) {
      return;
    }

    api
      .delete("/admin/players/clear")
      .then(() => {
        alert("All injury events deleted. Players were kept.");
        loadEvents(selectedMatch);
      })
      .catch((err) => {
        alert(err?.response?.data?.detail || "Failed to delete events.");
      });
  }

  const stats = deriveStats(events);

  const selectedMatchName =
    matches.find((m) => String(m.id) === String(selectedMatch))?.name || null;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="dashboard-page">
      {/* ── Navigation Bar ── */}
      <nav className="navbar">
        <div className="navbar-brand">
          <div className="navbar-logo-icon">🛡️</div>
          <span className="navbar-brand-name">
            Athlete<span>Guard</span>
          </span>
        </div>

        <div className="navbar-right">
          <div className="navbar-user">
            <div className="navbar-avatar">{initials(username)}</div>
            <div className="navbar-user-info">
              <span className="navbar-username">{username}</span>
              <span className="navbar-role">{role}</span>
            </div>
          </div>
          <button
            className="btn-secondary"
            onClick={handleLogout}
            id="logout-btn"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* ── Main Content ── */}
      <main className="dashboard-content">
        {/* Page Header */}
        <div className="page-header">
          <h1 className="page-title">Event Dashboard</h1>
          <p className="page-subtitle">
            Monitor and manage athlete injury events in real time
          </p>
        </div>

        {/* Global error */}
        {error && (
          <div className="alert alert-error" role="alert">
            ⚠️ {error}
          </div>
        )}

        {/* ── Stats Row ── */}
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Total Events</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--risk-high-text)" }}>
              {stats.high}
            </div>
            <div className="stat-label">High Risk</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "#c2410c" }}>
              {stats.unidentified}
            </div>
            <div className="stat-label">Unidentified</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--risk-medium-text)" }}>
              {stats.open}
            </div>
            <div className="stat-label">Open Events</div>
          </div>
        </div>

        {/* ── Team Details ── */}
        {teams.length > 0 && (() => {
          const team = teams[activeTeam] || teams[0];
          return (
            <div className="panel">
              <div className="panel-header">
                <div className="panel-title">
                  <div className="panel-title-icon">👥</div>
                  Team Details
                </div>

                {teams.length > 1 && (
                  <div style={{ display: "flex", gap: 8 }}>
                    {teams.map((t, i) => (
                      <button
                        key={t.id}
                        className={i === activeTeam ? "btn-primary" : "btn-secondary"}
                        style={{ padding: "4px 14px", fontSize: 13 }}
                        onClick={() => setActiveTeam(i)}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="panel-body">
                <div className="stats-row" style={{ marginBottom: 16 }}>
                  <div className="stat-card">
                    <div className="stat-value" style={{ fontSize: 20 }}>{team.name}</div>
                    <div className="stat-label">Team</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value" style={{ fontSize: 20 }}>
                      {team.coaches.length ? team.coaches.join(", ") : "—"}
                    </div>
                    <div className="stat-label">Coach</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{team.player_count}</div>
                    <div className="stat-label">Players</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{team.injury_events}</div>
                    <div className="stat-label">Injury Events</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value" style={{ color: "var(--risk-high-text)" }}>
                      {team.high_risk_events}
                    </div>
                    <div className="stat-label">High Risk</div>
                  </div>
                </div>

                <div className="events-table-wrap">
                  <table className="events-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Player</th>
                        <th>Injury Events</th>
                        <th>High Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {team.players.map((p) => (
                        <Fragment key={p.id}>
                          <tr className={openTeamPlayer === p.id ? "row-open" : ""}>
                            <td>{p.jersey_number}</td>
                            <td>
                              <button
                                className="player-toggle"
                                aria-expanded={openTeamPlayer === p.id}
                                onClick={() => setOpenTeamPlayer(openTeamPlayer === p.id ? null : p.id)}
                              >
                                <span className="player-toggle-caret">{openTeamPlayer === p.id ? "▾" : "▸"}</span>
                                {p.name}
                              </button>
                            </td>
                            <td>{p.injury_events}</td>
                            <td
                              style={{
                                color: p.high_risk_events > 0 ? "var(--risk-high-text)" : "var(--text-muted)",
                                fontWeight: p.high_risk_events > 0 ? 700 : 400,
                              }}
                            >
                              {p.high_risk_events}
                            </td>
                          </tr>
                          {openTeamPlayer === p.id && (
                            <tr className="history-row">
                              <td colSpan={4}>
                                <PlayerHistory playerId={p.id} playerName={p.name} events={allEvents} />
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Admin Controls (admin role only) ── */}
        {role === "admin" && (
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <div className="panel-title-icon">🗑️</div>
                Admin Controls
              </div>
            </div>
            <div className="panel-body">
              <p style={{ color: "var(--text-secondary)", marginBottom: 16 }}>
                This will permanently delete all injury events. Players and
                teams are kept. This cannot be undone.
              </p>
              <button
                className="btn-primary"
                style={{ background: "#dc2626" }}
                onClick={handleClearAllEvents}
                id="clear-events-btn"
              >
                Delete All Injury Events
              </button>
            </div>
          </div>
        )}

        {/* ── Manual Event Form (medical role only) ── */}
        {role === "medical" && (
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <div className="panel-title-icon">📋</div>
                Log Manual Event
              </div>
              {selectedMatchName && (
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Will be tagged to: {selectedMatchName}
                </span>
              )}
            </div>
            <div className="panel-body">
              <form onSubmit={handleSubmit}>
                <div className="form-grid">
                  {/* Player */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="player-select">
                      Player
                    </label>
                    <select
                      id="player-select"
                      className="form-select"
                      value={playerId}
                      onChange={(e) => setPlayerId(e.target.value)}
                    >
                      <option value="">Select a player…</option>
                      {players.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} (#{p.jersey_number})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Risk */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="risk-select">
                      Risk Level
                    </label>
                    <select
                      id="risk-select"
                      className="form-select"
                      value={risk}
                      onChange={(e) => setRisk(e.target.value)}
                    >
                      <option value="LOW">LOW</option>
                      <option value="MEDIUM">MEDIUM</option>
                      <option value="HIGH">HIGH</option>
                    </select>
                  </div>

                  {/* Event Type */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="event-type-input">
                      Event Type
                    </label>
                    <input
                      id="event-type-input"
                      type="text"
                      className="form-input"
                      value={eventType}
                      onChange={(e) => setEventType(e.target.value)}
                      placeholder="e.g. TWISTED_ANKLE"
                    />
                  </div>

                  {/* Note — full width */}
                  <div className="form-group form-grid-full">
                    <label className="form-label" htmlFor="note-textarea">
                      Note
                    </label>
                    <textarea
                      id="note-textarea"
                      className="form-textarea"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Describe the event…"
                      rows={3}
                    />
                  </div>
                </div>

                {/* Alerts */}
                {formError && (
                  <div className="alert alert-error" role="alert">
                    ⚠️ {formError}
                  </div>
                )}
                {formSuccess && (
                  <div className="alert alert-success" role="status">
                    ✓ {formSuccess}
                  </div>
                )}

                <div className="form-submit-row">
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={submitting}
                    id="log-event-btn"
                  >
                    {submitting ? "Logging…" : "Log Event"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── Events Table ── */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <div className="panel-title-icon">🗂️</div>
              Injury Events
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <select
                id="match-filter"
                className="form-select"
                style={{ minWidth: 220 }}
                value={selectedMatch}
                onChange={(e) => setSelectedMatch(e.target.value)}
              >
                <option value="">All matches</option>
                {matches.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>

              <span
                style={{
                  fontSize: 13,
                  color: "var(--text-muted)",
                  fontWeight: 500,
                }}
              >
                {events.length} {events.length === 1 ? "event" : "events"}
              </span>
            </div>
          </div>

          {events.length === 0 && !error ? (
            <div className="empty-state">
              <div className="empty-state-icon">📭</div>
              <div className="empty-state-text">No events recorded yet</div>
              <div className="empty-state-subtext">
                Events detected by the AI system or logged manually will appear
                here.
              </div>
            </div>
          ) : (
            <div className="events-table-wrap">
              <table className="events-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Type</th>
                    <th>Body Area</th>
                    <th>Injury Note</th>
                    <th>Risk</th>
                    <th>Match</th>
                    <th>Clip</th>
                    <th>Resolved</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <Fragment key={ev.id}>
                    <tr className={openEventRow === ev.id ? "row-open" : ""}>
                      <td style={{ minWidth: 170 }}>
                        {ev.identified ? (
                          <>
                            <button
                              className="player-toggle"
                              aria-expanded={openEventRow === ev.id}
                              title="Show this player's injury history"
                              onClick={() => setOpenEventRow(openEventRow === ev.id ? null : ev.id)}
                            >
                              <span className="player-toggle-caret">{openEventRow === ev.id ? "▾" : "▸"}</span>
                              {ev.player_name}
                            </button>
                            {ev.jersey_number !== null && ev.jersey_number !== undefined && (
                              <span style={{ color: "var(--text-muted)", marginLeft: 6 }}>
                                #{ev.jersey_number}
                              </span>
                            )}
                            {ev.team_name && (
                              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                                {ev.team_name}
                              </div>
                            )}
                            {identificationText(ev) && (
                              <div
                                style={methodBadge(ev.identified_by)}
                                title={ev.id_detail || ""}
                              >
                                {identificationText(ev)}
                              </div>
                            )}
                          </>
                        ) : (
                          <>
                            <span style={unidentifiedBadge}>Unidentified</span>
                            {ev.track_id !== null && ev.track_id !== undefined && (
                              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                                track {ev.track_id}
                              </div>
                            )}
                          </>
                        )}

                        {/* Assign / correct player (any role if Unidentified, medical + admin otherwise) */}
                        {canAssignEvent(ev) && assigningId === ev.id && (
                          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                            <select
                              className="form-select"
                              style={{ padding: "6px 30px 6px 10px", fontSize: 13 }}
                              value={assignChoice}
                              onChange={(e) => setAssignChoice(e.target.value)}
                            >
                              <option value="">Select player…</option>
                              {playerOptions()}
                            </select>
                            <div style={{ display: "flex", gap: 6 }}>
                              <button
                                className="btn-secondary"
                                style={{ padding: "3px 10px", fontSize: 12 }}
                                disabled={assignSaving}
                                onClick={() => saveAssign(ev.id)}
                              >
                                {assignSaving ? "Saving…" : "Save"}
                              </button>
                              <button
                                className="btn-secondary"
                                style={{ padding: "3px 10px", fontSize: 12 }}
                                onClick={cancelAssign}
                              >
                                Cancel
                              </button>
                            </div>
                            {assignError && (
                              <div style={{ fontSize: 12, color: "var(--error-text)" }}>{assignError}</div>
                            )}
                          </div>
                        )}

                        {canAssignEvent(ev) && assigningId !== ev.id && (
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {!ev.identified && ev.clip_url && (
                              <button style={smallLinkButton} onClick={() => openClip(ev)}>
                                ▶ Review clip & identify
                              </button>
                            )}
                            <button style={smallLinkButton} onClick={() => startAssign(ev)}>
                              {ev.identified ? "Change player" : "Assign player"}
                            </button>
                          </div>
                        )}
                      </td>
                      <td style={{ minWidth: 120 }}>
                        <span className="event-type-chip">{ev.event_type}</span>
                        {geminiBadge(ev) && (
                          <div
                            title={[ev.gemini_reason, ev.gemini_description].filter(Boolean).join(" — ")}
                            style={{
                              marginTop: 6,
                              padding: "1px 8px",
                              borderRadius: 999,
                              fontSize: 11,
                              fontWeight: 600,
                              display: "inline-block",
                              color: geminiBadge(ev).color,
                              background: geminiBadge(ev).bg,
                            }}
                          >
                            {geminiBadge(ev).text}
                          </div>
                        )}
                        {geminiDisagrees(ev) && (
                          <div style={{ fontSize: 11, color: "var(--risk-medium-text)", marginTop: 4 }}>
                            Gemini read #{ev.gemini_jersey}
                            {ev.gemini_team && ev.gemini_team !== "unknown" ? ` (${ev.gemini_team})` : ""}
                          </div>
                        )}
                      </td>
                      <td style={{ color: "var(--text-secondary)" }}>
                        {ev.region || "—"}
                      </td>
                      <td
                        style={{
                          color: "var(--text-secondary)",
                          maxWidth: 280,
                          fontSize: 13,
                        }}
                      >
                        {ev.injury_note || ev.note || "—"}
                        <details style={{ marginTop: 6 }}>
                          <summary
                            style={{ cursor: "pointer", fontSize: 12, color: "var(--brand-primary)", fontWeight: 500 }}
                          >
                            Safety measures
                          </summary>
                          <div style={{ marginTop: 6 }}>
                            <SafetyMeasures ev={ev} />
                          </div>
                        </details>
                      </td>
                      <td>
                        {ev.risk ? (
                          <span className={`risk-badge ${ev.risk}`}>
                            {ev.risk}
                          </span>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                        )}
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>
                        {ev.match_name || "—"}
                      </td>
                      <td>
                        {ev.clip_url ? (
                          <button
                            className="btn-secondary"
                            style={{ padding: "4px 10px", fontSize: 13 }}
                            onClick={() => openClip(ev)}
                          >
                            ▶ Play
                          </button>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                        )}
                      </td>
                      <td>
                        <span
                          className={`resolved-badge ${ev.resolved ? "yes" : "no"}`}
                        >
                          {ev.resolved ? "✓ Yes" : "Pending"}
                        </span>
                      </td>
                      <td className="timestamp">
                        {new Date(ev.timestamp).toLocaleString()}
                        {formatVideoTime(ev.video_time_sec) && (
                          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                            at {formatVideoTime(ev.video_time_sec)} in video
                          </div>
                        )}
                      </td>
                    </tr>
                    {openEventRow === ev.id && ev.identified && (
                      <tr className="history-row">
                        <td colSpan={9}>
                          <PlayerHistory playerId={ev.player_id} playerName={ev.player_name} events={allEvents} />
                        </td>
                      </tr>
                    )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* ── Clip Viewer ── */}
      {clipEvent && (
        <div
          onClick={closeClip}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 16,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#111827",
              color: "#f9fafb",
              borderRadius: 12,
              padding: 16,
              width: "100%",
              maxWidth: 900,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>
                  {clipEvent.event_type} — {clipEvent.identified ? clipEvent.player_name : "Unidentified"}
                  {clipEvent.jersey_number !== null &&
                    clipEvent.jersey_number !== undefined &&
                    ` #${clipEvent.jersey_number}`}
                </div>
                <div style={{ fontSize: 13, opacity: 0.75 }}>
                  {clipEvent.region || "—"} · {clipEvent.risk || "—"} ·{" "}
                  {new Date(clipEvent.timestamp).toLocaleString()}
                  {formatVideoTime(clipEvent.video_time_sec) &&
                    ` · ${formatVideoTime(clipEvent.video_time_sec)} in video`}
                </div>
                <div style={{ fontSize: 13, opacity: 0.75 }}>
                  {clipEvent.identified
                    ? `Identified by: ${identificationText(clipEvent) || "—"}${
                        clipEvent.id_detail ? ` (${clipEvent.id_detail})` : ""
                      }`
                    : "Not identified yet"}
                </div>
              </div>
              <button
                onClick={closeClip}
                style={{
                  background: "transparent",
                  color: "#f9fafb",
                  border: "1px solid #4b5563",
                  borderRadius: 8,
                  padding: "4px 12px",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </div>

            <video
              key={clipEvent.id}
              src={API_BASE + clipEvent.clip_url}
              controls
              autoPlay
              style={{ width: "100%", borderRadius: 8, background: "#000" }}
            />

            {/* Identify the player while watching (any role for Unidentified, medical/admin to change) */}
            {(canAssignEvent(clipEvent) || reviewDone) && (
              <div
                style={{
                  marginTop: 12,
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: clipEvent.identified ? "rgba(255,255,255,0.05)" : "rgba(194, 65, 12, 0.18)",
                  border: clipEvent.identified ? "1px solid #374151" : "1px solid rgba(251, 146, 60, 0.45)",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8 }}>
                  {clipEvent.identified
                    ? "Wrong player? Pick the right one"
                    : "Who fell? Watch the clip and pick the player"}
                </div>

                {canAssignEvent(clipEvent) && (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                    <select
                      className="form-select"
                      style={{ minWidth: 260, padding: "6px 30px 6px 10px", fontSize: 13 }}
                      value={reviewChoice}
                      onChange={(e) => {
                        setReviewChoice(e.target.value);
                        setReviewError("");
                        setReviewDone("");
                      }}
                    >
                      <option value="">Select player…</option>
                      {playerOptions()}
                    </select>
                    <button
                      className="btn-primary"
                      style={{ padding: "6px 16px", fontSize: 13, width: "auto" }}
                      disabled={reviewSaving}
                      onClick={saveReview}
                    >
                      {reviewSaving ? "Saving…" : "Save player"}
                    </button>
                  </div>
                )}

                {reviewError && (
                  <div style={{ fontSize: 12, color: "#fca5a5", marginTop: 6 }}>{reviewError}</div>
                )}
                {reviewDone && (
                  <div style={{ fontSize: 12, color: "#86efac", marginTop: 6 }}>✓ {reviewDone}</div>
                )}
                {!canChangeAny && !reviewDone && (
                  <div style={{ fontSize: 11, opacity: 0.6, marginTop: 6 }}>
                    Once saved, only medical staff or admin can change it.
                  </div>
                )}
              </div>
            )}

            {clipEvent.injury_note && (
              <p style={{ fontSize: 13, marginTop: 10, opacity: 0.85 }}>
                {clipEvent.injury_note}
              </p>
            )}

            <div style={{ marginTop: 8 }}>
              <SafetyMeasures ev={clipEvent} />
            </div>

            {clipEvent.gemini_verdict && (
              <div
                style={{
                  fontSize: 13,
                  marginTop: 8,
                  padding: "8px 10px",
                  borderRadius: 8,
                  background: "rgba(255,255,255,0.05)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 2 }}>
                  {geminiBadge(clipEvent)?.text}
                  {clipEvent.gemini_jersey !== null && clipEvent.gemini_jersey !== undefined &&
                    ` · read #${clipEvent.gemini_jersey}${
                      clipEvent.gemini_team && clipEvent.gemini_team !== "unknown" ? ` (${clipEvent.gemini_team})` : ""
                    }${
                      clipEvent.gemini_jersey_confidence
                        ? ` ${Math.round(clipEvent.gemini_jersey_confidence * 100)}%`
                        : ""
                    }`}
                </div>
                {clipEvent.gemini_description && (
                  <div style={{ opacity: 0.85 }}>{clipEvent.gemini_description}</div>
                )}
                {clipEvent.gemini_reason && (
                  <div style={{ opacity: 0.6, fontSize: 12 }}>Why: {clipEvent.gemini_reason}</div>
                )}
              </div>
            )}

            <p style={{ fontSize: 12, marginTop: 6, opacity: 0.6 }}>
              If the clip doesn't play,{" "}
              <a
                href={API_BASE + clipEvent.clip_url}
                download
                style={{ color: "#93c5fd" }}
              >
                download it
              </a>
              .
            </p>
          </div>
        </div>
      )}
    </div>
  );
}