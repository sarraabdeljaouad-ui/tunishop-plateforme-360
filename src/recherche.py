"""
TuniShop - Plateforme vue 360
Module recherche.py : recherche floue de clients, produits et fournisseurs (proposition 1).

Auteure : Sarra Abdeljaouad

Principe :
    - Chaque entité reçoit une "clé de recherche" normalisée (minuscules, sans accents,
      sans ponctuation) : prénom + nom + ville pour un client, nom + marque + SKU pour un produit...
    - La saisie de l'utilisateur est normalisée de la même façon.
    - rapidfuzz compare la saisie à toutes les clés (score_mixte) et renvoie les plus proches.
      Une faute de frappe ("belhaj" pour "Belhadj", "kelibia" pour "Kélibia") reste trouvée.
    - Un identifiant exact (CLI000123, PRD0042, FRN007, TS-01-00001) ouvre directement la fiche.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

SEUIL_PAR_DEFAUT = 60        # score minimal sur 100 ; réglé par tests (voir tests/test_recherche.py)
NB_RESULTATS_PAR_DEFAUT = 10
SEUIL_MOT = 75             # mot à mot : score minimal de chaque mot saisi (« pomme » ≠ « homme » + « banane »)

_RE_ID = re.compile(r"^\s*(CLI\d+|PRD\d+|FRN\d+|TS-\d{2}-\d{5})\s*$", re.IGNORECASE)
_RE_COMMANDE = re.compile(r"^\s*(CMD\d+)\s*$", re.IGNORECASE)   # commandes : hors index, fiche directe


def scores_mixtes(saisie: str, cles: pd.Series) -> np.ndarray:
    """Score de 0 à 100 entre la saisie et chaque clé : moyenne de deux scores rapidfuzz.
    - token_set_ratio : tolère les mots en plus ("riadh belhaj" trouve "riadh belhadj") ;
    - token_sort_ratio : pénalise l'écart de longueur, pour départager les ex aequo.
    Choisi après comparaison sur 10 recherches types : WRatio en classait 5 sur 10 en tête,
    ce score les classe 10 sur 10. Calcul vectorisé (process.cdist), en C, donc rapide."""
    liste = cles.tolist()
    a = process.cdist([saisie], liste, scorer=fuzz.token_set_ratio, workers=-1)[0]
    b = process.cdist([saisie], liste, scorer=fuzz.token_sort_ratio, workers=-1)[0]
    return (0.5 * a + 0.5 * b).astype(float)


def scores_mot_a_mot(saisie: str, cles: pd.Series) -> np.ndarray:
    """Score de 0 à 100 mot par mot : chaque mot saisi prend son meilleur score (fuzz.ratio) parmi
    les mots de la clé, puis on fait la moyenne. Sert quand on tape un seul mot d'un long nom :
    « nexra » contre « smartphone nexora evasion 15 » vaut 91 ici, mais moins de 60 en comparaison globale.
    Les scores sont calculés une fois par mot distinct de l'index (process.cdist), pas par clé."""
    mots = [m for m in saisie.split() if len(m) >= 2]
    if not mots:
        return np.zeros(len(cles))
    listes = cles.str.split()
    vocab = sorted({m for l in listes for m in l})
    if not vocab:
        return np.zeros(len(cles))
    matrice = process.cdist(mots, vocab, scorer=fuzz.ratio, workers=-1)          # mots saisis x vocabulaire
    meilleur = [dict(zip(vocab, ligne)) for ligne in matrice]

    def note(l):
        par_mot = [max((s.get(w, 0) for w in l), default=0) for s in meilleur]
        return float(np.mean(par_mot)) if l and min(par_mot) >= SEUIL_MOT else 0.0   # chaque mot doit trouver un écho

    return np.array([note(l) for l in listes], dtype=float)


def normaliser(texte) -> str:
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    if texte is None or (isinstance(texte, float) and pd.isna(texte)):
        return ""
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _joindre(*colonnes: pd.Series) -> pd.Series:
    """Concatène des colonnes texte en ignorant les valeurs vides."""
    df = pd.concat([c.fillna("").astype(str) for c in colonnes], axis=1)
    return df.apply(lambda r: " ".join(v for v in r if v.strip()), axis=1)


def construire_index(clients: pd.DataFrame | None = None,
                     produits: pd.DataFrame | None = None,
                     fournisseurs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Construit l'index de recherche. Colonnes attendues (adaptables à tes vues bi) :
        clients      : client_id, prenom, nom, raison_sociale, ville
        produits     : produit_id, sku, nom_produit, marque
        fournisseurs : fournisseur_id, nom_fournisseur, pays
    Renvoie : type, id, libelle et detail (affichés), cle_nom et cle (normalisées, pour la recherche).
    cle_nom = le nom seul ; cle = le nom + ville, marque ou pays. On garde le meilleur des deux scores :
    "riadh belhaj" vise le nom, "lahmar kelibia" vise nom + ville."""
    morceaux = []

    if clients is not None and len(clients):
        c = clients
        nom_personne = _joindre(c["prenom"], c["nom"])
        libelle = c["raison_sociale"].where(c["raison_sociale"].notna() & (c["raison_sociale"] != ""), nom_personne)
        morceaux.append(pd.DataFrame({
            "type": "Client", "id": c["client_id"], "libelle": libelle,
            "detail": c["ville"].fillna(""),
            "cle_nom": libelle.map(normaliser),
            "cle": _joindre(libelle, c["ville"]).map(normaliser),
        }))

    if produits is not None and len(produits):
        p = produits
        morceaux.append(pd.DataFrame({
            "type": "Produit", "id": p["produit_id"], "libelle": p["nom_produit"],
            "detail": _joindre(p["marque"], p["sku"]),
            "cle_nom": p["nom_produit"].map(normaliser),
            "cle": _joindre(p["nom_produit"], p["marque"]).map(normaliser),
        }))

    if fournisseurs is not None and len(fournisseurs):
        f = fournisseurs
        morceaux.append(pd.DataFrame({
            "type": "Fournisseur", "id": f["fournisseur_id"], "libelle": f["nom_fournisseur"],
            "detail": f["pays"].fillna(""),
            "cle_nom": f["nom_fournisseur"].map(normaliser),
            "cle": _joindre(f["nom_fournisseur"], f["pays"]).map(normaliser),
        }))

    index = pd.concat(morceaux, ignore_index=True) if morceaux else pd.DataFrame(
        columns=["type", "id", "libelle", "detail", "cle_nom", "cle"])
    # Le SKU sert à la recherche exacte par identifiant
    if produits is not None and len(produits):
        index["sku"] = index["id"].map(dict(zip(produits["produit_id"], produits["sku"])))
    return index


def index_depuis_vue(vue: pd.DataFrame) -> pd.DataFrame:
    """Index de recherche à partir de la vue SQL app.v_index_recherche
    (colonnes type_entite, id, libelle, detail, sku). Même structure que construire_index :
    detail = ville (client), marque (produit) ou pays (fournisseur)."""
    v = vue.rename(columns={"type_entite": "type"}).copy()
    v["detail"] = v["detail"].fillna("")
    v["cle_nom"] = v["libelle"].map(normaliser)
    v["cle"] = _joindre(v["libelle"], v["detail"]).map(normaliser)
    if "sku" not in v:
        v["sku"] = None
    return v[["type", "id", "libelle", "detail", "cle_nom", "cle", "sku"]].reset_index(drop=True)


def rechercher(saisie: str, index: pd.DataFrame,
               types: list[str] | None = None,
               seuil: int = SEUIL_PAR_DEFAUT,
               limite: int = NB_RESULTATS_PAR_DEFAUT) -> pd.DataFrame:
    """Renvoie les entités les plus proches de la saisie, triées par score décroissant.
    types : filtre facultatif, ex. ["Client"] ou ["Produit", "Fournisseur"]."""
    vide = index.iloc[0:0].assign(score=pd.Series(dtype=float))
    if not saisie or not saisie.strip():
        return vide

    base = index if not types else index[index["type"].isin(types)]

    # 1. Identifiant exact : pas de flou, on ouvre directement la fiche
    m = _RE_ID.match(saisie)
    if m:
        code = m.group(1).upper()
        exact = base[(base["id"].str.upper() == code) |
                     (base.get("sku", pd.Series(index=base.index, dtype=str)).fillna("").str.upper() == code)]
        return exact.assign(score=100.0).reset_index(drop=True)

    # 2. Recherche floue
    requete = normaliser(saisie)
    if len(requete) < 2:
        return vide
    global_ = np.maximum(scores_mixtes(requete, base["cle_nom"]), scores_mixtes(requete, base["cle"]))
    # mot à mot, légèrement pénalisé : à égalité, la comparaison du nom entier passe devant
    score = np.maximum(global_, 0.95 * scores_mot_a_mot(requete, base["cle_nom"]))
    garder = np.where(score >= seuil)[0]
    if len(garder) == 0:
        return vide
    ordre = garder[np.argsort(-score[garder], kind="stable")][:limite]
    lignes, scores = base.index[ordre], score[ordre]
    return base.loc[lignes].assign(score=scores.round(1)).reset_index(drop=True)


def commande_exacte(saisie: str) -> str | None:
    """Numéro de commande saisi tel quel (CMD0047890) : renvoyé en majuscules, sinon None."""
    m = _RE_COMMANDE.match(saisie or "")
    return m.group(1).upper() if m else None


def vocabulaire(index: pd.DataFrame) -> list[str]:
    """Mots distincts des noms indexés (normalisés, 3 lettres et plus), pour « Vouliez-vous dire ».
    Les noms de clients sont exclus : la suggestion ne doit pas souffler le nom d'une personne."""
    mots = index.loc[index["type"] != "Client", "cle_nom"].str.split().explode().dropna()
    return sorted({m for m in mots if len(m) >= 3 and not m.isdigit()})


def suggestion(saisie: str, vocab: list[str], seuil: int = 80) -> str | None:
    """Remplace chaque mot inconnu par le mot connu le plus proche ; None si rien ne change."""
    mots = normaliser(saisie).split()
    if not mots or not vocab:
        return None
    connus = set(vocab)
    sortie = []
    for m in mots:
        if m in connus or len(m) < 3 or m.isdigit():
            sortie.append(m)
            continue
        meilleur = process.extractOne(m, vocab, scorer=fuzz.ratio, score_cutoff=seuil)
        sortie.append(meilleur[0] if meilleur else m)
    propose = " ".join(sortie)
    return propose if propose != " ".join(mots) else None


def surligner(libelle: str, saisie: str, seuil: int = 75) -> str:
    """HTML du libellé où les mots proches d'un mot saisi sont surlignés (<mark>)."""
    import html as _html
    cibles = [m for m in normaliser(saisie).split() if len(m) >= 2]
    morceaux = []
    for mot in str(libelle).split(" "):
        n = normaliser(mot)
        proche = bool(n) and any(fuzz.ratio(n, c) >= seuil or (len(c) >= 4 and n.startswith(c)) for c in cibles)
        morceaux.append(f"<mark>{_html.escape(mot)}</mark>" if proche else _html.escape(mot))
    return " ".join(morceaux)
