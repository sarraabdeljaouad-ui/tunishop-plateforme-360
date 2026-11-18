"""Tests du module recherche.py (recherche floue). Lancer : pytest -v
Les données de test sont un extrait fixe du dataset TuniShop (tests/donnees/)."""
from pathlib import Path

import pandas as pd
import pytest

from src.recherche import construire_index, rechercher

DOSSIER = Path(__file__).parent / "donnees"


@pytest.fixture(scope="module")
def index():
    lire = lambda n: pd.read_csv(DOSSIER / n, dtype=str)
    return construire_index(lire("clients_test.csv"), lire("produits_test.csv"), lire("fournisseurs_test.csv"))


# saisie avec fautes -> début du libellé attendu en 1re position
CAS = [
    ("yasmin mansouri", "Yasmine Mansouri"),          # lettre manquante
    ("riadh belhaj", "Riadh Belhadj"),                # orthographe proche
    ("riadh belhaj tabarka", "Riadh Belhadj"),        # avec la ville
    ("tabarka belhadj", "Riadh Belhadj"),             # ordre inversé
    ("atlas distrib", "Atlas Distribution"),          # mot tronqué
    ("carthage import", "Carthage Import-Export"),
    ("nexra evasion 15", "Smartphone Nexora Évasion 15"),
    ("smartphone volta mini", "Smartphone Volta Mobile Mini"),
    ("lave vaiselle electo", "Lave-vaisselle Electo"),
    ("chemise barbary 58", "Chemise Barbary Confort 58"),
    ("sfar services", "Sfar Services"),
]


@pytest.mark.parametrize("saisie,attendu", CAS)
def test_recherche_floue_trouve_en_premier(index, saisie, attendu):
    res = rechercher(saisie, index)
    assert len(res) > 0
    assert res.loc[0, "libelle"].startswith(attendu)


def test_ville_avec_accent(index):
    res = rechercher("lahmar kelibia", index)
    # Les premiers résultats sont les Lahmar de Kélibia (le dataset en compte plusieurs)
    nb = ((res["detail"] == "Kélibia") & res["libelle"].str.endswith("Lahmar")).sum()
    assert nb >= 2
    assert (res.head(nb)["detail"] == "Kélibia").all()


@pytest.mark.parametrize("code,id_attendu", [
    ("CLI004074", "CLI004074"), ("prd0001", "PRD0001"), (" FRN002 ", "FRN002"), ("TS-01-00002", "PRD0002"),
])
def test_identifiant_exact(index, code, id_attendu):
    res = rechercher(code, index)
    assert list(res["id"]) == [id_attendu]
    assert res.loc[0, "score"] == 100


@pytest.mark.parametrize("saisie", ["", "   ", "a", "xqwz", "pomme banane", "zzzz yyyy"])
def test_saisie_sans_resultat(index, saisie):
    assert rechercher(saisie, index).empty


def test_filtre_par_type(index):
    res = rechercher("carthage", index, types=["Fournisseur"])
    assert set(res["type"]) == {"Fournisseur"}


def test_index_depuis_la_vue_sql():
    """La vue app.v_index_recherche donne le même index que construire_index."""
    from src.recherche import index_depuis_vue
    vue = pd.DataFrame({"type_entite": ["Client", "Produit", "Fournisseur"],
                        "id": ["CLI004074", "PRD0001", "FRN002"],
                        "libelle": ["Riadh Belhadj", "Smartphone Nexora Évasion 15", "Carthage Import-Export"],
                        "detail": ["Tabarka", "Nexora", "Tunisie"], "sku": [None, "TS-01-00001", None]})
    idx = index_depuis_vue(vue)
    assert list(idx.columns) == ["type", "id", "libelle", "detail", "cle_nom", "cle", "sku"]
    assert rechercher("riadh belhaj tabarka", idx).loc[0, "id"] == "CLI004074"
    assert list(rechercher("TS-01-00001", idx)["id"]) == ["PRD0001"]


@pytest.mark.parametrize("saisie, mot", [("nexra", "Nexora"), ("carthgo", "Carthago")])
def test_un_seul_mot_mal_ecrit_trouve_les_produits(index, saisie, mot):
    """Un seul mot d'un long nom, avec une faute : comparaison mot à mot (maquette 00)."""
    res = rechercher(saisie, index)
    assert len(res) > 0 and res["libelle"].str.contains(mot).all()
