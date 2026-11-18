"""Test de fumée : chaque page de la plateforme ouverte sur la VRAIE base SQL Server.

Les autres tests remplacent la base par des données fictives : ils vérifient l'affichage, pas le SQL
envoyé au serveur. Celui-ci exécute toutes les requêtes pour de vrai (c'est lui qui aurait attrapé
l'erreur « agrégat sur sous-requête » de la fiche Transporteur).

Il ne tourne que sur demande, avec SQL Server démarré :
    PowerShell :  $env:TUNISHOP_BASE_REELLE = "1" ; python -m pytest tests/test_fumee.py -v
    puis       :  Remove-Item Env:TUNISHOP_BASE_REELLE

Résultat : un rapport tests/rapport_fumee.csv (page, cas, identifiant, durée, statut), preuve pour la recette.
"""
import csv
import os
import time
import tomllib
from datetime import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RACINE = Path(__file__).resolve().parents[1]
APP = str(RACINE / "app.py")
DELAI = 120                      # secondes par page : le premier chargement remplit les caches
RAPPORT = RACINE / "tests" / "rapport_fumee.csv"

pytestmark = pytest.mark.skipif(os.environ.get("TUNISHOP_BASE_REELLE") != "1",
                                reason="test sur la vraie base : définir TUNISHOP_BASE_REELLE=1")
RESULTATS: list[dict] = []


@pytest.fixture(scope="module", autouse=True)
def bon_python():
    """Le test doit tourner avec le Python du .venv de la plateforme (mêmes versions que l'appli).
    Avec le Python global de Windows, pandas ne reconnaît pas la connexion SQLAlchemy
    (« Query must be a string unless using sqlalchemy ») et toutes les pages échouent."""
    import sys
    if ".venv" not in sys.executable:
        pytest.exit(f"Test lancé avec {sys.executable}, hors du .venv. Active-le (.venv\\Scripts\\activate), "
                    "vérifie que « (.venv) » s'affiche devant l'invite, puis relance.", returncode=1)


def _secrets() -> dict:
    f = RACINE / ".streamlit" / "secrets.toml"
    return tomllib.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _requete(sql: str):
    """Lecture directe dans TuniShop_ANALYTICS, hors Streamlit, pour choisir des identifiants réels."""
    os.chdir(RACINE)                                   # src.db lit .streamlit/secrets.toml depuis ce dossier
    from src.db import lire
    return lire(sql, base="analytics")


def _message_court(err: Exception) -> str:
    """Dernière ligne utile d'une erreur pyodbc / SQLAlchemy (le texte de SQL Server)."""
    texte = str(getattr(err, "orig", err))
    return texte.split("[SQL Server]")[-1].split("(SQLExecDirectW)")[0].strip()[:300]


@pytest.fixture(scope="module")
def ids() -> dict:
    """Un identifiant réel par cas à tester : les cas « riches » et les cas limites.
    En cas d'échec : un message d'une ligne par requête (nom du cas + message de SQL Server)."""
    try:
        _requete("SELECT 1 AS ok")
    except Exception as err:                                           # pas de connexion : inutile d'aller plus loin
        pytest.fail(f"Connexion à TuniShop_ANALYTICS impossible : {_message_court(err)}", pytrace=False)
    requetes = {
        "client_risque": ("""SELECT TOP (1) client_id FROM pbi.v_ml_scores_churn
                               WHERE decile_risque = 1 AND date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_churn)
                               ORDER BY proba_churn * montant_reconnu_ttc DESC"""),
        "client_sans_score": ("SELECT TOP (1) client_id FROM app.v_client_identite WHERE proba_churn IS NULL ORDER BY client_id"),
        "produit_rupture": ("""SELECT TOP (1) produit_id FROM pbi.v_ml_scores_demande
                                 WHERE rupture_sans_reappro = 1 ORDER BY mois, produit_id"""),
        "produit_top": ("SELECT TOP (1) produit_id FROM app.v_produit_annee WHERE annee = 2025 ORDER BY ca_ttc DESC"),
        "fournisseur_alerte": ("SELECT TOP (1) fournisseur_id FROM app.v_fournisseur_fiche ORDER BY ecart_fiabilite"),
        "commande_transit": ("""SELECT TOP (1) commande_id FROM pbi.v_ml_scores_retard
                                  WHERE date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_retard)
                                  ORDER BY proba_retard DESC"""),
        "commande_retard_retour": ("""SELECT TOP (1) commande_id FROM app.v_commande_fiche
                                        WHERE retard_j > 0 AND montant_rembourse_ttc > 0 ORDER BY date_commande DESC"""),
        "commande_annulee": ("SELECT TOP (1) commande_id FROM app.v_commande_fiche WHERE date_annulation > '1901-01-01' "
                               "ORDER BY date_commande DESC"),
        "transporteur": ("SELECT TOP (1) transporteur FROM app.v_livraison_detail WHERE annee = 2025 "
                           "GROUP BY transporteur ORDER BY AVG(CAST(en_retard AS float)) DESC"),
    }
    trouves, echecs = {}, []
    for cas, sql in requetes.items():
        try:
            t = _requete(sql)
            if t.empty:
                echecs.append(f"{cas} : aucune ligne")
            else:
                trouves[cas] = t.iat[0, 0]
        except Exception as err:
            echecs.append(f"{cas} : {_message_court(err)}")
    if echecs:
        pytest.fail("Identifiants introuvables :\n  - " + "\n  - ".join(echecs), pytrace=False)
    return trouves


def ouvrir(page: str, **query) -> tuple[AppTest, float]:
    at = AppTest.from_file(APP, default_timeout=DELAI)
    for section, valeurs in _secrets().items():
        at.secrets[section] = valeurs
    at.switch_page(page)
    for k, v in query.items():
        at.query_params[k] = v
    t0 = time.perf_counter()
    at.run()
    return at, time.perf_counter() - t0


def verifier(page: str, cas: str, at: AppTest, duree: float, ident: str = "") -> None:
    erreurs = [e.value for e in at.error] + [str(x.value) for x in at.exception]
    RESULTATS.append({"page": page, "cas": cas, "identifiant": ident, "duree_s": round(duree, 2),
                      "statut": "OK" if not erreurs else "ERREUR", "detail": " | ".join(erreurs)[:300]})
    assert not at.exception, f"{page} ({cas}) : {at.exception[0].value}"
    assert not at.error, f"{page} ({cas}) : {at.error[0].value}"


CAS = [  # (page, cas, clé de l'identifiant dans ids ou None)
    ("pages/accueil.py", "accueil", None),
    ("pages/client.py", "client à risque", "client_risque"),
    ("pages/client.py", "client sans score", "client_sans_score"),
    ("pages/produit.py", "produit en rupture", "produit_rupture"),
    ("pages/produit.py", "meilleur produit 2025", "produit_top"),
    ("pages/fournisseur.py", "fournisseur en alerte", "fournisseur_alerte"),
    ("pages/commande.py", "colis en transit", "commande_transit"),
    ("pages/commande.py", "retard et retour", "commande_retard_retour"),
    ("pages/commande.py", "commande annulée", "commande_annulee"),
    ("pages/transporteur.py", "transporteur le plus en retard", "transporteur"),
    ("pages/voix_client.py", "toutes catégories", None),
    ("pages/modeles.py", "registre et suivi", None),
    ("pages/verification.py", "vérification", None),
]


@pytest.mark.parametrize("page, cas, cle", CAS, ids=[f"{p.split('/')[-1][:-3]}-{c}" for p, c, _ in CAS])
def test_page_sur_la_vraie_base(ids, page, cas, cle):
    ident = str(ids[cle]) if cle else ""
    at, duree = ouvrir(page, **({"id": ident} if ident else {}))
    verifier(page, cas, at, duree, ident)


@pytest.mark.parametrize("saisie", ["nexra", "carthgo", "riadh belhaj"])
def test_recherche_floue(saisie):
    at, duree = ouvrir("pages/recherche.py", q=saisie)
    verifier("pages/recherche.py", f"recherche « {saisie} »", at, duree, saisie)
    assert any("Ouvrir · " in m.value for m in at.markdown), f"aucun résultat pour « {saisie} »"


def test_filtres_voix_du_client():
    at, duree = ouvrir("pages/voix_client.py")
    at.selectbox[1].set_value("2025").run()
    at.selectbox[0].set_value(at.selectbox[0].options[1]).run()
    verifier("pages/voix_client.py", "filtres catégorie et 2025", at, duree)


def teardown_module(_):
    """Écrit le rapport, même si un test a échoué."""
    if not RESULTATS:
        return
    with open(RAPPORT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["date", *RESULTATS[0].keys()], delimiter=";")
        w.writeheader()
        quand = datetime.now().strftime("%d/%m/%Y %H:%M")
        for r in RESULTATS:
            w.writerow({"date": quand, **r})
