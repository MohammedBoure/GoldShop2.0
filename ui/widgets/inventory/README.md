# Inventory UI Module (`ui/widgets/inventory`)

Ce module gère l'interface utilisateur pour la gestion des stocks, la consultation des articles et la saisie rapide des produits.

---

## Structure des fichiers :

* `touch_product_entry.py` : Interface et assistants de saisie tactile pour l'enregistrement des articles en inventaire (pavé numérique direct, boîtes de dialogue).
* `inventory_list/` : Sous-module contenant l'onglet de consultation, filtrage avancé et gestion détaillée du stock (`InventoryListTab`).
* `tabs_batches/` : Sous-module gérant la saisie rapide à haute fréquence (`InventoryFormTab`) avec interface scindée réactive et tableau de session.
