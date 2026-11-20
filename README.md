# TuniShop · Plateforme vue 360 (Streamlit)

Auteure : Sarra Abdeljaouad · Étape 9 du projet TuniShop

> **Démo en ligne : https://tunishopsarraapps.streamlit.app**
>
> **Projet complet** (du staging à l'automatisation : DWH, cubes SSAS, Power BI, ML) : [tunishop-projet-data-bi](https://github.com/sarraabdeljaouad-ui/tunishop-projet-data-bi)
> 
> **Version HTML** (site statique, mêmes données) : [sarraabdeljaouad-ui.github.io/Tunishop-plateforme-360-web](https://sarraabdeljaouad-ui.github.io/Tunishop-plateforme-360-web/) · code : [sarraabdeljaouad-ui/Tunishop-plateforme-360-web](https://github.com/sarraabdeljaouad-ui/Tunishop-plateforme-360-web)

Taper un client, un produit, un fournisseur ou un numéro de commande (même avec des fautes) et voir tout ce
qui le concerne sur une seule fiche : indicateurs, historique, prédictions des modèles de machine learning
et analyse des avis clients.

**À propos des données.** TuniShop est une enseigne e-commerce tunisienne fictive. Toutes les données
(clients, commandes, livraisons, avis) ont été générées pour ce portfolio, puis traitées comme celles d'une
vraie entreprise : entrepôt SQL Server, contrôles qualité, modèles et text mining. Aucun nom ne correspond
à une personne réelle.

## Ce que fait la plateforme

| Page | Ce qu'on y trouve |
|---|---|
| Recherche | recherche floue sur 16 600 entités, ouverture directe d'un numéro CMD… |
| Accueil | chiffres globaux, prévision du CA, listes d'alertes (churn, ruptures, fournisseurs, colis) |
| Fiche Client | score de churn et ce qui pèse dedans, parcours RFM, commandes, avis |
| Fiche Produit | ventes, projection du stock et date de rupture, ventes perdues, produits achetés avec |
| Fiche Fournisseur | score /100 (ponctualité, complétude, qualité), délais réels contre annoncés |
| Fiche Commande | suivi, risque de retard prédit à l'expédition, retours et remboursements |
| Fiche Transporteur | taux de retard par année, colis en transit à risque, avis sur la livraison |
| Voix du client | thèmes et polarité des avis, vérification des avis par les faits |
| Modèles | performances, registre et suivi des modèles |

## Architecture

```
SQL Server (TuniShop_DWH, TuniShop_ANALYTICS)
   └─ vues app / pbi / ana  (calculs métier en SQL)
        └─ src/donnees.py   (seule porte vers les données, une fonction par bloc)
             └─ pages/      (affichage seulement)

Démo en ligne : mêmes vues exportées en Parquet (demo_data/), mêmes requêtes exécutées par DuckDB
```

```
app.py                  point d'entrée : menu et navigation (st.navigation, une adresse par fiche)
pages/                  10 pages (recherche, accueil, 5 fiches, voix du client, modèles, vérification)
src/donnees.py          requêtes SQL, cache
src/db.py               connexion SQL Server, ou bascule vers le mode démo
src/demo.py             mode démo : DuckDB sur Parquet, traduction T-SQL automatique (sqlglot)
src/recherche.py        recherche floue (rapidfuzz)
src/regles.py           règles métier (rupture, score fournisseur…)
src/ui.py, format.py    composants d'affichage, formats à la française
sql/                    scripts des vues app (01 à 06)
scripts/exporter_demo.py export des vues en Parquet
tests/                  70 tests (pages, recherche, règles, mode démo) + test de fumée sur la vraie base
```

## Recette

Recette menée du 07/12 au 11/12/2026 : 33 cas de test, 25 contrôles SQL, test de fumée 17/17 sur la base réelle
et 17/17 en mode démo. Documents : note de conception, cahier de recette, rapport de recette, PV, rapport de phase.

## Installation (une seule fois)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .streamlit\secrets.toml.exemple .streamlit\secrets.toml
```

## Lancer

```
.venv\Scripts\activate
pytest -v
streamlit run app.py
```

## Choix techniques

- **Calculs en SQL, affichage en Python.** Les KPI viennent des vues app (contrôles C1 à C7 du script 01) ;
  donnees.py filtre, trie et limite, sans calcul métier.
- **Une adresse par fiche** (st.navigation, st.query_params) : chaque fiche se partage par un lien.
- **Recherche floue : score mixte** (moyenne token_set_ratio + token_sort_ratio), calculé sur le nom seul
  et sur nom + détail, en gardant le meilleur. Sur 13 recherches types avec fautes, WRatio plaçait la bonne
  entité en tête 5 fois sur 10 ; le score mixte, 13 fois sur 13. Seuil : 60/100. Temps : environ 40 ms
  pour 16 600 entités.
- **Pas de recherche floue pour les doublons clients.** Les 150 doublons injectés (règle DQ-37) se trouvent
  tous par simple égalité (nom normalisé + 8 derniers chiffres du téléphone), sans fausse alerte.

## Test de fumée sur la vraie base

Les tests habituels (`pytest -q`) remplacent la base par des données fictives : ils vérifient l'affichage,
pas le SQL. Le test de fumée ouvre chaque page sur la vraie base SQL Server (13 cas, 3 recherches, les filtres
de Voix du client) et écrit `tests/rapport_fumee.csv` (page, cas, identifiant, durée, statut).

```powershell
$env:TUNISHOP_BASE_REELLE = "1"
python -m pytest tests/test_fumee.py -v
Remove-Item Env:TUNISHOP_BASE_REELLE
```

## Mode démonstration (sans SQL Server)

L'application peut tourner sans SQL Server, par exemple en ligne sur Streamlit Community Cloud. Les vues et tables
qu'elle lit sont exportées en fichiers Parquet (dossier `demo_data/`) ; en mode démo, les mêmes requêtes SQL sont
exécutées par DuckDB sur ces fichiers, après traduction automatique du T-SQL (sqlglot). Code : `src/demo.py`.

1. Exporter (sur le poste qui a SQL Server, `.venv` activé) : `python scripts/exporter_demo.py`
2. Vérifier en mode démo, avec le test de fumée :
   ```powershell
   $env:TUNISHOP_MODE = "demo"
   $env:TUNISHOP_BASE_REELLE = "1"
   python -m pytest tests/test_fumee.py -v
   Remove-Item Env:TUNISHOP_BASE_REELLE
   ```
3. Voir l'application en mode démo : `streamlit run app.py` (avec `TUNISHOP_MODE=demo`), puis
   `Remove-Item Env:TUNISHOP_MODE` pour revenir au mode direct.

Choix du mode : la variable `TUNISHOP_MODE` (`demo` ou `direct`) décide si elle existe ; sinon, l'application passe
en mode démo quand `secrets.toml` n'a pas de section `[sql]` et que `demo_data/` existe (cas de Streamlit Cloud).
