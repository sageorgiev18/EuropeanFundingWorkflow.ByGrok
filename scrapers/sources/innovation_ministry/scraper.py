"""Independent source collector; run from repository root or scrapers directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.funding_sources import main

if __name__ == "__main__":
    main('innovation_ministry', ['https://www.mig.government.bg/'])
