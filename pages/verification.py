"""
TuniShop - Plateforme vue 360
Page Vérification : diagnostic de l'environnement (librairies, pilote ODBC, bases, index de recherche).
Utile après une installation ou une mise à jour.

Auteure : Sarra Abdeljaouad
"""
import sys

import pandas as pd
import streamlit as st

st.title("Vérification de l'environnement")

# 1. Python et librairies
st.subheader("1. Python et librairies")
import pandas, plotly, rapidfuzz, sqlalchemy  # noqa: E401,E402
from src import demo  # noqa: E402

versions = {"Python": sys.version.split()[0], "streamlit": st.__version__, "pandas": pandas.__version__,
            "rapidfuzz": rapidfuzz.__version__, "sqlalchemy": sqlalchemy.__version__, "plotly": plotly.__version__}
try:
    import pyodbc  # noqa: E402
    versions["pyodbc"] = pyodbc.version
except ImportError:
    versions["pyodbc"] = "absent (normal en mode démo)"
if demo.actif():
    import duckdb  # noqa: E402
    versions["duckdb"] = duckdb.__version__
st.write(versions)

if demo.actif():
    # 2. Mode démonstration : état de l'export
    st.subheader("2. Mode démonstration")
    m = demo.manifeste()
    st.info(f"Données lues dans des fichiers Parquet exportés le {m.get('date_export', '—')} "
            f"depuis {m.get('serveur', '—')} ; requêtes exécutées par DuckDB.")
    lignes = m.get("objets", {})
    etat = pd.DataFrame([{"objet": o, "lignes": lignes.get(o), "fichier présent": demo.fichier(o).exists()}
                         for o in demo.OBJETS])
    manquants = etat[~etat["fichier présent"]]
    (st.error if len(manquants) else st.success)(f"{len(etat) - len(manquants)} objets sur {len(etat)} présents")
    st.dataframe(etat, hide_index=True)
else:
    # 2. Pilote ODBC
    st.subheader("2. Pilote ODBC")
    from src.db import pilote_odbc, tester_connexion  # noqa: E402
    try:
        st.success(f"Pilote utilisé : {pilote_odbc()}")
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    # 3. Connexion aux deux bases
    st.subheader("3. Connexion aux bases")
    for base in ["dwh", "analytics"]:
        try:
            r = tester_connexion(base)
            st.success(f"{r['base']} sur {r['serveur']} ({r['edition']})")
            st.dataframe(r["vues"], hide_index=True)
        except Exception as e:  # on affiche l'erreur telle quelle pour le diagnostic
            st.error(f"Connexion « {base} » impossible : {e}")

# 4. Index de recherche
st.subheader("4. Index de recherche")
try:
    from src import donnees  # noqa: E402
    idx = donnees.index_recherche()
    st.success(f"{len(idx)} entités indexées")
    st.dataframe(idx.groupby("type").size().rename("entités").reset_index(), hide_index=True)
except Exception as e:
    st.error(f"Index indisponible (as-tu exécuté sql/01_vues_plateforme.sql ?) : {e}")
