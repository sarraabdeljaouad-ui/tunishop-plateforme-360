"""
TuniShop - Plateforme vue 360
Page Modèles (maquette 08, v2) : une carte par cas (modèle retenu, mesure 2025, gain face à la référence,
état du suivi, pages alimentées), indicateurs de suivi de la dernière exécution face à leur seuil,
variables les plus importantes du churn, registre des versions.

Adresse : /modeles
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import donnees, ui
from src.format import date_fr, nombre, pct

modeles = donnees.ml_modeles()
registre = donnees.ml_registre()
suivi = donnees.ml_suivi()
historique = donnees.ml_suivi_historique()

TITRE = {"ventes": "Prévision des ventes", "churn": "Churn client", "demande": "Demande par produit",
         "retard": "Retard de livraison"}
ALIMENTE = {"ventes": "Accueil", "churn": "Accueil, fiche Client", "demande": "Accueil, fiches Produit et Fournisseur",
            "retard": "Accueil, fiches Commande et Transporteur"}
ERREUR = ("MAPE", "WAPE", "MAE", "RMSE")                  # mesures d'erreur : plus bas = mieux


def cle_cas(cas) -> str:
    c = str(cas).lower()
    return next((k for k in TITRE if k in c), c)


def est_alerte(statut) -> bool:
    s = str(statut).lower()
    return "alerte" in s or "ko" == s or "dépass" in s or "depass" in s


def format_mesure(mesure, valeur) -> str:
    if valeur is None or pd.isna(valeur):
        return "—"
    return pct(valeur) if any(m in str(mesure).upper() for m in ERREUR) else nombre(valeur, 3)


suivi = suivi.assign(cle=suivi["cas"].map(cle_cas), alerte=suivi["statut"].map(est_alerte))
retenus = modeles[modeles["retenu"] == 1].assign(cle=lambda t: t["cas"].map(cle_cas))

# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
n_alertes = int(suivi["alerte"].sum())
pastilles = [ui.badge(f"{retenus['cle'].nunique()} modèles en production", "gris"),
             ui.badge("Rescorés chaque nuit à 22 h", "vert")]
if n_alertes:
    pastilles.append(ui.badge(f"{n_alertes} indicateur{'s' if n_alertes > 1 else ''} en alerte", "orange"))
ui.en_tete("Accueil › Modèles", "Modèles de machine learning", pastilles=pastilles,
           liens=['<span class="ts-lien-bouton">pbi.v_ml_modeles · v_ml_registre · v_ml_suivi</span>'])

# ---------------------------------------------------------------------------
# 2. Une carte par cas
# ---------------------------------------------------------------------------
cles = [k for k in TITRE if k in set(retenus["cle"])] + sorted(set(retenus["cle"]) - set(TITRE))
cartes = []
for k in cles:
    r = retenus[retenus["cle"] == k].iloc[0]
    alerte = bool(suivi.loc[suivi["cle"] == k, "alerte"].any())
    etat = ui.badge("À surveiller", "orange") if alerte else ui.badge("Actif", "vert")
    version = registre[(registre["cas"].map(cle_cas) == k)]
    version = f" · {ui.e(version.iloc[0]['version'])}" if not version.empty and pd.notna(version.iloc[0]["version"]) else ""
    # Gain face à la référence : positif = le modèle fait mieux (moins d'erreur, ou AUC plus haute),
    # comme dans le PV global (« MAPE 9,5 % (−37,5 % d'erreur) », « AUC 0,818 (+2,9 %) »).
    erreur = any(m in str(r["mesure"]).upper() for m in ERREUR)
    gain = r["gain_vs_reference"]
    if pd.isna(gain):                                  # colonne vide : recalcul depuis la ligne « référence »
        ref_ = modeles[(modeles["cas"] == r["cas"]) & modeles["role"].str.lower().str.startswith("réf")]
        if not ref_.empty and pd.notna(ref_.iloc[0]["valeur_test"]) and ref_.iloc[0]["valeur_test"]:
            v_ref = ref_.iloc[0]["valeur_test"]
            gain = (v_ref - r["valeur_test"]) / v_ref if erreur else (r["valeur_test"] - v_ref) / v_ref
    if pd.notna(gain):
        couleur = ui.VERT if gain > 0 else ui.ROUGE
        txt = (f"{'-' if gain > 0 else '+'}{pct(abs(gain))} d'erreur" if erreur
               else f"{'+' if gain >= 0 else '-'}{pct(abs(gain))}")
        txt_gain = f'<span style="color:{couleur};font-weight:600">{txt}</span> vs référence'
    else:
        txt_gain = ""
    cartes.append(
        f'<div class="ts-kpi"><div style="display:flex;justify-content:space-between;align-items:center">'
        f'<b style="font-size:1.05rem">{ui.e(TITRE.get(k, r["cas"]))}</b>{etat}</div>'
        f'<div class="ts-kpi-note">{ui.e(r["modele"])}{version}</div>'
        f'<div class="ts-kpi-label" style="margin-top:.5rem">{ui.e(r["mesure"])} 2025</div>'
        f'<div class="ts-kpi-valeur">{format_mesure(r["mesure"], r["valeur_test"])}</div>'
        f'<span class="ts-kpi-delta">{txt_gain}</span>'
        f'<div class="ts-kpi-note" style="margin-top:.4rem;color:{ui.FONCE}">Alimente : {ALIMENTE.get(k, "—")}</div></div>')
ui.rangee_kpi(cartes, colonnes=max(len(cartes), 1))

# ---------------------------------------------------------------------------
# 3. Suivi | variables importantes
# ---------------------------------------------------------------------------
g, d = st.columns([1.5, 1], gap="medium")
with g, st.container(border=True):
    ui.titre_carte("Suivi de la dernière exécution", "pbi.v_ml_suivi · indicateur face à son seuil")
    if suivi.empty:
        st.caption("Suivi non publié.")
    else:
        alertes = suivi[suivi["alerte"]]
        if not alertes.empty:
            a0 = alertes.iloc[0]
            ui.encadre(f"<b>{len(alertes)} alerte{'s' if len(alertes) > 1 else ''}.</b> Exemple : {ui.e(TITRE.get(a0['cle'], a0['cas']))}, "
                       f"{ui.e(a0['indicateur'])} ({ui.e(a0['objet'])}) = {nombre(a0['valeur'], 3)} pour un seuil de "
                       f"{nombre(a0['seuil'], 3)}.", alerte=True)
        t = suivi.sort_values(["alerte", "cle"], ascending=[False, True])
        ui.tableau([("Modèle", ""), ("Objet", ""), ("Indicateur", ""), ("Période", ""), ("Valeur", "num"),
                    ("Seuil", "num"), ("Statut", "")],
                   [[ui.e(TITRE.get(r["cle"], r["cas"])), ui.e(r["objet"]), ui.e(r["indicateur"]), ui.e(r["periode"]),
                     nombre(r["valeur"], 3), nombre(r["seuil"], 3),
                     ui.badge(ui.e(r["statut"]), "orange" if r["alerte"] else "vert")] for _, r in t.head(12).iterrows()])
        st.caption(f"{len(suivi)} indicateurs suivis" + (" · 12 premiers, alertes d'abord" if len(suivi) > 12 else "")
                   + ". Évolution dans le temps : ci-dessous.")

with d, st.container(border=True):
    ui.titre_carte("Variables les plus importantes · churn", "ana.ml03_importance")
    imp = donnees.importance_churn(8)
    if imp.empty:
        st.caption("Importance non publiée.")
    else:
        ui.barres([(r["variable"], r["perte_auc"], nombre(r["perte_auc"], 3)) for _, r in imp.iterrows()])
        st.caption("Perte d'AUC quand on mélange la variable (permutation, test 2025). "
                   "La récence explique l'essentiel du modèle.")

# ---------------------------------------------------------------------------
# 4. Suivi dans le temps : alertes à chaque exécution | retard mois par mois
# ---------------------------------------------------------------------------
COULEURS = {"ventes": ui.CANARD, "churn": ui.ROUGE, "demande": ui.ORANGE, "retard": ui.FONCE}
SERIES = [ui.CANARD, ui.BLEU, ui.ROUGE, ui.ORANGE, ui.GRIS]       # transporteurs, ordre alphabétique


MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def mois_court(periode) -> str:
    """'2025-01' -> 'janv. 2025'."""
    t = pd.Timestamp(f"{periode}-01")
    return f"{MOIS_COURTS[t.month - 1]} {t.year}"


ui.section("Suivi dans le temps")
g, d = st.columns(2, gap="medium")
with g, st.container(border=True):
    ui.titre_carte("Alertes à chaque exécution", "pbi.v_ml_suivi_historique")
    if historique.empty:
        st.caption("Historique non publié : il commence avec la version 1.5 de l'étape 7.")
    else:
        h = (historique.assign(cle=historique["cas"].map(cle_cas))
             .groupby(["date_donnees", "cle"], as_index=False)[["indicateurs", "alertes"]].sum())
        dates = sorted(h["date_donnees"].unique())
        fig = go.Figure()
        for k in TITRE:
            alertes = h[h["cle"] == k].set_index("date_donnees")["alertes"].reindex(dates, fill_value=0)
            fig.add_trace(go.Scatter(x=[date_fr(x) for x in dates], y=alertes, name=TITRE[k], mode="lines+markers",
                                     marker=dict(size=9), line=dict(color=COULEURS[k], width=2)))
        ui.styler(fig, 260).update_yaxes(rangemode="tozero", tickformat="d")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        dernier = h[h["date_donnees"] == dates[-1]]
        texte = (f"Dernière exécution (données au {date_fr(dates[-1])}) : {nombre(dernier['alertes'].sum())} alertes "
                 f"sur {nombre(dernier['indicateurs'].sum())} indicateurs.")
        if len(dates) == 1:
            texte += (" Une seule exécution pour l'instant : un point par modèle. La courbe se remplit à chaque "
                      "exécution de la chaîne sur des données plus récentes.")
        else:
            texte += f" {len(dates)} exécutions depuis les données au {date_fr(dates[0])}."
        st.caption(texte)

with d, st.container(border=True):
    production = suivi[suivi["cas"] == "retard_production"]
    rejeu = production if not production.empty else suivi[suivi["cas"] == "retard"]
    ui.titre_carte("Retard de livraison : écart prévu − réel, mois par mois", "pbi.v_ml_suivi")
    if rejeu.empty:
        st.caption("Suivi mensuel du retard non publié.")
    else:
        seuil = float(rejeu["seuil"].iloc[0])
        p = rejeu.pivot_table(index="periode", columns="objet", values="valeur").sort_index()
        fig = go.Figure()
        for i, tr in enumerate(p.columns):
            fig.add_trace(go.Scatter(x=[mois_court(m) for m in p.index], y=p[tr], name=tr, mode="lines+markers",
                                     line=dict(width=2, color=SERIES[i % len(SERIES)])))
        for y in (-seuil, seuil):
            fig.add_hline(y=y, line=dict(color=ui.ROUGE, width=1, dash="dash"))
        ui.styler(fig, 260).update_yaxes(tickformat=".0%")
        fig.update_xaxes(tickangle=0, dtick=2)                     # un mois sur deux, à l'horizontale
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        n = int(rejeu["alerte"].sum())
        modele = ("modèle de production, réappris chaque mois sur 12 mois" if not production.empty
                  else "modèle évalué, appris sur 2023-2024")
        st.caption(f"{modele.capitalize()} · {nombre(n)} alerte{'s' if n > 1 else ''} sur {nombre(len(rejeu))} "
                   f"(transporteur × mois) · pointillés : seuils de ±{nombre(seuil * 100)} points. "
                   "Sous zéro, le modèle sous-estime le retard.")

# ---------------------------------------------------------------------------
# 5. Registre
# ---------------------------------------------------------------------------
with st.container(border=True):
    ui.titre_carte("Registre des versions", "pbi.v_ml_registre")
    if registre.empty:
        st.caption("Registre non publié.")
    else:

        def statut(r) -> str:
            role = str(r["role"]).lower()
            if "retenu" in role or "production" in role:
                return ui.badge("À surveiller", "orange") if suivi.loc[suivi["cle"] == cle_cas(r["cas"]), "alerte"].any() \
                    else ui.badge("Actif", "vert")
            return ui.badge(ui.e(r["role"]), "gris")

        ui.tableau([("Modèle", ""), ("Cas", ""), ("Version", ""), ("Appris le", ""), ("Période d'apprentissage", ""),
                    ("Lignes", "num"), ("Variables", "num"), ("Seuil", "num"), ("Statut", "")],
                   [[ui.e(r["nom"]), ui.e(TITRE.get(cle_cas(r["cas"]), r["cas"])), ui.e(r["version"]), ui.e(r["appris_le"]),
                     ui.e(r["periode_apprentissage"]), nombre(r["lignes_apprentissage"]), nombre(r["nb_variables"]),
                     nombre(r["seuil"], 2) if pd.notna(r["seuil"]) else "—", statut(r)] for _, r in registre.iterrows()])
