from fastapi import FastAPI

app = FastAPI(title="Sofia Municipality Scraper")

@app.get("/")
async def root():
    return {
        "service": "sofia_municipality",
        "status": "ok",
        "note": "Run scraper.py to fetch Sofia Municipality funding programmes.",
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
