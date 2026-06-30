from __future__ import annotations

from datetime import date, datetime

import qtawesome as qta
from PySide6.QtWidgets import QLabel, QPushButton

from ui.touch_design import apply_touch_button_defaults


def as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt_weight(value) -> str:
    return f"{as_float(value):,.3f} g"


def fmt_money(value) -> str:
    return f"{as_float(value):,.2f} DA"


def fmt_unit(value) -> str:
    return f"{as_float(value):,.2f} DA/g"


def fmt_date(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def operation_label(value) -> str:
    return "Entree" if str(value or "").upper() == "INCOMING" else "Sortie"


def make_action_button(text: str, icon_name: str, permission_key: str, *, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(qta.icon(icon_name, color="white" if primary else "#0f8f83"))
    button.setProperty("permission_key", permission_key)
    button.setProperty("permission_label", text)
    button.setProperty("ui_element_type", "action")
    apply_touch_button_defaults(button, primary=primary)
    return button


def value_label(text: str = "-") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("ui_element_type", "display_field")
    return label
