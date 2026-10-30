"use client";

import { useEffect, useState } from "react";

type Opportunity = {
  id: string;
  title: string;
  summary?: string;
  url?: string;
  deadline?: string;
  match_score?: number;
  matched_keywords?: string[];
  call_identifier?: string;
};

type Payload = {
  profile?: string;
  scraped_at?: string;
  count?: number;
  matches?: Opportunity[];
};

type CompanyProfile = {
  description: string;
  keywords: string;
};

function scoreOpportunity(opp: Opportunity, keywords: string[]): number {
  if (!keywords.length) return 0;
  const text = ((opp.title || "") + " " + (opp.summary || "")).toLowerCase();
  const hits = keywords.filter((kw) => text.includes(kw.toLowerCase().trim())).length;
  return Math.min(1, hits / keywords.length);
}

export default function Home() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [search, setSearch] = useState("");
  const [profile, setProfile] = useState<CompanyProfile>({
    description: "",
    keywords: "software, AI, digital, cloud, cybersecurity",
  });
  const [editing, setEditing] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("companyProfile");
    if (saved) {
      try {
        setProfile(JSON.parse(saved));
        setEditing(false);
      } catch {}
    }
  }, []);

  useEffect(() => {
    fetch("/api/opportunities")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ matches: [] }))
      .finally(() => setLoading(false));
  }, []);

  const saveProfile = () => {
    localStorage.setItem("companyProfile", JSON.stringify(profile));
    setEditing(false);
  };

  const keywords = profile.keywords
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);

  const matches = data?.matches ?? [];
  const scored = matches.map((m) => ({
    ...m,
    computed_score: scoreOpportunity(m, keywords),
    matched_keywords: keywords.filter((kw) =>
      ((m.title || "") + " " + (m.summary || "")).toLowerCase().includes(kw.toLowerCase())
    ),
  }));

  const filtered = scored.filter((m) => {
    const scoreOk = m.computed_score >= minScore;
    const text = (m.title + " " + (m.summary || "")).toLowerCase();
    const searchOk = !search || text.includes(search.toLowerCase());
    return scoreOk && searchOk;
  });

  if (loading) {
    return (
      <main style={{ padding: "2rem", textAlign: "center" }}>
        <p>Loading opportunities…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem 1rem" }}>
      <h1
        style={{
          background: "linear-gradient(90deg, #38bdf8, #818cf8, #c084fc)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          fontSize: "2.4rem",
          marginBottom: "0.25rem",
        }}
      >
        € EU Funding Opportunities
      </h1>
      <p style={{ color: "#94a3b8", marginTop: 0 }}>
        Matching calls for tenders • European Commission Funding & Tenders Portal
      </p>

      {/* Company profile form */}
      <div
        style={{
          background: "rgba(30, 41, 59, 0.7)",
          border: "1px solid rgba(56, 189, 248, 0.3)",
          borderRadius: 12,
          padding: "1.2rem",
          margin: "1.5rem 0",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Company profile</h3>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              style={{
                background: "#334155",
                color: "#e2e8f0",
                border: "none",
                borderRadius: 6,
                padding: "0.3rem 0.8rem",
                cursor: "pointer",
              }}
            >
              Edit
            </button>
          )}
        </div>

        {editing ? (
          <>
            <label style={{ display: "block", marginTop: "0.8rem", fontSize: "0.9rem" }}>
              Company description
              <textarea
                value={profile.description}
                onChange={(e) => setProfile({ ...profile, description: e.target.value })}
                rows={3}
                placeholder="What does your company do? e.g. We build AI-powered software for public sector digital transformation."
                style={{
                  width: "100%",
                  marginTop: 4,
                  padding: "0.5rem",
                  borderRadius: 8,
                  border: "1px solid #334155",
                  background: "#1e293b",
                  color: "#e2e8f0",
                }}
              />
            </label>
            <label style={{ display: "block", marginTop: "0.8rem", fontSize: "0.9rem" }}>
              Keywords (comma-separated)
              <input
                value={profile.keywords}
                onChange={(e) => setProfile({ ...profile, keywords: e.target.value })}
                placeholder="software, AI, cloud, cybersecurity, data analytics"
                style={{
                  width: "100%",
                  marginTop: 4,
                  padding: "0.5rem",
                  borderRadius: 8,
                  border: "1px solid #334155",
                  background: "#1e293b",
                  color: "#e2e8f0",
                }}
              />
            </label>
            <button
              onClick={saveProfile}
              style={{
                marginTop: "0.8rem",
                background: "linear-gradient(90deg, #22c55e, #38bdf8)",
                color: "white",
                border: "none",
                borderRadius: 8,
                padding: "0.5rem 1.2rem",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Save & match
            </button>
          </>
        ) : (
          <div style={{ marginTop: "0.6rem", color: "#cbd5e1", fontSize: "0.95rem" }}>
            <p style={{ margin: "0.3rem 0" }}>{profile.description || "No description set."}</p>
            <p style={{ margin: "0.3rem 0", color: "#94a3b8" }}>
              Keywords: {keywords.join(", ") || "none"}
            </p>
          </div>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: "1rem", margin: "1rem 0", flexWrap: "wrap" }}>
        <label>
          Min score: {minScore.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minScore}
            onChange={(e) => setMinScore(parseFloat(e.target.value))}
            style={{ marginLeft: 8 }}
          />
        </label>
        <input
          placeholder="Search title or summary…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "0.5rem 0.75rem",
            borderRadius: 8,
            border: "1px solid #334155",
            background: "#1e293b",
            color: "#e2e8f0",
            minWidth: 240,
          }}
        />
        <span style={{ alignSelf: "center", color: "#94a3b8" }}>
          Showing {filtered.length} of {matches.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <p>No opportunities match the current profile and filters.</p>
      ) : (
        filtered
          .sort((a, b) => b.computed_score - a.computed_score)
          .map((opp) => (
            <div
              key={opp.id}
              style={{
                background: "rgba(30, 41, 59, 0.7)",
                border: "1px solid rgba(56, 189, 248, 0.3)",
                borderRadius: 12,
                padding: "1rem 1.2rem",
                marginBottom: "0.8rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{opp.title}</strong>
                <span
                  style={{
                    background: "linear-gradient(90deg, #22c55e, #38bdf8)",
                    color: "white",
                    padding: "0.2rem 0.6rem",
                    borderRadius: 999,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                  }}
                >
                  {opp.computed_score.toFixed(2)}
                </span>
              </div>
              <p style={{ color: "#cbd5e1", margin: "0.5rem 0", fontSize: "0.95rem" }}>
                {(opp.summary || "").slice(0, 280)}
                {(opp.summary || "").length > 280 ? "…" : ""}
              </p>
              <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                Deadline: <b>{opp.deadline || "—"}</b>
                {opp.matched_keywords?.length ? (
                  <> • Matched: {opp.matched_keywords.join(", ")}</>
                ) : null}
                {opp.url ? (
                  <> • <a href={opp.url} target="_blank" rel="noreferrer">Open on portal →</a></>
                ) : null}
              </div>
            </div>
          ))
      )}

      <p style={{ marginTop: "2rem", fontSize: "0.8rem", color: "#64748b" }}>
        Last scraped: {data?.scraped_at?.slice(0, 19) || "N/A"}
      </p>
    </main>
  );
}
