import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  try {
    // Read the scraper output from the sibling data folder
    const dataPath = path.join(process.cwd(), "..", "data", "eu_funding_tenders_matches.json");
    if (!fs.existsSync(dataPath)) {
      return NextResponse.json({ matches: [], count: 0 });
    }
    const raw = fs.readFileSync(dataPath, "utf-8");
    const payload = JSON.parse(raw);
    return NextResponse.json(payload);
  } catch (err) {
    console.error(err);
    return NextResponse.json({ matches: [], error: "Failed to load data" }, { status: 500 });
  }
}
