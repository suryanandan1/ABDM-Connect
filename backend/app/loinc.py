"""Search over a small, local LOINC subset (see data/loinc_subset.csv and the README licence note)."""
import csv
from pathlib import Path

LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"
# UCUM unit codes accepted for numeric results.
ALLOWED_UNITS = {
    "10*3/uL", "10*6/uL", "10*9/L", "10*12/L", "g/dL", "g/L", "%", "fL", "pg",
    "mm/h", "mg/dL", "mmol/L", "umol/L", "U/L", "m[IU]/L",
}

with open(Path(__file__).parent / "data" / "loinc_subset.csv", newline="", encoding="utf-8") as f:
    CONCEPTS = [
        {**row, "abbreviations": [a.strip() for a in row["abbreviations"].split(";") if a.strip()]}
        for row in csv.DictReader(f)
    ]
BY_CODE = {c["code"]: c for c in CONCEPTS}


def get_concept(code: str):
    return BY_CODE.get(code)


def search(q: str, kind: str | None = None, limit: int = 20):
    """Rank: exact code or abbreviation first, then prefix matches, then 'contains' matches."""
    q = q.strip().lower()
    if not q:
        return []
    results = []
    for c in CONCEPTS:
        if kind and c["kind"] != kind:
            continue
        names = [c["display"].lower()] + [a.lower() for a in c["abbreviations"]]
        if q == c["code"] or q in [a.lower() for a in c["abbreviations"]]:
            rank = 0
        elif c["code"].startswith(q) or any(n.startswith(q) for n in names):
            rank = 1
        elif any(q in n for n in names):
            rank = 2
        else:
            continue
        results.append((rank, c["display"], c))
    results.sort(key=lambda r: (r[0], r[1]))
    return [r[2] for r in results[:limit]]
