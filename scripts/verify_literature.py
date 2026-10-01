"""Done check for P1.2 / P1.4: is docs/literature_review.md complete and correct?

1. Every paper in the matrix has a detail entry, and every detail entry has the P1.1
   fields (citation, study area, data, method, validation, key findings, relevance).
2. Abhinav's section (A*) has >= 5 papers and nothing left "to fill".
3. Every DOI in the review resolves on Crossref, and the Crossref title matches the
   title written in the citation (catches wrong DOIs / mixed-up papers). Needs network;
   skip with --no-network.

Run: python scripts/verify_literature.py [--no-network]
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests

DOC = Path(__file__).resolve().parents[1] / "docs" / "literature_review.md"
FIELDS = {
    "citation": r"\*\*Citation:\*\*",
    "method": r"\*\*Method:\*\*",
    "relevance": r"\*\*Relevance( to us)?:\*\*",
}
# A* entries (P1.2, Abhinav) must have every P1.1 field; H*/D* are checked for the
# core fields only (methods / data papers often have no study area).
FIELDS_A = {
    "study area": r"\*\*Study area:\*\*",
    "data": r"\*\*Data( and features)?:\*\*",
    "validation": r"\*\*Validation:\*\*",
    "key findings": r"\*\*Key findings:\*\*",
}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def entries(text: str) -> dict[str, str]:
    """Paper id (A1, H3, D2, ...) -> its detail section text."""
    parts = re.split(r"^### ([AHD]\d+)\. ", text, flags=re.M)
    return {parts[i]: parts[i + 1].split("\n## ")[0] for i in range(1, len(parts) - 1, 2)}


def norm(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)  # Crossref titles can carry markup, e.g. <scp>block</scp>CV
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"[^a-z0-9 ]", "", t.lower())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args(argv)
    text = DOC.read_text(encoding="utf-8")
    det = entries(text)
    matrix = re.findall(r"^\| ([AHD]\d+) \|", text, flags=re.M)

    print("1. matrix rows <-> detail entries, P1.1 fields")
    check(sorted(matrix) == sorted(det), f"matrix rows {len(matrix)} = detail entries {len(det)}")
    for pid, body in det.items():
        need = dict(FIELDS)
        if pid.startswith("A"):
            need.update(FIELDS_A)
        missing = [f for f, pat in need.items() if not re.search(pat, body)]
        check(
            not missing,
            f"{pid}: fields present{' (missing ' + ', '.join(missing) + ')' if missing else ''}",
        )

    print("2. Abhinav's section (P1.2)")
    a_ids = [p for p in det if p.startswith("A")]
    check(len(a_ids) >= 5, f"{len(a_ids)} A-papers (need >= 5)")
    check("To fill" not in text, "nothing left 'to fill'")
    check("(suggested)" not in text, "no rows still marked (suggested)")
    total = len(matrix)
    check(total >= 10, f"{total} papers in total (Phase 1 gate needs >= 10)")

    if not args.no_network:
        print("3. DOIs resolve on Crossref with matching titles")
        for pid, body in det.items():
            cit = re.search(r"\*\*Citation:\*\*(.+)", body)
            if not cit:
                continue
            m = re.search(r"https://doi\.org/(\S+?)(?:\s|$)", cit.group(1))
            if not m:
                print(f"  [--] {pid}: no DOI in the citation (not checked)")
                continue
            doi = m.group(1).rstrip(".")
            title_written = re.search(r"\*(.+?)\*", cit.group(1))
            try:
                r = requests.get(
                    f"https://api.crossref.org/works/{doi}",
                    headers={"User-Agent": "gis-urban-suitability/0.1 (term project)"},
                    timeout=30,
                )
                cr_title = r.json()["message"]["title"][0] if r.ok else None
            except (requests.RequestException, ValueError, KeyError, IndexError):
                cr_title = None
            if cr_title is None:
                check(False, f"{pid}: DOI {doi} did not resolve on Crossref")
                continue
            sim = SequenceMatcher(
                None, norm(cr_title), norm(title_written.group(1) if title_written else "")
            ).ratio()
            check(sim > 0.85, f"{pid}: DOI {doi} -> '{cr_title[:70]}' (title match {sim:.2f})")
            time.sleep(0.3)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
