"""Summarise the first 20 IAG 1502000 claim reports for landslide mentions.

Reads ``claims-report-paths-iag-1502000.csv`` (built by
``find_iag_1502000_final_reports.py``), fetches each report's docx from T:
through ``tdrive_sync`` (caching it locally), and pulls out of the report
text:

- the claim type and site address, both read off the fixed line the T+T claim
  report template carries just below its "Claim for Natural Disaster (...)
  Damage" heading, e.g. "Ngaire Bennie, 44 Cecil Road, Wadestown";
- whether the report mentions landslide/landslip damage at all;
- whether it goes on to describe an evacuated and/or an inundated land
  extent, the two ways NHC settles landslide land damage.

Run:

    uv run --frozen python src/scripts/landloss/vul/static_data_gen/gen_iag_1502000_landslide_claims_summary.py

Reads only the first REPORT_COUNT rows of the source CSV -- this is a first
look at how common each flag is across the claims book, not a full run.
Results are saved to claims-landslide-summary-iag-1502000.csv.
"""

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import tdrive_sync as ts
from scripts.landloss import paths

REPORT_COUNT = 20

# The docx WordprocessingML namespace, unqualified paragraph/text/body tags are
# read against below.
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# The template heading every claim report opens with, right before the line
# carrying the customer's name and the site address.
CLAIM_TYPE_PATTERN = re.compile(r"^claim for natural disaster", re.IGNORECASE)


def read_paragraphs(path: Path) -> list[str]:
    """Return a docx's paragraph text, in document order, empty ones dropped."""
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    # Our own claim reports, not untrusted input -- stdlib ElementTree is fine.
    body = ET.fromstring(document_xml).find(f"{W_NS}body")  # noqa: S314
    paragraphs = [
        "".join(run.text or "" for run in paragraph.iter(f"{W_NS}t"))
        for paragraph in body.iter(f"{W_NS}p")
    ]
    return [text for text in paragraphs if text.strip()]


def summarise_report(paragraphs: list[str]) -> dict[str, str | bool]:
    """Pull the claim type, address and landslide/extent flags out of a report."""
    full_text = "\n".join(paragraphs).lower()

    claim_type = ""
    address = ""
    for index, paragraph in enumerate(paragraphs):
        if CLAIM_TYPE_PATTERN.match(paragraph.strip()):
            claim_type = paragraph.strip()
            if index + 1 < len(paragraphs):
                address = paragraphs[index + 1].strip()
            break

    return {
        "claim_type": claim_type,
        "address": address,
        "has_landslide": "landslide" in full_text or "landslip" in full_text,
        "mentions_evacuated_extent": "evacuat" in full_text,
        "mentions_inundated_extent": "inundat" in full_text,
    }


def main() -> int:
    with paths.IAG_1502000_REPORT_PATHS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[:REPORT_COUNT]

    summaries = []
    for row in rows:
        print(f"{row['subproject']}: caching and reading report")
        local_path = ts.get_cached(Path(row["report_path"]))
        summary = summarise_report(read_paragraphs(local_path))
        summaries.append(
            {
                "project_number": row["project_number"],
                "subproject_number": row["subproject_number"],
                **summary,
                "report_path": row["report_path"],
            }
        )

    paths.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with paths.IAG_1502000_LANDSLIDE_SUMMARY_CSV.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)

    landslide_count = sum(1 for summary in summaries if summary["has_landslide"])
    evacuated_count = sum(
        1 for summary in summaries if summary["mentions_evacuated_extent"]
    )
    inundated_count = sum(
        1 for summary in summaries if summary["mentions_inundated_extent"]
    )
    print(f"Wrote {len(summaries)} rows to {paths.IAG_1502000_LANDSLIDE_SUMMARY_CSV}")
    print(f"{landslide_count}/{len(summaries)} mention landslide/landslip")
    print(f"{evacuated_count}/{len(summaries)} mention an evacuated extent")
    print(f"{inundated_count}/{len(summaries)} mention an inundated extent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
