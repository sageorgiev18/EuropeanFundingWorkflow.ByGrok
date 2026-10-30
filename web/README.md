# Web Application (Next.js + React)

React UI that consumes the scraper JSON and visualizes matching EU funding opportunities.

## Stack

- **Next.js 14** (App Router) + **React** + TypeScript
- API route (`/api/opportunities`) reads `data/eu_funding_tenders_matches.json`
- Follows the contract in `docs/scraper-to-web-contract.md`

## Local development

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000

## Deployment

- Vercel (recommended, free for public repos)
- Or any Node host / Docker

## Project structure

```
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx          ← main React page
│   ├── globals.css
│   └── api/opportunities/route.ts
├── package.json
├── next.config.js
└── tsconfig.json
```

The old Streamlit files (`app.py`, `requirements.txt`, `Dockerfile`) can be removed if you no longer need them.
