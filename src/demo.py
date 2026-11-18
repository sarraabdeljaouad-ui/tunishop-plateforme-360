"""
TuniShop - Plateforme vue 360
src/demo.py : mode démonstration, sans SQL Server.

Les vues et tables lues par l'application sont exportées en fichiers Parquet (scripts/exporter_demo.py,
lancé sur le poste qui a SQL Server). En mode démo, les MÊMES requêtes SQL sont exécutées par DuckDB
sur ces fichiers, après traduction automatique du T-SQL (sqlglot) : rien n'est réécrit à la main.

Le mode démo s'active :
  - si la variable d'environnement TUNISHOP_MODE vaut « demo » ;
  - ou s'il n'y a pas de section [sql] dans .streamlit/secrets.toml et que le dossier demo_data/ existe
    (cas de Streamlit Community Cloud).

Auteure : Sarra Abdeljaouad
"""
import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

DOSSIER = Path(__file__).resolve().parents[1] / "demo_data"
MANIFESTE = DOSSIER / "manifeste.json"

# Objets lus par l'application (liste tenue à jour par tests/test_demo.py, qui la compare au code)
OBJETS = [
    "TuniShop_DWH.bi.v_dim_client", "TuniShop_DWH.bi.v_dim_date", "TuniShop_DWH.bi.v_dim_geographie",
    "TuniShop_DWH.bi.v_dim_produit", "TuniShop_DWH.bi.v_dim_transporteur", "TuniShop_DWH.bi.v_fact_avis",
    "TuniShop_DWH.bi.v_fact_livraisons",
    "ana.dm02_profil_clusters", "ana.ml03_importance", "ana.ml_metriques_retard", "ana.ml_pred_ventes_2026",
    "ana.tm_avis", "ana.tm_avis_themes",
    "app.v_client_annee", "app.v_client_churn_test", "app.v_client_commandes", "app.v_client_experience",
    "app.v_client_habitudes", "app.v_client_identite", "app.v_client_kpi", "app.v_client_produits",
    "app.v_client_remboursements", "app.v_client_rfm", "app.v_client_ventes_mois", "app.v_commande_fiche",
    "app.v_commande_lignes", "app.v_commande_livraison", "app.v_fournisseur_achats_mois", "app.v_fournisseur_annee",
    "app.v_fournisseur_fiche", "app.v_index_recherche", "app.v_livraison_detail", "app.v_produit_annee",
    "app.v_produit_identite", "app.v_produit_kpi", "app.v_produit_stock_mois", "app.v_produit_ventes_mois",
    "ctl.v_derniere_execution",
    "pbi.v_dm_regles", "pbi.v_eda_vue_ensemble", "pbi.v_ml_modeles", "pbi.v_ml_registre", "pbi.v_ml_retard",
    "pbi.v_ml_scores_churn", "pbi.v_ml_scores_demande", "pbi.v_ml_scores_retard", "pbi.v_ml_suivi", "pbi.v_ml_ventes",
    "pbi.v_tm_avis", "pbi.v_tm_avis_themes", "pbi.v_tm_produits", "pbi.v_tm_verification_faits",
]


def fichier(objet: str) -> Path:
    return DOSSIER / f"{objet}.parquet"


def _connexion_sql_configuree() -> bool:
    """Vrai si .streamlit/secrets.toml contient une section [sql] (cas du poste de développement)."""
    try:
        return "sql" in st.secrets
    except Exception:                        # pas de secrets.toml du tout
        return False


def actif() -> bool:
    mode = os.environ.get("TUNISHOP_MODE", "").lower()
    if mode in ("demo", "direct"):
        return mode == "demo"
    return not _connexion_sql_configuree() and DOSSIER.exists()


def manifeste() -> dict:
    return json.loads(MANIFESTE.read_text(encoding="utf-8")) if MANIFESTE.exists() else {}


@st.cache_resource(show_spinner=False)
def connexion():
    """Base DuckDB en mémoire : une vue par fichier Parquet, sous le même nom qu'en SQL Server
    (catalogue TuniShop_DWH pour les vues bi du DWH, schémas app, pbi, ana et ctl pour TuniShop_ANALYTICS)."""
    import duckdb
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS TuniShop_DWH")
    con.execute("CREATE SCHEMA IF NOT EXISTS TuniShop_DWH.bi")
    for schema in ("app", "pbi", "ana", "ctl"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for objet in OBJETS:
        f = fichier(objet)
        if f.exists():
            chemin = str(f).replace("'", "''")
            con.execute(f"CREATE VIEW {objet} AS SELECT * FROM read_parquet('{chemin}')")
    return con


_N_TEXTE = re.compile(r"\bN'")                      # N'négatif' : préfixe T-SQL inconnu de DuckDB
_REEL = re.compile(r"\bAS REAL\)", re.IGNORECASE)    # float T-SQL = double précision


def traduire(requete: str) -> str:
    """T-SQL de l'application → SQL DuckDB. Les paramètres :x deviennent $x (liés par DuckDB, jamais collés au texte)."""
    import sqlglot
    from sqlglot import exp
    arbre = sqlglot.parse_one(requete, read="tsql")
    sql = arbre.sql(dialect="duckdb")
    # OUTER APPLY devient « LEFT JOIN LATERAL (…) AS x » : DuckDB exige en plus « ON TRUE »
    for jointure in arbre.find_all(exp.Join):
        lat = jointure.this
        if isinstance(lat, exp.Lateral) and lat.args.get("cross_apply") is False and not jointure.args.get("on"):
            morceau = jointure.sql(dialect="duckdb")
            sql = sql.replace(morceau, morceau + " ON TRUE", 1)
    sql = _N_TEXTE.sub("'", sql)
    return _REEL.sub("AS DOUBLE)", sql)


def comme_sql_server(df: pd.DataFrame) -> pd.DataFrame:
    """Rend les types identiques à ceux lus depuis SQL Server (pyodbc + pandas).
    DuckDB renvoie des types « nullables » (boolean, Int32) dont la valeur vide pd.NA plante un simple
    « if x == 1 » (« boolean value of NA is ambiguous »). SQL Server renvoie None (bit) ou NaN (entier)."""
    for col in df.columns:
        s = df[col]
        if isinstance(s.dtype, pd.BooleanDtype):
            df[col] = s.astype(object).where(s.notna(), None)
        elif pd.api.types.is_extension_array_dtype(s.dtype) and pd.api.types.is_numeric_dtype(s.dtype):
            df[col] = s.astype("float64") if s.isna().any() else s.to_numpy(dtype=s.dtype.numpy_dtype)
    return df


def lire(requete: str, params: dict | None = None) -> pd.DataFrame:
    con = connexion().cursor()
    sql = traduire(requete)
    utiles = {k: v for k, v in (params or {}).items() if f"${k}" in sql}
    return comme_sql_server(con.execute(sql, utiles).df())
