# Tests Suite (`tests/`)

Ce dossier contient l'ensemble des tests unitaires et scripts de validation fonctionnelle pour le backend et l'interface utilisateur de l'application GoldShop.

---

## Fichiers de tests :

* `test_versement_idempotency_and_weight.py` : Tests unitaires vérifiant l'idempotence des clôtures et annulations de versements, le bornage des poids sortis au poids réel de l'article, et la restauration de stock bornée sans duplication.
* `test_excel_journal_features.py` : Tests des fonctionnalités et calculs du journal Excel quotidien des ventes et recettes.
* `test_profit_calculator.py` : Tests des calculs de bénéfices, déductions de versements et analyse financière.
* `test_invoice_pdf_generator.py` : Tests de génération de factures PDF et tickets thermiques.
* `test_versement_pricing.py` : Tests du calcul des prix, conversions de devises et déductions d'or cassé pour les versements.
* `test_versement_quantity_manager.py` : Tests de gestion des quantités pour les articles vendus à la pièce (`PIECE`).
* `test_versement_quantity_ui.py` : Tests d'interface graphique pour la sélection et réservation de quantités.
* `test_versement_reservation.py` : Tests du verrouillage et de la libération des articles réservés en inventaire.
* `test_versement_custom_notes.py` : Tests de persistance et transfert des notes personnalisées lors des clôtures de versements.
* `test_flow.py` : Script d'intégration pour le flux complet création-annulation-restauration de versement.
* `test_restore.py`, `test_restore_2.py`, `test_failures.py`, `test_duplicates.py`, `test_zero_weight.py`, `test_annule.py`, `test_items.py`, `test_v2.py` : Scripts de validation pour cas limites et diagnostics d'intégrité de la base de données.
