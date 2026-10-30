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

export default function Home() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/opportunities")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ matches: [] }))
      .finally(() => setLoading(false));
  }, []);

  const matches = data?.matches ?? [];
  const filtered = matches.filter((m) => {
    const scoreOk = (m.match_score ?? 0) >= minScore;
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

      <div style={{ display: "flex", gap: "1rem", margin: "1.5rem 0", flexWrap: "wrap" }}>
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
        <p>No opportunities match the current filters. Run the scraper to generate data.</p>
      ) : (
        filtered
          .sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0))
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
                  {(opp.match_score ?? 0).toFixed(2)}
                </span>
              </div>
              <p style={{ color: "#cbd5e1", margin: "0.5rem 0", fontSize: "0.95rem" }}>
                {(opp.summary || "").slice(0, 280)}
                {(opp.summary || "").length > 280 ? "…" : ""}
              </p>
              <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                Deadline: <b>{opp.deadline || "—"}</b>
                {opp.matched_keywords?.length ? (
                  <> • Keywords: {opp.matched_keywords.join(", ")}</>
                ) : null}
                {opp.url ? (
                  <> • <a href={opp.url} target="_blank" rel="noreferrer">Open on portal →</a></>
                ) : null}
              </div>
            </div>
          ))
      )}

      <p style={{ marginTop: "2rem", fontSize: "0.8rem", color: "#64748b" }}>
        Profile: {data?.profile || "N/A"} • Last scraped: {data?.scraped_at?.slice(0, 19) || "N/A"}
      </p>
    </main>
  );
}
