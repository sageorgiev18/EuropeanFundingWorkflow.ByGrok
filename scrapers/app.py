from fastapi import FastAPI

app = FastAPI(title="Scrapers")

@app.get("/")
async def root():
    return {
        "service": "scrapers",
        "status": "ok",
        "note": "Batch scrapers live in sources/*/scraper.py. Use run_all.py to execute them.",
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
