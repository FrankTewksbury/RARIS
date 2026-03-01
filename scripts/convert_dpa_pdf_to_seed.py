from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class RowAccumulator:
    program_name: str = ""
    provider_name: str = ""
    state: str = ""
    max_purchase_price: str = ""
    max_annual_income: str = ""
    credit_score: str = ""
    program_type: str = ""
    page: int = 0

    def append(self, key: str, value: str) -> None:
        value = value.strip()
        if not value:
            return
        current = getattr(self, key)
        setattr(self, key, f"{current} {value}".strip() if current else value)


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_state(raw_state: str) -> str:
    state = _collapse_ws(raw_state).replace(" ,", ",")
    state_fixes = {
        "Pennsylvani": "Pennsylvania",
        "Pennsylvani a": "Pennsylvania",
        "Massachuse tts": "Massachusetts",
        "West Virginia": "West Virginia",
        "North Carolina": "North Carolina",
        "South Carolina": "South Carolina",
        "New Hampshire": "New Hampshire",
        "New Jersey": "New Jersey",
        "New Mexico": "New Mexico",
        "New York": "New York",
        "District of Columbia": "District of Columbia",
    }
    if state in state_fixes:
        return state_fixes[state]
    # Common OCR split artifacts
    state = state.replace("Pennsylvani a", "Pennsylvania")
    state = state.replace("Massachuse tts", "Massachusetts")
    return _collapse_ws(state)


def _extract_amount_range(text: str) -> tuple[int | None, int | None]:
    values = [int(v.replace(",", "")) for v in re.findall(r"\$([0-9][0-9,]*)", text)]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return min(values), max(values)


def _extract_credit_score(text: str) -> int | None:
    scores = [int(v) for v in re.findall(r"\b([0-9]{3})\b", text)]
    if not scores:
        return None
    return min(scores)


def _line_to_columns(words: list[dict]) -> dict[str, str]:
    cols = {
        "program_name": [],
        "provider_name": [],
        "state": [],
        "max_purchase_price": [],
        "max_annual_income": [],
        "credit_score": [],
        "program_type": [],
    }
    for w in words:
        x0 = float(w["x0"])
        text = str(w["text"]).strip()
        if not text:
            continue
        if x0 < 210:
            cols["program_name"].append(text)
        elif x0 < 390:
            cols["provider_name"].append(text)
        elif x0 < 462:
            cols["state"].append(text)
        elif x0 < 576:
            cols["max_purchase_price"].append(text)
        elif x0 < 689:
            cols["max_annual_income"].append(text)
        elif x0 < 749:
            cols["credit_score"].append(text)
        else:
            cols["program_type"].append(text)
    return {k: _collapse_ws(" ".join(v)) for k, v in cols.items()}


def _is_noise_line(text: str) -> bool:
    t = text.lower()
    if not t:
        return True
    if "program name" in t and "provider name" in t:
        return True
    if "max purchase price" in t and "max annual income" in t:
        return True
    if "credit score" in t:
        return True
    header_markers = ["search results:"]
    footer_markers = ["freddie mac", "--", "page ", "of37"]
    if any(marker in t for marker in header_markers):
        return True
    if any(marker in t for marker in footer_markers):
        return True
    return False


def _row_complete(acc: RowAccumulator) -> bool:
    return "loan" in acc.program_type.lower() or "grant" in acc.program_type.lower()


def _to_program_seed(acc: RowAccumulator, row_index: int, source_name: str) -> dict:
    program_name = _collapse_ws(acc.program_name) or "Seed Program"
    administering_entity = _collapse_ws(acc.provider_name) or "Unknown Provider"
    state = _normalize_state(acc.state)
    price_min, price_max = _extract_amount_range(acc.max_purchase_price)
    income_min, income_max = _extract_amount_range(acc.max_annual_income)
    credit_min = _extract_credit_score(acc.credit_score)
    assistance_type = "Loan"
    if "grant" in acc.program_type.lower():
        assistance_type = "Grant"

    benefits_parts: list[str] = [f"{assistance_type} assistance"]
    if price_min is not None:
        if price_min == price_max:
            benefits_parts.append(f"max purchase price ${price_min:,}")
        else:
            benefits_parts.append(f"max purchase price ${price_min:,}-${price_max:,}")
    if income_min is not None:
        if income_min == income_max:
            benefits_parts.append(f"max annual income ${income_min:,}")
        else:
            benefits_parts.append(f"max annual income ${income_min:,}-${income_max:,}")
    benefits = "; ".join(benefits_parts)

    eligibility_parts: list[str] = []
    if credit_min is not None:
        eligibility_parts.append(f"minimum credit score {credit_min}")
    if income_min is not None:
        if income_min == income_max:
            eligibility_parts.append(f"income cap ${income_min:,}")
        else:
            eligibility_parts.append(f"income range ${income_min:,}-${income_max:,}")
    eligibility = "; ".join(eligibility_parts) if eligibility_parts else None

    confidence = 0.78
    if not state:
        confidence -= 0.14
    if administering_entity == "Unknown Provider":
        confidence -= 0.12
    if program_name == "Seed Program":
        confidence -= 0.12
    if "scraped with ai" in acc.program_name.lower():
        confidence -= 0.20
    confidence = round(max(0.35, min(0.95, confidence)), 2)

    return {
        "program_name": program_name,
        "administering_entity": administering_entity,
        "geo_scope": "state",
        "jurisdiction": state,
        "benefits": benefits,
        "eligibility": eligibility,
        "status": "verification_pending",
        "source_urls": [],
        "confidence": confidence,
        "needs_human_review": confidence < 0.75 or program_name == "Seed Program" or administering_entity == "Unknown Provider",
        "seed_row_type": assistance_type.lower(),
        "provenance_links": {
            "seed_file": source_name,
            "seed_row": row_index,
            "source_page": acc.page,
        },
        "raw_fields": {
            "max_purchase_price": _collapse_ws(acc.max_purchase_price),
            "max_annual_income": _collapse_ws(acc.max_annual_income),
            "credit_score": _collapse_ws(acc.credit_score),
            "type": _collapse_ws(acc.program_type),
        },
    }


def convert(pdf_path: Path) -> tuple[list[dict], list[dict]]:
    rows: list[RowAccumulator] = []
    current = RowAccumulator()
    just_finalized = False

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words() or []
            line_groups: dict[float, list[dict]] = {}
            for w in words:
                y_key = round(float(w["top"]), 1)
                line_groups.setdefault(y_key, []).append(w)

            for y in sorted(line_groups.keys()):
                line_words = sorted(line_groups[y], key=lambda item: float(item["x0"]))
                line_text = _collapse_ws(" ".join(str(item["text"]) for item in line_words))
                if _is_noise_line(line_text):
                    continue

                cols = _line_to_columns(line_words)
                if all(not value for value in cols.values()):
                    continue

                has_state = bool(cols["state"] and not re.fullmatch(r"[A-Za-z]", cols["state"]))
                has_amount = bool(
                    "$" in cols["max_purchase_price"] or "$" in cols["max_annual_income"]
                )
                has_type = bool(re.search(r"\b(loan|grant)\b", cols["program_type"], flags=re.I))
                has_core_name = bool(cols["program_name"] or cols["provider_name"])

                if not any([has_state, has_amount, has_type, has_core_name]):
                    continue

                if not current.program_name and just_finalized and not (has_state or has_amount or has_type):
                    # Wrapped orphan text after a completed row.
                    continue

                if not current.program_name and cols["state"] and re.fullmatch(r"[A-Za-z]", cols["state"]):
                    # Isolated single-letter state wrap (e.g., trailing "a")
                    continue

                current.page = page_index
                for key, value in cols.items():
                    current.append(key, value)
                just_finalized = False

                if _row_complete(current):
                    rows.append(current)
                    current = RowAccumulator()
                    just_finalized = True

    programs: list[dict] = []
    quarantined: list[dict] = []
    source_name = pdf_path.name

    for idx, row in enumerate(rows, start=1):
        if "scraped with ai" in row.program_name.lower():
            quarantined.append(
                {
                    "seed_row": idx,
                    "source_page": row.page,
                    "reason": "contains noisy marker",
                    "raw": row.__dict__,
                }
            )
            continue
        programs.append(_to_program_seed(row, idx, source_name))

    deduped: dict[str, dict] = {}
    for record in programs:
        key = "|".join(
            [
                record["program_name"].lower(),
                record["administering_entity"].lower(),
                record["jurisdiction"].lower(),
                record["seed_row_type"],
            ]
        )
        existing = deduped.get(key)
        if existing is None or record["confidence"] > existing["confidence"]:
            deduped[key] = record

    return list(deduped.values()), quarantined


def main() -> None:
    pdf_path = Path(r"X:\Keyz\DPA\DPA One- Search Results 2026-02-28 05_24_14.pdf")
    output_dir = Path(r"X:\RARIS\research\sources")
    output_dir.mkdir(parents=True, exist_ok=True)

    programs, quarantined = convert(pdf_path)

    programs_path = output_dir / "dpa_seed_programs.json"
    anchors_path = output_dir / "dpa_seed_anchors.json"
    report_path = output_dir / "dpa_seed_conversion_report.json"

    anchors: list[dict] = []
    report = {
        "source_pdf": str(pdf_path),
        "generated_files": {
            "programs": str(programs_path),
            "anchors": str(anchors_path),
            "report": str(report_path),
        },
        "counts": {
            "program_records": len(programs),
            "anchor_records": len(anchors),
            "quarantined_records": len(quarantined),
        },
        "notes": [
            "PDF rows contain wrapped text and occasional OCR artifacts.",
            "Program records are deduplicated on (program, provider, jurisdiction, type).",
            "Quarantined rows were excluded from output seeds.",
        ],
        "quarantine_preview": quarantined[:20],
    }

    programs_path.write_text(json.dumps(programs, indent=2), encoding="utf-8")
    anchors_path.write_text(json.dumps(anchors, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote {len(programs)} program seed records -> {programs_path}")
    print(f"Wrote {len(anchors)} anchor seed records -> {anchors_path}")
    print(f"Wrote report -> {report_path}")


if __name__ == "__main__":
    main()
