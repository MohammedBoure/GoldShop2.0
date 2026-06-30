"""Touch helpers for inventory product entry workflows."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ui.touch_design import apply_touch_button_defaults
from ui.tools.virtual_numpad import VirtualNumpad


def open_numpad_for(
    parent: QWidget,
    target_widget,
    title: str,
    *,
    allow_decimal: bool = True,
) -> None:
    """Open the shared direct-entry numpad for a numeric widget."""
    dialog = VirtualNumpad(
        title=title,
        mode="direct",
        target_widget=target_widget,
        allow_decimal=allow_decimal,
        parent=parent.window() if isinstance(parent, QWidget) else None,
    )
    dialog.exec()


def make_numpad_button(
    parent: QWidget,
    target_widget,
    title: str,
    *,
    allow_decimal: bool = True,
) -> QPushButton:
    button = QPushButton("123")
    button.setObjectName("btn_touch_numpad")
    button.setToolTip("Pave numerique")
    button.setFixedWidth(58)
    apply_touch_button_defaults(button)
    button.clicked.connect(
        lambda _checked=False: open_numpad_for(
            parent,
            target_widget,
            title,
            allow_decimal=allow_decimal,
        )
    )
    return button


def wrap_with_numpad(
    parent: QWidget,
    target_widget,
    title: str,
    *,
    allow_decimal: bool = True,
) -> QWidget:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(target_widget, 1)
    row.addWidget(
        make_numpad_button(
            parent,
            target_widget,
            title,
            allow_decimal=allow_decimal,
        )
    )

    container = QWidget()
    container.setLayout(row)
    return container


def build_product_entry_summary(
    data: dict,
    receipt: dict | None,
    *,
    supplier_label: str = "",
    account_label: str = "",
) -> str:
    item_type = data.get("item_type") or "-"
    receipt_mode = (
        "Reception fournisseur a credit / cree un bon fournisseur"
        if receipt
        else "Stock uniquement / aucune dette fournisseur creee"
    )
    supplier = supplier_label or str(data.get("supplier_id") or "-")
    account = account_label or str((receipt or {}).get("supplier_account_id") or "-")
    return "\n".join(
        [
            "Verifiez les informations avant d'ajouter le produit.",
            "",
            f"Designation : {data.get('name') or '-'}",
            f"Type : {item_type}",
            f"Poids : {float(data.get('weight') or 0):,.3f} g",
            f"Quantite : {int(data.get('quantity') or 0)} pcs",
            f"Cout metal : {float(data.get('metal_cost_per_gram') or 0):,.2f} DA/g",
            f"Cout facon : {float(data.get('labor_cost_per_gram') or 0):,.2f} DA/g",
            f"Cout total : {float(data.get('total_cost') or 0):,.2f} DA",
            f"Prix vente : {float(data.get('selling_price') or 0):,.2f} DA",
            f"Fournisseur : {supplier}",
            f"Compte fournisseur : {account}",
            f"Traitement : {receipt_mode}",
        ]
    )


def confirm_product_entry(
    parent,
    data: dict,
    receipt: dict | None,
    *,
    supplier_label: str = "",
    account_label: str = "",
) -> bool:
    """Ask the operator to confirm financial/stock effects before saving."""
    if not isinstance(parent, QWidget):
        return True

    summary = build_product_entry_summary(
        data,
        receipt,
        supplier_label=supplier_label,
        account_label=account_label,
    )
    reply = QMessageBox.question(
        parent,
        "Confirmer l'ajout",
        summary,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return reply == QMessageBox.Yes


def after_save_options_text(item_name: str) -> str:
    name = item_name or "Produit"
    return (
        f"{name} ajoute. Options disponibles dans la ligne recente : "
        "Imprimer l'etiquette, ouvrir/modifier le produit, ou ajouter un autre produit."
    )
