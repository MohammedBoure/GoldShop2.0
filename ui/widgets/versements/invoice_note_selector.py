"""Shared helpers for Versement product-level invoice notes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


MAX_CUSTOM_NOTE_LENGTH = 255
EMPTY_NOTE_LABEL = "--- Note ---"


def normalize_custom_note(value):
    """Return the persisted snapshot format used by SaleItems.custom_note."""
    return str(value or "").strip()[:MAX_CUSTOM_NOTE_LENGTH]


def get_invoice_note_values(manager):
    """Load the POS note catalogue without making the dialog fail if unavailable."""
    try:
        values = manager.invoice_notes.get_all_notes()
    except Exception:
        values = []

    notes = []
    seen = set()
    for value in values or []:
        note = normalize_custom_note(value)
        if note and note not in seen:
            notes.append(note)
            seen.add(note)
    return notes


def create_invoice_note_combo(manager, current_value="", parent=None):
    """Build the Versement equivalent of the POS ``À Vendre`` selector."""
    combo = QComboBox(parent)
    combo.addItem(EMPTY_NOTE_LABEL, "")

    available_notes = get_invoice_note_values(manager)
    for note in available_notes:
        combo.addItem(note, note)

    current_note = normalize_custom_note(current_value)
    if current_note and current_note not in available_notes:
        combo.addItem(f"{current_note} (valeur actuelle)", current_note)
        combo.setItemData(combo.count() - 1, "Cette valeur historique n'existe plus dans InvoiceNotes.", Qt.ToolTipRole)

    current_index = combo.findData(current_note)
    combo.setCurrentIndex(current_index if current_index >= 0 else 0)
    combo.setMaxVisibleItems(20)
    combo.setStyleSheet("font-size: 14px; padding: 5px;")
    return combo


def selected_custom_note(combo):
    return normalize_custom_note(combo.currentData())
