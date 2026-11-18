"""
TuniShop - Plateforme vue 360
Module db.py : connexion à SQL Server (authentification Windows, aucun mot de passe).

Auteure : Sarra Abdeljaouad

Les paramètres sont lus dans .streamlit/secrets.toml (non versionné) :
    [sql]
    serveur = "localhost"
    pilote  = ""            # vide = détection automatique (ODBC Driver 18 puis 17)
    base_dwh = "TuniShop_DWH"
    base_analytics = "TuniShop_ANALYTICS"

Règles :
    - Un moteur SQLAlchemy par base, créé une seule fois (st.cache_resource).
    - Les résultats de requêtes sont mis en cache 10 minutes (st.cache_data).
    - Toujours des requêtes avec paramètres (:nom), jamais de concaténation de texte.
"""
from __future__ import annotations

import urllib.parse

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

PILOTES_ACCEPTES = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]


def _config() -> dict:
    try:
        cfg = dict(st.secrets.get("sql", {}))
    except Exception:  # pas de secrets.toml : on prend les valeurs par défaut ci-dessous
        cfg = {}
    cfg.setdefault("serveur", "localhost")
    cfg.setdefault("base_dwh", "TuniShop_DWH")
    cfg.setdefault("base_analytics", "TuniShop_ANALYTICS")
    cfg.setdefault("pilote", "")
    return cfg


def pilote_odbc() -> str:
    """Renvoie le pilote ODBC à utiliser. Erreur claire s'il n'y en a aucun."""
    voulu = _config()["pilote"]
    import pyodbc                      # import ici : absent en mode démo (Streamlit Cloud)
    installes = pyodbc.drivers()
    if voulu:
        if voulu not in installes:
            raise RuntimeError(f"Pilote « {voulu} » introuvable. Pilotes installés : {installes}")
        return voulu
    for p in PILOTES_ACCEPTES:
        if p in installes:
            return p
    raise RuntimeError(f"Aucun pilote ODBC SQL Server trouvé. Pilotes installés : {installes}")


@st.cache_resource(show_spinner=False)
def moteur(base: str) -> Engine:
    """Moteur SQLAlchemy pour une base ('dwh' ou 'analytics')."""
    cfg = _config()
    nom_base = cfg["base_dwh"] if base == "dwh" else cfg["base_analytics"]
    chaine = (f"DRIVER={{{pilote_odbc()}}};SERVER={cfg['serveur']};DATABASE={nom_base};"
              "Trusted_Connection=yes;TrustServerCertificate=yes")
    return create_engine("mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(chaine),
                         pool_pre_ping=True)


@st.cache_data(ttl=600, show_spinner=False)
def lire(requete: str, base: str = "dwh", params: dict | None = None) -> pd.DataFrame:
    """Exécute une requête SELECT et renvoie un DataFrame. Mis en cache 10 minutes.
    En mode démo (src/demo.py), la même requête est exécutée par DuckDB sur les fichiers Parquet exportés."""
    from src import demo
    if demo.actif():
        return demo.lire(requete, params)
    with moteur(base).connect() as cn:
        return pd.read_sql(text(requete), cn, params=params or {})


def tester_connexion(base: str) -> dict:
    """Utilisé par la page de vérification : renvoie nom de base, version, nombre de vues par schéma."""
    with moteur(base).connect() as cn:
        info = cn.execute(text("SELECT DB_NAME() AS base, @@SERVERNAME AS serveur, "
                               "CAST(SERVERPROPERTY('Edition') AS NVARCHAR(100)) AS edition")).mappings().one()
        vues = pd.read_sql(text("SELECT s.name AS schema_nom, COUNT(*) AS nb_vues FROM sys.views v "
                                "JOIN sys.schemas s ON s.schema_id = v.schema_id GROUP BY s.name ORDER BY s.name"), cn)
    return {**dict(info), "vues": vues}
