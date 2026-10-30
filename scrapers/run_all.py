"""
Run every scraper.py found under scrapers/sources/.

Usage (from repo root or scrapers/):
    python scrapers/run_all.py
or
    cd scrapers && python run_all.py
"""

import subprocess
import sys
from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "sources"


def find_scrapers() -> list[Path]:
    scrapers = sorted(SOURCES_DIR.glob("*/scraper.py"))
    return scrapers


def run_scraper(scraper_path: Path) -> int:
    print(f"\n{'=' * 60}")
    print(f"Running: {scraper_path.relative_to(Path(__file__).parent)}")
    print(f"{'=' * 60}")

    # Run from the scraper's own directory so relative imports / files work
    result = subprocess.run(
        [sys.executable, scraper_path.name],
        cwd=scraper_path.parent,
        check=False,
    )
    return result.returncode


def main() -> None:
    scrapers = find_scrapers()
    if not scrapers:
        print(f"No scraper.py files found under {SOURCES_DIR}")
        sys.exit(0)

    print(f"Found {len(scrapers)} scraper(s):")
    for s in scrapers:
        print(f"  - {s.relative_to(SOURCES_DIR.parent)}")

    failures = []
    for scraper in scrapers:
        code = run_scraper(scraper)
        if code != 0:
            failures.append((scraper, code))

    print(f"\n{'=' * 60}")
    print("Done.")
    if failures:
        print(f"{len(failures)} scraper(s) failed:")
        for path, code in failures:
            print(f"  - {path.name} (exit {code})")
        sys.exit(1)
    else:
        print("All scrapers completed successfully.")


if __name__ == "__main__":
    main()
