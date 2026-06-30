"""Read-only touch readiness inventory for PySide dialogs.

The command scans Python source files for QDialog classes and reports whether
they appear to provide touch-friendly basics such as virtual keyboard/numpad
entry points, scrollable layouts, validation hints, and confirmation paths.
It is intentionally heuristic: the report is a triage manifest, not a UI test.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, TextIO


REPORT_KIND = "touch_dialog_gap_inventory"
SCHEMA_VERSION = 1

TEXT_INPUT_CALLS = {
    "QLineEdit",
    "QTextEdit",
    "QPlainTextEdit",
}

NUMERIC_INPUT_CALLS = {
    "QSpinBox",
    "QDoubleSpinBox",
    "QAbstractSpinBox",
}

DATE_TIME_INPUT_CALLS = {
    "QDateEdit",
    "QDateTimeEdit",
    "QTimeEdit",
}

TABLE_OR_LIST_CALLS = {
    "QTableWidget",
    "QTableView",
    "QTreeWidget",
    "QTreeView",
    "QListWidget",
    "QListView",
}

SCROLL_CALLS = {
    "QScrollArea",
}

FOOTER_CALLS = {
    "QDialogButtonBox",
}

KEYBOARD_MARKERS = {
    "VirtualKeyboardDialog",
    "TouchDialogMixin",
    "add_keyboard_button",
    "show_virtual_keyboard",
    "Afficher clavier",
    "Clavier",
    "keyboard",
}

NUMPAD_MARKERS = {
    "VirtualNumpad",
    "TouchDialogMixin",
    "create_numpad_button",
    "open_numpad_for",
    "open_numpad",
    "Pave numerique",
    "Pavé numérique",
    "numpad",
}

VALIDATION_MARKERS = {
    "QMessageBox.warning",
    "QMessageBox.critical",
    "validate",
    "validation",
    "accept_dialog",
}

CONFIRMATION_MARKERS = {
    "QMessageBox.question",
    "confirm",
    "confirmation",
    "Are you sure",
    "Etes-vous sur",
    "Êtes-vous sûr",
}

SENSITIVE_MARKERS = {
    "delete",
    "remove",
    "supprimer",
    "corrig",
    "refund",
    "reversal",
    "reverse",
    "publish",
    "publier",
    "payment",
    "paiement",
    "versement",
    "expense",
    "depense",
    "dépense",
    "supplier",
    "fournisseur",
    "cash",
    "caisse",
    "treasury",
    "tresor",
    "trésor",
    "stock",
}

IGNORED_DIRS = {
    "__pycache__",
    ".git",
    "build",
    "dist",
    "runtime",
    ".venv",
    "venv",
}


def _name_from_node(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name_from_node(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return _name_from_node(node.value)
    return ""


def _short_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _call_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _name_from_node(child.func)
            if name:
                names.add(_short_name(name))
                names.add(name)
    return names


def _class_bases(node: ast.ClassDef) -> Set[str]:
    bases: Set[str] = set()
    for base in node.bases:
        name = _name_from_node(base)
        if name:
            bases.add(name)
            bases.add(_short_name(name))
    return bases


def _has_marker(source: str, markers: Iterable[str]) -> bool:
    lowered = source.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def _source_lines(source: str) -> int:
    return len(source.splitlines()) if source else 0


def _is_qdialog_class(node: ast.ClassDef, known_dialog_classes: Set[str]) -> bool:
    bases = _class_bases(node)
    if "QDialog" in bases:
        return True
    return bool(bases.intersection(known_dialog_classes))


def _collect_dialog_class_names(trees: Sequence[ast.AST]) -> Set[str]:
    known: Set[str] = {"QDialog"}
    changed = True
    while changed:
        changed = False
        for tree in trees:
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if node.name in known:
                    continue
                bases = _class_bases(node)
                if "QDialog" in bases or bases.intersection(known):
                    known.add(node.name)
                    changed = True
    return known


def _dialog_findings(
    class_name: str,
    source: str,
    calls: Set[str],
    source_line_count: int,
) -> List[str]:
    has_text_inputs = bool(calls.intersection(TEXT_INPUT_CALLS))
    has_numeric_inputs = bool(calls.intersection(NUMERIC_INPUT_CALLS))
    has_date_time_inputs = bool(calls.intersection(DATE_TIME_INPUT_CALLS))
    has_table_or_list = bool(calls.intersection(TABLE_OR_LIST_CALLS))
    has_scroll_area = bool(calls.intersection(SCROLL_CALLS))
    has_footer = bool(calls.intersection(FOOTER_CALLS)) or _has_marker(source, {"btn_save", "btn_cancel", "Annuler"})
    has_keyboard = _has_marker(source, KEYBOARD_MARKERS)
    has_numpad = _has_marker(source, NUMPAD_MARKERS)
    has_validation = _has_marker(source, VALIDATION_MARKERS)
    has_confirmation = _has_marker(source, CONFIRMATION_MARKERS)
    sensitive = _has_marker(f"{class_name}\n{source}", SENSITIVE_MARKERS)

    findings: List[str] = []
    if has_text_inputs and not has_keyboard:
        findings.append("NEEDS_KEYBOARD")
    if has_numeric_inputs and not has_numpad:
        findings.append("NEEDS_NUMPAD")
    if has_date_time_inputs and not (has_numpad or "calendarPopup" in source or "setCalendarPopup" in source):
        findings.append("NEEDS_TOUCH_DATE_INPUT")
    large_or_complex = source_line_count >= 180 or has_table_or_list or (
        has_text_inputs and has_numeric_inputs and source_line_count >= 90
    )
    if large_or_complex and not has_scroll_area:
        findings.append("NEEDS_LAYOUT_FIX")
    if large_or_complex and not has_footer:
        findings.append("NEEDS_FIXED_FOOTER_REVIEW")
    if sensitive and not has_confirmation:
        findings.append("NEEDS_CONFIRMATION")
    if (has_text_inputs or has_numeric_inputs or sensitive) and not has_validation:
        findings.append("NEEDS_VALIDATION_REVIEW")
    if not findings:
        findings.append("TOUCH_READY")
    return findings


def _recommendations(findings: Sequence[str]) -> List[str]:
    recommendations: List[str] = []
    if "NEEDS_KEYBOARD" in findings:
        recommendations.append("Add a visible Clavier/Afficher clavier button wired to VirtualKeyboardDialog.")
    if "NEEDS_NUMPAD" in findings:
        recommendations.append("Add Pavé numérique buttons next to numeric inputs using VirtualNumpad in direct mode.")
    if "NEEDS_TOUCH_DATE_INPUT" in findings:
        recommendations.append("Use a touch-friendly date picker or explicit date controls.")
    if "NEEDS_LAYOUT_FIX" in findings:
        recommendations.append("Review size, QScrollArea usage, touch spacing, and table/list row heights.")
    if "NEEDS_FIXED_FOOTER_REVIEW" in findings:
        recommendations.append("Keep Save/Cancel/Validate actions in a fixed footer outside scrollable content.")
    if "NEEDS_CONFIRMATION" in findings:
        recommendations.append("Show a clear summary and confirmation before the sensitive operation.")
    if "NEEDS_VALIDATION_REVIEW" in findings:
        recommendations.append("Add field validation and user-facing recovery guidance.")
    return recommendations


def _analyze_class(
    path: Path,
    repo_root: Path,
    source: str,
    node: ast.ClassDef,
) -> Dict[str, Any]:
    class_source = ast.get_source_segment(source, node) or ""
    calls = _call_names(node)
    source_line_count = _source_lines(class_source)
    findings = _dialog_findings(node.name, class_source, calls, source_line_count)
    relative_path = path.relative_to(repo_root).as_posix()
    return {
        "class_name": node.name,
        "file": relative_path,
        "line": node.lineno,
        "source_lines": source_line_count,
        "inputs": {
            "text": bool(calls.intersection(TEXT_INPUT_CALLS)),
            "numeric": bool(calls.intersection(NUMERIC_INPUT_CALLS)),
            "date_time": bool(calls.intersection(DATE_TIME_INPUT_CALLS)),
            "table_or_list": bool(calls.intersection(TABLE_OR_LIST_CALLS)),
        },
        "touch_support": {
            "keyboard": _has_marker(class_source, KEYBOARD_MARKERS),
            "numpad": _has_marker(class_source, NUMPAD_MARKERS),
            "scroll_area": bool(calls.intersection(SCROLL_CALLS)),
            "dialog_button_box": bool(calls.intersection(FOOTER_CALLS)),
            "validation_hint": _has_marker(class_source, VALIDATION_MARKERS),
            "confirmation_hint": _has_marker(class_source, CONFIRMATION_MARKERS),
        },
        "findings": findings,
        "recommendations": _recommendations(findings),
    }


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def _parse_files(paths: Sequence[Path]) -> List[tuple[Path, str, ast.AST]]:
    parsed: List[tuple[Path, str, ast.AST]] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        parsed.append((path, source, tree))
    return parsed


def analyze_dialogs(source_root: Path | str, repo_root: Optional[Path | str] = None) -> Dict[str, Any]:
    root = Path(source_root).resolve()
    repo = Path(repo_root).resolve() if repo_root is not None else root
    paths = list(_iter_python_files(root))
    parsed = _parse_files(paths)
    known_dialog_classes = _collect_dialog_class_names([tree for _, _, tree in parsed])

    dialogs: List[Dict[str, Any]] = []
    for path, source, tree in parsed:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_qdialog_class(node, known_dialog_classes):
                if node.name in {"QDialog"}:
                    continue
                dialogs.append(_analyze_class(path, repo, source, node))

    finding_counts: Counter[str] = Counter()
    for dialog in dialogs:
        finding_counts.update(dialog["findings"])

    return {
        "report_kind": REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "source_root": root.as_posix(),
        "dialog_count": len(dialogs),
        "finding_counts": dict(sorted(finding_counts.items())),
        "dialogs": sorted(dialogs, key=lambda item: (item["file"], item["line"], item["class_name"])),
    }


def _write_json(report: Dict[str, Any], handle: TextIO) -> None:
    json.dump(report, handle, ensure_ascii=False, indent=2)
    handle.write("\n")


def _write_markdown(report: Dict[str, Any], handle: TextIO) -> None:
    handle.write("# Touch Dialog Gap Inventory\n\n")
    handle.write(f"- Report kind: `{report['report_kind']}`\n")
    handle.write(f"- Dialog count: `{report['dialog_count']}`\n")
    handle.write(f"- Source root: `{report['source_root']}`\n\n")

    handle.write("## Finding Counts\n\n")
    handle.write("| Finding | Count |\n")
    handle.write("| --- | ---: |\n")
    for finding, count in report["finding_counts"].items():
        handle.write(f"| `{finding}` | {count} |\n")

    handle.write("\n## Dialogs\n\n")
    handle.write("| Dialog | Location | Findings | Inputs |\n")
    handle.write("| --- | --- | --- | --- |\n")
    for dialog in report["dialogs"]:
        inputs = ", ".join(name for name, enabled in dialog["inputs"].items() if enabled) or "-"
        findings = ", ".join(f"`{finding}`" for finding in dialog["findings"])
        location = f"{dialog['file']}:{dialog['line']}"
        handle.write(f"| `{dialog['class_name']}` | `{location}` | {findings} | {inputs} |\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze QDialog touch readiness.")
    parser.add_argument(
        "source_root",
        nargs="?",
        default="ui",
        help="Directory to scan. Defaults to ui.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for relative paths. Defaults to current directory.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Defaults to stdout.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    report = analyze_dialogs(args.source_root, args.repo_root)
    writer = _write_markdown if args.format == "markdown" else _write_json

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            writer(report, handle)
    else:
        import sys

        writer(report, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
