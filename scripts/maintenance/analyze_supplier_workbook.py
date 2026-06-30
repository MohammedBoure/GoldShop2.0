"""Read-only scope analysis for the legacy supplier workbook.

This command deliberately does not import the application database layer. It
reads an ``.xls`` workbook and produces a review manifest; publishing rows to
the supplier ledger is a separate, later operation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, TextIO


SUPPLIER_CANDIDATE = "SUPPLIER_CANDIDATE"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
NEEDS_MAPPING = "NEEDS_MAPPING"

REPORT_KIND = "legacy_supplier_workbook_scope"
REPORT_SCHEMA_VERSION = 1
HEADER_SCAN_ROWS = 30

STAGE_NEEDS_REVIEW = "NEEDS_REVIEW"
STAGE_OUT_OF_SCOPE = "OUT_OF_SCOPE"
STAGE_IGNORED_TOTAL = "IGNORED_TOTAL"

KNOWN_OUT_OF_SCOPE_SHEETS = {
    "tpe": "Electronic collection ledger is not a supplier account.",
    "tpe h1": "Electronic collection ledger is not a supplier account.",
    "or casse 2023": "Scrap metal ledger is outside supplier migration scope.",
    "bono": "Special merchandise/metal ledger is outside supplier migration scope.",
    "appartement delly ibrahim": "Asset/general ledger is outside supplier migration scope.",
    "marchandise h1": "Merchandise ledger is outside confirmed supplier scope.",
    "h2s nv": "Unconfirmed general ledger is outside supplier migration scope.",
    "xadv 750": "Unconfirmed general ledger is outside supplier migration scope.",
}

OUT_OF_SCOPE_PREFIXES = {
    "tpe": "Electronic collection ledger is not a supplier account.",
    "or casse": "Scrap metal ledger is outside supplier migration scope.",
    "bono": "Special merchandise/metal ledger is outside supplier migration scope.",
}

UNCONFIRMED_GENERAL_NAME_HINTS = {
    "appartement",
    "banque",
    "caisse",
    "charge",
    "depense",
    "loyer",
    "marchandise",
    "stock",
    "xadv",
}

SPECIAL_SUPPLIER_REVIEW_SHEETS = {"ballo", "badi"}

HEADER_ALIASES = {
    "date": {"date", "jour", "transaction date"},
    "weight": {"poids", "poid", "weight", "gramme", "grammes"},
    "labor": {"afacon", "facon", "labor", "main oeuvre"},
    "amount": {"montant", "amount", "somme"},
    "purity": {"titre", "titrage", "purity", "purete"},
    "fixing": {"fixing", "fixage", "cours", "fixing price"},
    "notes": {"obs", "observation", "observations", "note", "notes"},
}

ACCOUNT_ALIASES = {
    "local": "LOCAL",
    "locale": "LOCAL",
    "import": "IMPORT",
    "importation": "IMPORT",
}

TOTAL_MARKERS = {"total", "totaux", "solde", "balance", "cumul", "reste"}


def _normalized_text(value: Any) -> str:
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = "".join(char if char.isalnum() else " " for char in ascii_text)
    return " ".join(cleaned.casefold().split())


def _canonical_header(value: Any) -> Optional[str]:
    candidate = _normalized_text(value)
    if not candidate:
        return None
    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if candidate == alias or candidate.startswith(alias + " "):
                return field_name
    return None


def _account_hint(value: Any) -> Optional[str]:
    candidate = _normalized_text(value)
    return ACCOUNT_ALIASES.get(candidate)


def _out_of_scope_reason(normalized_sheet_name: str) -> Optional[str]:
    exact_reason = KNOWN_OUT_OF_SCOPE_SHEETS.get(normalized_sheet_name)
    if exact_reason:
        return exact_reason
    for prefix, reason in OUT_OF_SCOPE_PREFIXES.items():
        if normalized_sheet_name == prefix or normalized_sheet_name.startswith(prefix + " "):
            return reason
    return None


def _looks_like_unconfirmed_general_ledger(normalized_sheet_name: str) -> bool:
    words = set(normalized_sheet_name.split())
    return bool(words.intersection(UNCONFIRMED_GENERAL_NAME_HINTS))


def _decimal_cell(value: Any) -> Optional[Decimal]:
    """Return only typed numeric spreadsheet values, avoiding text guesses."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return None


def _format_decimal(value: Decimal, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum), f".{places}f")


def _sheet_value(sheet: Any, row_index: int, column_index: int) -> Any:
    if row_index < 0 or column_index < 0:
        return ""
    try:
        return sheet.cell_value(row_index, column_index)
    except IndexError:
        return ""


def _field_columns(sheet: Any, row_index: int, start_column: int, end_column: int) -> Dict[str, int]:
    fields: Dict[str, int] = {}
    for column_index in range(start_column, end_column + 1):
        field_name = _canonical_header(_sheet_value(sheet, row_index, column_index))
        if field_name and field_name not in fields:
            fields[field_name] = column_index
    return fields


def _find_account_hint(sheet: Any, header_row: int, start_column: int, end_column: int) -> Optional[str]:
    for row_index in range(max(0, header_row - 2), header_row + 1):
        for column_index in range(start_column, end_column + 1):
            hint = _account_hint(_sheet_value(sheet, row_index, column_index))
            if hint:
                return hint
    return None


def _has_supplier_columns(fields: Dict[str, int]) -> bool:
    return "date" in fields and "weight" in fields and (
        "labor" in fields or "amount" in fields
    )


def _find_segments(sheet: Any) -> List[Dict[str, Any]]:
    scan_limit = min(int(sheet.nrows), HEADER_SCAN_ROWS)
    for row_index in range(scan_limit):
        recognized = [
            (_canonical_header(_sheet_value(sheet, row_index, column_index)), column_index)
            for column_index in range(int(sheet.ncols))
        ]
        date_columns = [column_index for field, column_index in recognized if field == "date"]
        if not date_columns:
            all_fields = _field_columns(sheet, row_index, 0, max(0, int(sheet.ncols) - 1))
            if _has_supplier_columns(all_fields):
                date_columns = [min(all_fields.values())]
        if not date_columns:
            continue

        segments: List[Dict[str, Any]] = []
        for position, start_column in enumerate(date_columns):
            end_column = (
                date_columns[position + 1] - 1
                if position + 1 < len(date_columns)
                else int(sheet.ncols) - 1
            )
            fields = _field_columns(sheet, row_index, start_column, end_column)
            if len(fields) < 2:
                continue
            segments.append(
                {
                    "account_hint": _find_account_hint(sheet, row_index, start_column, end_column)
                    or "UNMAPPED",
                    "header_row": row_index + 1,
                    "start_column": start_column + 1,
                    "end_column": end_column + 1,
                    "columns": {name: column + 1 for name, column in fields.items()},
                    "_zero_based_columns": fields,
                }
            )
        if segments:
            return segments
    return []


def _is_summary_row(sheet: Any, row_index: int, segment: Dict[str, Any]) -> bool:
    columns = segment["_zero_based_columns"]
    numeric_columns = [
        columns[field_name]
        for field_name in ("weight", "labor", "amount")
        if field_name in columns
    ]
    end_of_label = min(numeric_columns) if numeric_columns else segment["end_column"] - 1
    label_text = " ".join(
        _normalized_text(_sheet_value(sheet, row_index, column_index))
        for column_index in range(segment["start_column"] - 1, end_of_label + 1)
    )
    words = set(label_text.split())
    return bool(words.intersection(TOTAL_MARKERS))


def _analyze_segment(sheet: Any, segment: Dict[str, Any]) -> Dict[str, Any]:
    columns = segment["_zero_based_columns"]
    candidate_rows = 0
    weight_total = Decimal("0")
    amount_total = Decimal("0")
    ignored_textual_numeric_cells = 0

    for row_index in range(segment["header_row"], int(sheet.nrows)):
        if _is_summary_row(sheet, row_index, segment):
            continue

        numeric_values: Dict[str, Optional[Decimal]] = {
            field_name: _decimal_cell(_sheet_value(sheet, row_index, columns[field_name]))
            for field_name in ("weight", "labor", "amount")
            if field_name in columns
        }
        for field_name in ("weight", "amount"):
            if (
                field_name in columns
                and numeric_values.get(field_name) is None
                and str(_sheet_value(sheet, row_index, columns[field_name])).strip()
            ):
                ignored_textual_numeric_cells += 1
        if not any(value is not None for value in numeric_values.values()):
            continue

        candidate_rows += 1
        if numeric_values.get("weight") is not None:
            weight_total += numeric_values["weight"] or Decimal("0")
        if numeric_values.get("amount") is not None:
            amount_total += numeric_values["amount"] or Decimal("0")

    warnings: List[str] = []
    if ignored_textual_numeric_cells:
        warnings.append(
            "Text values in numeric columns were excluded from totals to avoid guessing separators or units."
        )

    result = {key: value for key, value in segment.items() if key != "_zero_based_columns"}
    result.update(
        {
            "candidate_transaction_rows": candidate_rows,
            "visible_weight_total": _format_decimal(weight_total, 3),
            "visible_amount_total": _format_decimal(amount_total, 2),
            "warnings": warnings,
        }
    )
    return result


def analyze_sheet(sheet: Any) -> Dict[str, Any]:
    raw_segments = _find_segments(sheet)
    segments = [_analyze_segment(sheet, segment) for segment in raw_segments]
    sheet_name = str(sheet.name)
    normalized_name = _normalized_text(sheet_name)
    candidate_rows = sum(segment["candidate_transaction_rows"] for segment in segments)
    weight_total = sum(
        (Decimal(segment["visible_weight_total"]) for segment in segments), Decimal("0")
    )
    amount_total = sum(
        (Decimal(segment["visible_amount_total"]) for segment in segments), Decimal("0")
    )
    warnings = [warning for segment in segments for warning in segment["warnings"]]
    exclusion_reason = _out_of_scope_reason(normalized_name)

    if exclusion_reason:
        classification = OUT_OF_SCOPE
        reasons = [exclusion_reason]
    elif normalized_name in SPECIAL_SUPPLIER_REVIEW_SHEETS:
        classification = NEEDS_MAPPING
        reasons = ["Known supplier-like sheet uses a special format that requires explicit mapping."]
    elif _looks_like_unconfirmed_general_ledger(normalized_name):
        classification = NEEDS_MAPPING
        reasons = ["Sheet name indicates an unconfirmed general or asset ledger, not an automatic supplier."]
    elif not segments:
        classification = NEEDS_MAPPING
        reasons = ["No supplier-style Date/Poids/Afacon/Montant section was detected."]
    elif not all(_has_supplier_columns(segment["_zero_based_columns"]) for segment in raw_segments):
        classification = NEEDS_MAPPING
        reasons = ["Detected columns do not form a complete supplier-style section."]
    elif len(segments) > 1 and {
        segment["account_hint"] for segment in segments
    } != {"LOCAL", "IMPORT"}:
        classification = NEEDS_MAPPING
        reasons = ["Multiple horizontal sections were found but LOCAL/IMPORT mapping is not explicit."]
    elif candidate_rows == 0:
        classification = NEEDS_MAPPING
        reasons = ["A supplier-style header exists, but no typed numeric transaction rows were detected."]
    else:
        classification = SUPPLIER_CANDIDATE
        if len(segments) > 1:
            reasons = ["Supplier-style LOCAL and IMPORT sections were detected separately."]
        else:
            reasons = ["A supplier-style transaction section with typed numeric rows was detected."]

    if classification == NEEDS_MAPPING:
        warnings.append("Review this sheet manually before any later staging or import operation.")

    return {
        "sheet_name": sheet_name,
        "row_count": int(sheet.nrows),
        "column_count": int(sheet.ncols),
        "classification": classification,
        "classification_reasons": reasons,
        "warnings": sorted(set(warnings)),
        "candidate_transaction_rows": candidate_rows,
        "visible_weight_total": _format_decimal(weight_total, 3),
        "visible_amount_total": _format_decimal(amount_total, 2),
        "segments": segments,
    }


def analyze_workbook(workbook: Any, source_name: str = "<workbook>") -> Dict[str, Any]:
    sheets = [analyze_sheet(workbook.sheet_by_name(name)) for name in workbook.sheet_names()]
    classifications = Counter(sheet["classification"] for sheet in sheets)
    return {
        "report_kind": REPORT_KIND,
        "schema_version": REPORT_SCHEMA_VERSION,
        "read_only": True,
        "source": {"file_name": Path(source_name).name, "file_type": ".xls"},
        "classification_counts": {
            classification: classifications.get(classification, 0)
            for classification in (SUPPLIER_CANDIDATE, OUT_OF_SCOPE, NEEDS_MAPPING)
        },
        "sheets": sheets,
    }


def _json_cell_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _normalized_date_value(workbook: Any, sheet: Any, row_index: int, column_index: int) -> Optional[str]:
    value = _sheet_value(sheet, row_index, column_index)
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    cell_type = None
    try:
        cell_type = sheet.cell_type(row_index, column_index)
    except AttributeError:
        pass
    if cell_type == 3 and isinstance(value, (int, float)):
        import xlrd

        return xlrd.xldate_as_datetime(value, int(getattr(workbook, "datemode", 0))).date().isoformat()

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return text


def _staging_segment(segment: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(segment)
    result["_zero_based_columns"] = {
        field_name: int(column_index) - 1
        for field_name, column_index in segment["columns"].items()
    }
    return result


def _staging_row(
    *,
    sheet_name: str,
    classification: str,
    section_hint: str,
    segment_start_column: Optional[int] = None,
    row_number: int,
    raw_values: Dict[str, Any],
    normalized_values: Dict[str, Any],
    proposed_operation_type: Optional[str],
    validation_status: str,
    validation_message: str,
) -> Dict[str, Any]:
    return {
        "sheet_name": sheet_name,
        "sheet_classification": classification,
        "section_hint": section_hint,
        "segment_start_column": segment_start_column,
        "row_number": row_number,
        "raw_values": raw_values,
        "normalized_values": normalized_values,
        "proposed_operation_type": proposed_operation_type,
        "validation_status": validation_status,
        "validation_message": validation_message,
    }


def extract_staging_rows(
    workbook: Any,
    report: Optional[Dict[str, Any]] = None,
    manually_included_sheets: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Extract review rows for database staging without publishing supplier balances.

    Unlike the scope report, these rows can contain original cell values. Callers
    must keep them in authorized runtime storage and must not write real workbook
    rows into committed fixtures or generated reports.
    """
    report = report or analyze_workbook(workbook)
    rows: List[Dict[str, Any]] = []
    manual_sheet_names = set(manually_included_sheets or [])

    for sheet_report in report["sheets"]:
        sheet_name = sheet_report["sheet_name"]
        classification = sheet_report["classification"]
        message = " | ".join(sheet_report["classification_reasons"])
        if classification == OUT_OF_SCOPE:
            rows.append(
                _staging_row(
                    sheet_name=sheet_name,
                    classification=classification,
                    section_hint="",
                    segment_start_column=None,
                    row_number=0,
                    raw_values={},
                    normalized_values={},
                    proposed_operation_type=None,
                    validation_status=STAGE_OUT_OF_SCOPE,
                    validation_message=message,
                )
            )
            continue
        if classification == NEEDS_MAPPING and sheet_name not in manual_sheet_names:
            rows.append(
                _staging_row(
                    sheet_name=sheet_name,
                    classification=classification,
                    section_hint="UNMAPPED",
                    segment_start_column=None,
                    row_number=0,
                    raw_values={},
                    normalized_values={},
                    proposed_operation_type=None,
                    validation_status=STAGE_NEEDS_REVIEW,
                    validation_message=message + " Include this sheet explicitly to stage its source rows.",
                )
            )
            continue

        sheet = workbook.sheet_by_name(sheet_name)
        staged_sheet_rows = 0
        for visible_segment in sheet_report["segments"]:
            segment = _staging_segment(visible_segment)
            columns = segment["_zero_based_columns"]
            section_hint = visible_segment["account_hint"]
            for row_index in range(segment["header_row"], int(sheet.nrows)):
                raw_values = {
                    field_name: _json_cell_value(_sheet_value(sheet, row_index, column_index))
                    for field_name, column_index in columns.items()
                }
                if not any(str(value or "").strip() for value in raw_values.values()):
                    continue

                if _is_summary_row(sheet, row_index, segment):
                    rows.append(
                        _staging_row(
                            sheet_name=sheet_name,
                            classification=classification,
                            section_hint=section_hint,
                            segment_start_column=visible_segment["start_column"],
                            row_number=row_index + 1,
                            raw_values=raw_values,
                            normalized_values={},
                            proposed_operation_type=None,
                            validation_status=STAGE_IGNORED_TOTAL,
                            validation_message="Summary/total row retained for review and excluded from transactions.",
                        )
                    )
                    staged_sheet_rows += 1
                    continue

                normalized_values: Dict[str, Any] = {}
                if "date" in columns:
                    normalized_values["operation_date"] = _normalized_date_value(
                        workbook, sheet, row_index, columns["date"]
                    )
                typed_numbers = {
                    field_name: _decimal_cell(_sheet_value(sheet, row_index, columns[field_name]))
                    for field_name in ("weight", "labor", "amount", "purity", "fixing")
                    if field_name in columns
                }
                field_names = {
                    "weight": "raw_weight",
                    "labor": "labor_price_per_gram",
                    "amount": "money_amount",
                    "purity": "input_purity",
                    "fixing": "fixing_price_per_gram",
                }
                for source_field, target_field in field_names.items():
                    value = typed_numbers.get(source_field)
                    if value is not None:
                        places = 3 if source_field == "weight" else 2
                        normalized_values[target_field] = _format_decimal(value, places)
                if "notes" in raw_values:
                    normalized_values["notes"] = raw_values["notes"]

                numeric_values = [value for value in typed_numbers.values() if value is not None]
                if not numeric_values:
                    row_message = "Row contains no typed numeric supplier value and requires manual mapping."
                    proposed_type = None
                else:
                    row_message = "Supplier row requires supplier/account review before any later publication."
                    proposed_type = "GOODS_RECEIPT" if classification == SUPPLIER_CANDIDATE else None
                    if typed_numbers.get("weight") is not None and typed_numbers.get("labor") is not None:
                        calculated = (typed_numbers["weight"] * typed_numbers["labor"]).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                        normalized_values["calculated_labor_amount"] = _format_decimal(calculated, 2)
                        if typed_numbers.get("amount") is not None:
                            difference = typed_numbers["amount"] - calculated
                            normalized_values["amount_difference"] = _format_decimal(difference, 2)
                            normalized_values["requires_review"] = difference != Decimal("0")
                            if difference != Decimal("0"):
                                row_message += " Montant differs from Poids x Afacon."

                rows.append(
                    _staging_row(
                        sheet_name=sheet_name,
                        classification=classification,
                        section_hint=section_hint,
                        segment_start_column=visible_segment["start_column"],
                        row_number=row_index + 1,
                        raw_values=raw_values,
                        normalized_values=normalized_values,
                        proposed_operation_type=proposed_type,
                        validation_status=STAGE_NEEDS_REVIEW,
                        validation_message=row_message,
                    )
                )
                staged_sheet_rows += 1

        if staged_sheet_rows == 0:
            rows.append(
                _staging_row(
                    sheet_name=sheet_name,
                    classification=classification,
                    section_hint="UNMAPPED",
                    segment_start_column=None,
                    row_number=0,
                    raw_values={},
                    normalized_values={},
                    proposed_operation_type=None,
                    validation_status=STAGE_NEEDS_REVIEW,
                    validation_message=message,
                )
            )
    return rows


def analyze_workbook_path(
    workbook_path: str | Path,
    opener: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    path = Path(workbook_path)
    if path.suffix.casefold() != ".xls":
        raise ValueError("The legacy scope analyzer accepts .xls workbooks only.")
    if opener is None:
        import xlrd

        opener = xlrd.open_workbook

    workbook = opener(str(path), on_demand=True)
    try:
        return analyze_workbook(workbook, path.name)
    finally:
        release_resources = getattr(workbook, "release_resources", None)
        if callable(release_resources):
            release_resources()


def _csv_rows(report: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for sheet in report["sheets"]:
        yield {
            "sheet_name": sheet["sheet_name"],
            "row_count": sheet["row_count"],
            "column_count": sheet["column_count"],
            "classification": sheet["classification"],
            "candidate_transaction_rows": sheet["candidate_transaction_rows"],
            "visible_weight_total": sheet["visible_weight_total"],
            "visible_amount_total": sheet["visible_amount_total"],
            "segment_count": len(sheet["segments"]),
            "account_hints": ",".join(segment["account_hint"] for segment in sheet["segments"]),
            "classification_reasons": " | ".join(sheet["classification_reasons"]),
            "warnings": " | ".join(sheet["warnings"]),
        }


def write_report(report: Dict[str, Any], stream: TextIO, report_format: str = "json") -> None:
    if report_format == "json":
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        return
    if report_format != "csv":
        raise ValueError(f"Unsupported report format: {report_format}")

    fieldnames = [
        "sheet_name",
        "row_count",
        "column_count",
        "classification",
        "candidate_transaction_rows",
        "visible_weight_total",
        "visible_amount_total",
        "segment_count",
        "account_hints",
        "classification_reasons",
        "warnings",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(_csv_rows(report))


def _write_output(report: Dict[str, Any], output: str, report_format: str) -> None:
    if output == "-":
        write_report(report, sys.stdout, report_format)
        return
    with Path(output).open("w", encoding="utf-8", newline="") as stream:
        write_report(report, stream, report_format)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze legacy supplier workbook scope without writing application data."
    )
    parser.add_argument("workbook", help="Input legacy .xls workbook path.")
    parser.add_argument(
        "--output",
        "-o",
        default="-",
        help="Report path, or '-' for standard output (default).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        dest="report_format",
        help="Report format; inferred from a .csv output name or defaults to JSON.",
    )
    args = parser.parse_args(argv)
    report_format = args.report_format or (
        "csv" if args.output.casefold().endswith(".csv") else "json"
    )

    report = analyze_workbook_path(args.workbook)
    _write_output(report, args.output, report_format)
    if args.output != "-":
        counts = report["classification_counts"]
        print(
            "Read-only scope report written: "
            f"{counts[SUPPLIER_CANDIDATE]} candidate, "
            f"{counts[OUT_OF_SCOPE]} out of scope, "
            f"{counts[NEEDS_MAPPING]} needing mapping.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
