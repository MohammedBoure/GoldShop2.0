# Rapid Entry & Batch Inventory Module (`ui/widgets/inventory/tabs_batches`)

Ce sous-module gère l'interface de saisie rapide d'articles d'inventaire et le suivi en direct de la session d'ajout pour les bijouteries. Il adopte une architecture scindée horizontalement (Side-by-Side) éliminant tout défilement vertical sur les écrans de caisse et portables (1024×768 / 1366×768 jusqu'à 2K).

---

## Fichiers du module :

* `__init__.py` : Point d'entrée du package exportant le widget principal `InventoryFormTab`.
* `tabs_batches.py` : Widget racine (`InventoryFormTab`) assemblant le panneau de gauche (formulaire rapide + barre d'actions 44px) et le panneau de droite (tableau de session) via un `QSplitter` horizontal (62% / 38%).
* `formInput_section.py` : Formulaire de saisie ultra-rapide (`FormInputSection`) structuré en sous-grille dense à 3 colonnes avec micro-labels, hauteur d'entrée 36px, navigation Tab stricte sans interruption (`Qt.NoFocus` sur les boutons secondaires), validation rapide par touche Entrée, et badges visuels distincts pour les calculs automatiques (Coût Total Achat et Prix de Vente).
* `session_table_section.py` : Tableau de contrôle de la session courante (`SessionTableSection`) avec hauteur de ligne compacte (36px), bandeau de statistiques en temps réel (poids total, nombre d'articles), bouton de nouvelle série et actions rapides par ligne (impression d'étiquette, modification, suppression).
* `price_calculator.py` : Moteur de calcul financier autonome (`PriceCalculator`) déterminant le coût de revient total et le prix de vente conseillé selon le poids, le cours du métal, la façon et la marge bénéficiaire (fixe ou en pourcentage).
* `state_manager.py` : Gestionnaire de persistance (`StateManager`) assurant la sauvegarde et la restauration automatique des derniers paramètres saisis dans `runtime/inventory_last_state.json`.
