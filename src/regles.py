"""
TuniShop - Plateforme vue 360
regles.py : règles d'affichage de la fiche Client (niveau de risque, signaux observés).

Les signaux sont des CONSTATS calculés sur les faits du client, affichés à côté du score de churn.
Ce ne sont PAS les raisons du modèle : le modèle n'expose pas d'explication par client
(une explication SHAP serait une évolution du notebook 08, en option).
Chaque règle et son seuil sont écrits ici, une seule fois, et testés (tests/test_regles.py).

Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import pandas as pd

from src.format import nombre, pct

# Seuils des signaux (modifiables ici seulement)
JOURS_SANS_COMMANDE = 90       # même horizon que la cible du churn (90 jours)
MIN_LIVRAISONS_EN_RETARD = 2
TAUX_RETARD_ELEVE = 0.30       # contre 17,3 % pour l'ensemble des livraisons 2025
BAISSE_CA = 0.30               # baisse du CA de l'année face à la précédente


def niveau_risque(decile) -> str | None:
    """Niveau lisible à partir du décile de risque (1 = 10 % des clients les plus à risque)."""
    if decile is None or pd.isna(decile):
        return None
    d = int(decile)
    return "élevé" if d <= 2 else "moyen" if d <= 5 else "faible"


def signaux(jours_sans_commande, experience: dict | None, annees: pd.DataFrame | None,
            rfm: pd.DataFrame | None, dernier_avis_polarite: str | None) -> list[str]:
    """Liste des constats défavorables observés sur le client, du plus récent au plus ancien."""
    s: list[str] = []
    if jours_sans_commande is not None and not pd.isna(jours_sans_commande) and jours_sans_commande >= JOURS_SANS_COMMANDE:
        s.append(f"{nombre(jours_sans_commande)} jours sans commande")

    if annees is not None and len(annees) >= 2:
        a = annees.sort_values("annee")
        der, pre = a.iloc[-1], a.iloc[-2]
        if pre["ca_reconnu_ttc"] and pre["ca_reconnu_ttc"] > 0:
            baisse = 1 - der["ca_reconnu_ttc"] / pre["ca_reconnu_ttc"]
            if baisse >= BAISSE_CA:
                s.append(f"CA {int(der['annee'])} en baisse de {pct(baisse, 0)} face à {int(pre['annee'])}")

    if rfm is not None and len(rfm) >= 2:
        r = rfm.sort_values("date_observation")
        avant, apres = r.iloc[-2]["segment_rfm"], r.iloc[-1]["segment_rfm"]
        if avant != apres:
            s.append(f"segment RFM passé de « {avant} » à « {apres} »")

    if experience:
        e = experience
        n_retard, taux = e.get("nb_livrees_en_retard") or 0, e.get("taux_retard")
        if n_retard >= MIN_LIVRAISONS_EN_RETARD and taux is not None and not pd.isna(taux) and taux >= TAUX_RETARD_ELEVE:
            s.append(f"{nombre(n_retard)} livraisons en retard ({pct(taux, 0)} de ses livraisons)")
        if (e.get("nb_echecs_livraison") or 0) > 0:
            s.append(f"{nombre(e['nb_echecs_livraison'])} livraison(s) en échec")
        if (e.get("nb_paiements_echoues") or 0) > 0:
            s.append(f"{nombre(e['nb_paiements_echoues'])} paiement(s) échoué(s)")
        if (e.get("nb_remboursements") or 0) > 0:
            s.append(f"{nombre(e['nb_remboursements'])} demande(s) de remboursement")

    if dernier_avis_polarite == "négatif":
        s.append("dernier avis négatif")
    return s


def date_rupture(demande: pd.DataFrame) -> pd.Timestamp | None:
    """Jour estimé où le stock de départ est épuisé, sans réapprovisionnement.
    La prévision est mensuelle : dans le mois de rupture, la demande est supposée régulière
    (interpolation linéaire). Renvoie None si le stock couvre toute la période prévue."""
    if demande is None or demande.empty:
        return None
    d = demande.sort_values("mois")
    stock = float(d["stock_depart"].iloc[0] or 0)
    cumul = 0.0
    for _, r in d.iterrows():
        q = float(r["quantite_prevue"] or 0)
        debut = pd.Timestamp(r["mois"])
        if q > 0 and cumul + q >= stock:
            part = max(stock - cumul, 0) / q
            return (debut + pd.Timedelta(days=int(part * debut.days_in_month))).normalize()
        cumul += q
    return None


def couverture_mois(stock, demande_t1) -> float | None:
    """Mois de vente couverts par le stock, au rythme moyen prévu du 1er trimestre."""
    if stock is None or demande_t1 is None or pd.isna(stock) or pd.isna(demande_t1) or demande_t1 <= 0:
        return None
    return float(stock) / (float(demande_t1) / 3)


def projection_stock(demande: pd.DataFrame, apres_rupture_j: int = 30) -> pd.DataFrame:
    """Stock projeté jour par jour sans réapprovisionnement, à partir du 1er mois prévu.
    La demande d'un mois est répartie également sur ses jours. La projection s'arrête
    apres_rupture_j jours après la rupture (ou à la fin de la prévision s'il n'y en a pas).
    Colonnes : jour, demande, stock (au début du jour, jamais négatif), perdu (demande non servie ce jour-là)."""
    if demande is None or demande.empty:
        return pd.DataFrame(columns=["jour", "demande", "stock", "perdu"])
    d = demande.sort_values("mois")
    jours, besoins = [], []
    for _, r in d.iterrows():
        debut = pd.Timestamp(r["mois"])
        n = debut.days_in_month
        for i in range(n):
            jours.append(debut + pd.Timedelta(days=i))
            besoins.append(float(r["quantite_prevue"] or 0) / n)
    t = pd.DataFrame({"jour": jours, "demande": besoins})
    reste = float(d["stock_depart"].iloc[0] or 0) - t["demande"].cumsum()
    t["stock"] = (reste + t["demande"]).clip(lower=0)      # stock au début du jour : 0 le jour de la rupture
    t["perdu"] = (-reste).clip(lower=0).diff().fillna((-reste).clip(lower=0)).clip(lower=0)
    rupture = t.index[t["stock"] <= 0]
    if len(rupture):
        t = t.iloc[: rupture[0] + apres_rupture_j + 1]
    return t.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Score fournisseur sur 100 (fiche Fournisseur) : moyenne de 3 notes
# ---------------------------------------------------------------------------
SCORE_BON, SCORE_A_SURVEILLER = 80, 60      # 80 et plus : fiable ; 60 à 79 : à surveiller ; moins de 60 : à risque


def score_fournisseurs(annee: pd.DataFrame) -> pd.DataFrame:
    """Ajoute ponctualite, completude, qualite et score (0-100) à un tableau d'une ligne par fournisseur
    (colonnes fiabilite_reelle, taux_reception, taux_retour) pour une même année.
    - ponctualité : part des livraisons arrivées dans la tolérance (fiabilité réelle) x 100 ;
    - complétude : quantité reçue / quantité commandée x 100 ;
    - qualité : rang du taux de retour de ses produits parmi les fournisseurs, 100 = le moins de retours.
      Un rang plutôt qu'un barème : les taux de retour sont tous faibles (quelques %) et proches.
    Le score est la moyenne des notes disponibles."""
    t = annee.copy()
    t["ponctualite"] = 100 * t["fiabilite_reelle"]
    t["completude"] = 100 * t["taux_reception"]
    rang = t["taux_retour"].rank(method="average", ascending=True)
    n = t["taux_retour"].notna().sum()
    t["qualite"] = 100 * (n - rang) / (n - 1) if n > 1 else 100.0
    t["score"] = t[["ponctualite", "completude", "qualite"]].mean(axis=1, skipna=True)
    return t


def niveau_fournisseur(score) -> str | None:
    if score is None or pd.isna(score):
        return None
    return "fiable" if score >= SCORE_BON else "à surveiller" if score >= SCORE_A_SURVEILLER else "à risque"
