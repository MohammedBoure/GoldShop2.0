# Inventory List Sub-module (`ui/widgets/inventory/inventory_list`)

Ce sous-module gère l'affichage principal des listes de stocks, les filtres avancés, et le formulaire d'ajout/modification d'articles.

---

## Structure des fichiers :

* `__init__.py` : Point d'entrée du sous-module exportant les vues et composants principaux.
* `_helpers.py` : Fonctions utilitaires partagées, convertisseurs de formats, helpers graphiques et formats de données.
* `inventory_form_tab.py` : Onglet formulaire pour la création, la modification et la validation des fiches articles en stock.
* `inventory_list_tab.py` : Onglet tableau listant les articles en stock, avec gestion des colonnes, filtres d'état (Available, Sold, Reserved, Partially_Sold), pagination et actions contextuelles.
