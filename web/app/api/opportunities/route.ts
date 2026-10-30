import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  try {
    // Merge every scraper output data/*_matches.json (docs/scraper-to-web-contract.md, multi-source)
    const dataDir = path.join(process.cwd(), "..", "data");
    if (!fs.existsSync(dataDir)) {
      return NextResponse.json({ matches: [], count: 0 });
    }
    const files = fs.readdirSync(dataDir).filter((f) => f.endsWith("_matches.json")).sort();
    const matches: unknown[] = [];
    const sources: string[] = [];
    let scrapedAt: string | undefined;
    let profile: string | undefined;
    for (const f of files) {
      try {
        const payload = JSON.parse(fs.readFileSync(path.join(dataDir, f), "utf-8"));
        matches.push(...(payload.matches ?? []));
        sources.push(f.replace(/_matches\.json$/, ""));
        profile = profile ?? payload.profile;
        if (payload.scraped_at && (!scrapedAt || payload.scraped_at > scrapedAt)) scrapedAt = payload.scraped_at;
      } catch (e) {
        console.error(`Skipping unreadable ${f}`, e);
      }
    }
    return NextResponse.json({ profile, scraped_at: scrapedAt, count: matches.length, sources, matches });
  } catch (err) {
    console.error(err);
    return NextResponse.json({ matches: [], error: "Failed to load data" }, { status: 500 });
  }
}
