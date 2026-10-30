import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"  # every scraper writes data/<source>_matches.json

st.set_page_config(
    page_title="EU Funding Workflow",
    page_icon="€",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a modern, flashy look
st.markdown(
    """
    <style>
    /* Dark theme base */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        color: #e2e8f0;
    }
    /* Header */
    h1 {
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    /* Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .metric-card h3 {
        margin: 0;
        font-size: 2rem;
        color: #38bdf8;
    }
    .metric-card p {
        margin: 0.3rem 0 0 0;
        color: #94a3b8;
        font-size: 0.9rem;
    }
    /* Opportunity cards */
    .opp-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .opp-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(56, 189, 248, 0.2);
    }
    .score-badge {
        background: linear-gradient(90deg, #22c55e, #38bdf8);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.95);
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("# € EU Funding Opportunities")
st.caption("Matching calls for tenders • European Commission Funding & Tenders Portal")


@st.cache_data
def load_matches():
    matches, scraped, profile = [], [], None
    for path in sorted(DATA_DIR.glob("*_matches.json")):
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, ValueError):
            continue
        matches.extend(payload.get("matches", []))
        profile = profile or payload.get("profile")
        if payload.get("scraped_at"):
            scraped.append(payload["scraped_at"])
    if not matches:
        return pd.DataFrame(), {}
    df = pd.DataFrame(matches)
    if "match_score" not in df.columns:
        df["match_score"] = 0.0
    df["match_score"] = df["match_score"].fillna(0.0)
    meta = {
        "profile": profile,
        "scraped_at": max(scraped) if scraped else "N/A",
        "count": len(matches),
    }
    return df, meta


df, meta = load_matches()

if df.empty:
    st.warning(
        "No data found yet. Run the scraper first:\n\n"
        "```bash\ncd scrapers\npython -m sources.eu_funding_tenders.scraper\n```"
    )
    st.stop()

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    min_score = st.slider("Minimum match score", 0.0, 1.0, 0.0, 0.05)
    search = st.text_input("Search title / summary", placeholder="AI, software, digital...")
    st.divider()
    st.metric("Showing", 0)  # placeholder, updated later
    st.caption(f"Profile: **{meta.get('profile', 'N/A')}**")
    scraped = meta.get("scraped_at", "N/A")
    st.caption(f"Last scraped: {scraped[:19] if scraped != 'N/A' else scraped}")

# Filter data
filtered = df[df["match_score"] >= min_score].copy()
if search:
    mask = (
        filtered["title"].fillna("").str.contains(search, case=False)
        | filtered["summary"].fillna("").str.contains(search, case=False)
    )
    filtered = filtered[mask]

# Update sidebar metric (hacky but works)
st.sidebar.metric("Showing", len(filtered))

# Top metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""<div class="metric-card"><h3>{meta.get("count", 0)}</h3><p>Total matches</p></div>""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""<div class="metric-card"><h3>{len(filtered)}</h3><p>After filters</p></div>""",
        unsafe_allow_html=True,
    )
with col3:
    with_deadline = int(filtered["deadline"].notna().sum()) if "deadline" in filtered.columns else 0
    st.markdown(
        f"""<div class="metric-card"><h3>{with_deadline}</h3><p>With deadline</p></div>""",
        unsafe_allow_html=True,
    )
with col4:
    avg_score = filtered["match_score"].mean() if not filtered.empty else 0
    st.markdown(
        f"""<div class="metric-card"><h3>{avg_score:.2f}</h3><p>Avg match score</p></div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Charts row
if not filtered.empty and "match_score" in filtered.columns:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Match Score Distribution")
        fig = px.histogram(
            filtered,
            x="match_score",
            nbins=15,
            color_discrete_sequence=["#38bdf8"],
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0",
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        if "deadline" in filtered.columns and filtered["deadline"].notna().any():
            st.subheader("Upcoming Deadlines")
            deadline_df = filtered.dropna(subset=["deadline"]).copy()
            deadline_df["deadline"] = pd.to_datetime(deadline_df["deadline"], errors="coerce")
            deadline_df = deadline_df.dropna(subset=["deadline"])
            if not deadline_df.empty:
                fig2 = px.timeline(
                    deadline_df.head(15),
                    x_start="deadline",
                    x_end="deadline",
                    y="title",
                    color="match_score",
                    color_continuous_scale="Viridis",
                )
                fig2.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0",
                    height=400,
                    margin=dict(l=0, r=0, t=20, b=0),
                )
                st.plotly_chart(fig2, use_container_width=True)

# Opportunity cards
st.subheader("Top Opportunities")
if filtered.empty:
    st.info("No opportunities match the current filters.")
else:
    sorted_df = filtered.sort_values("match_score", ascending=False)
    for _, row in sorted_df.head(12).iterrows():
        keywords = ", ".join(row.get("matched_keywords") or [])
        deadline = row.get("deadline") or "No deadline"
        url = row.get("url") or "#"
        title = row.get("title", "Untitled")
        summary = (row.get("summary") or "")[:280] + ("..." if len(row.get("summary") or "") > 280 else "")
        score = row.get("match_score", 0)

        st.markdown(
            f"""
            <div class="opp-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="font-size:1.05rem;">{title}</strong>
                    <span class="score-badge">{score:.2f}</span>
                </div>
                <p style="color:#cbd5e1; margin:0.5rem 0 0.3rem 0; font-size:0.9rem;">{summary}</p>
                <div style="font-size:0.8rem; color:#94a3b8;">
                    Deadline: <b>{deadline}</b> &nbsp;•&nbsp; Keywords: {keywords or "—"}
                    &nbsp;•&nbsp; <a href="{url}" target="_blank" style="color:#38bdf8;">Open on portal →</a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.caption("Data source: EU Funding & Tenders Portal via official SEDIA Search API")
