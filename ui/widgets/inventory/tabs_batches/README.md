# Rapid Entry & Batch Inventory Module (`ui/widgets/inventory/tabs_batches`)

Ce sous-module gère l'interface de saisie rapide d'articles d'inventaire et le suivi en direct de la session d'ajout pour les bijouteries. Il adopte une architecture réactive à double mode (Dual-Mode Responsive Splitter) éliminant tout défilement vertical et évitant le rétrécissement des champs ou du tableau sur toutes les résolutions (de 1024×768 jusqu'à 2K).

---

## Fichiers du module :

* `__init__.py` : Point d'entrée du package exportant le widget principal `InventoryFormTab`.
* `tabs_batches.py` : Widget racine (`InventoryFormTab`) intégrant la logique de rupture responsive (`resizeEvent`) :
  - **Mode Large (Largeur ≥ 1120px)** : `QSplitter` horizontal avec stretch factor 1 pour le formulaire et 0 pour le tableau, bloquant le tableau à 450px (`setMinimumWidth(440)`).
  - **Mode Compact (Largeur < 1120px)** : Basculement automatique en mode tiroir vertical (Vertical Drawer) allouant 100% de la largeur au formulaire, avec bouton de bascule manuelle (`btn_toggle_drawer`).
* `formInput_section.py` : Formulaire de saisie fluide (`FormInputSection`) avec `QSizePolicy.Expanding` sur tous les champs, boutons d'aide compacts (34px) `QSizePolicy.Fixed`, étirements de colonnes équilibrés (`grid.setColumnStretch`), navigation Tab linéaire sans interruption (`Qt.NoFocus` sur les boutons secondaires), validation rapide par touche Entrée, et badges visuels distincts pour les calculs automatiques.
* `session_table_section.py` : Tableau de contrôle de la session courante (`SessionTableSection`) avec dimensionnement dynamique (`QHeaderView.Stretch` sur Article avec tooltips, `ResizeToContents` sur les colonnes fixes, et colonne d'actions dédiée de 102px sans débordement).
* `price_calculator.py` : Moteur de calcul financier autonome (`PriceCalculator`) déterminant le coût de revient total et le prix de vente conseillé selon le poids, le cours du métal, la façon et la marge bénéficiaire (fixe ou en pourcentage).
* `state_manager.py` : Gestionnaire de persistance (`StateManager`) assurant la sauvegarde et la restauration automatique des derniers paramètres saisis dans `runtime/inventory_last_state.json`.
