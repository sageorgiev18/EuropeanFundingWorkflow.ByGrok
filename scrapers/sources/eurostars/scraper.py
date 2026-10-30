"""Discover Eurostars / Eureka funding links from an official public listing."""
import argparse
from scrapers.common.funding_sources import html_links, save
SOURCE = "eurostars"
SEEDS = ["https://www.eurekanetwork.org/programmes/eurostars/"]

def collect(*, session=None, limit=100, delay=1.5):
    return html_links(SOURCE, SEEDS, session=session, limit=limit, delay=delay)

def main():
    parser = argparse.ArgumentParser(description="Eurostars / Eureka discovery")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    rows = collect(limit=args.limit, delay=args.delay)
    output = save(SOURCE, rows, output_dir=args.output_dir)
    print(f"{len(rows)} candidates written to {output}")

if __name__ == "__main__":
    main()
