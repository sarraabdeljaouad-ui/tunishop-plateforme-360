"""
TuniShop - Plateforme vue 360
Page Voix du client (maquette 07, v2) : text mining des avis (v1.4). Filtres catégorie et année,
bandeau « À retenir », 5 chiffres, volume par thème, langues et expressions derja fréquentes,
confrontation des thèmes aux faits (retards et retours réels) avec sa conclusion.

Adresse : /voix-du-client
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import streamlit as st

from src import donnees, ui
from src.format import nombre, pct

ui.en_tete("Accueil › Voix du client", "Voix du client",
           sous_titre="Text mining des avis : thèmes, langue (français et derja en arabizi), polarité, "
                      "confrontation aux faits.")

ref = donnees.date_reference()
f1, f2, _ = st.columns([1.3, 1, 2])
cats = ["Toutes les catégories"] + donnees.tm_categories()
categorie = f1.selectbox("Catégorie", cats, label_visibility="collapsed")
annees = ["Toute la période"] + [str(a) for a in range(ref.year, ref.year - 3, -1)]
periode = f2.selectbox("Période", annees, label_visibility="collapsed")
cat = None if categorie == cats[0] else categorie
an = None if periode == annees[0] else int(periode)

res = donnees.tm_resume(cat, an)
themes = donnees.tm_themes(cat, an)
langues = donnees.tm_langues(cat, an)
verif = donnees.tm_verification()


def taux_pondere(t: pd.DataFrame, col: str):
    t = t.dropna(subset=[col])
    return None if t.empty or t["avis"].sum() == 0 else float((t[col] * t["avis"]).sum() / t["avis"].sum())


# Conclusion de la confrontation aux faits (toutes catégories, toute la période)
neg = verif[verif["polarite"] == "négatif"]
liv = neg[neg["theme"] == "Livraison"]
r_liv = None if liv.empty else float(liv["part_colis_en_retard"].iloc[0])
r_neg_autres = taux_pondere(neg[neg["theme"] != "Livraison"], "part_colis_en_retard")
r_pos = taux_pondere(verif[verif["polarite"] == "positif"], "part_colis_en_retard")
suit_la_note = r_liv is not None and r_neg_autres is not None and r_liv <= r_neg_autres + 0.03

# ---------------------------------------------------------------------------
# 1. À retenir
# ---------------------------------------------------------------------------
part_derja = res["nb_derja"] / res["nb_commentes"] if res["nb_commentes"] else None
constats = []
if part_derja is not None:
    constats.append(f"<b>{pct(part_derja, 0)}</b> des commentaires en derja")
if not themes.empty:
    constats.append(f"Le thème « {ui.e(themes.iloc[0]['theme'])} » domine (<b>{nombre(themes.iloc[0]['mentions'])}</b> mentions)")
if r_liv is not None:
    constats.append("Le texte suit la <b>note</b>, pas l'événement vécu" if suit_la_note
                    else "Les plaintes de livraison reflètent de <b>vrais retards</b>")
ui.a_retenir(constats or ["Aucun avis commenté pour ce filtre"], None, "neutre")

# ---------------------------------------------------------------------------
# 2. Chiffres
# ---------------------------------------------------------------------------
ui.rangee_kpi([
    ui.kpi("Avis", nombre(res["nb_avis"]), note="commentés ou non"),
    ui.kpi("Avec commentaire", nombre(res["nb_commentes"]),
           note=f"{pct(res['nb_commentes'] / res['nb_avis'], 0)} des avis" if res["nb_avis"] else ""),
    ui.kpi("En derja", nombre(res["nb_derja"]), note=f"{pct(part_derja, 0)} des commentaires" if part_derja is not None else ""),
    ui.kpi("Formulations distinctes", nombre(res["nb_formulations"]), note="phrases différentes"),
    ui.kpi("Incohérences texte / note", nombre(res["nb_incoherents"]), note="texte positif et note basse, ou l'inverse"),
], colonnes=5)

# ---------------------------------------------------------------------------
# 3. Thèmes | langue
# ---------------------------------------------------------------------------
g, d = st.columns([1.15, 1], gap="medium")
with g, st.container(border=True):
    ui.titre_carte("Volume par thème", "un avis peut en avoir plusieurs · pbi.v_tm_avis_themes")
    if themes.empty:
        st.caption("Aucun avis commenté.")
    else:
        ui.barres([(r["theme"], r["mentions"], f"{nombre(r['mentions'])} · {pct(r['negatives'] / r['mentions'], 0)} nég.")
                   for _, r in themes.head(8).iterrows()])
        st.caption("Nombre de mentions, puis part de mentions négatives.")

with d, st.container(border=True):
    ui.titre_carte("Langue", "pbi.v_tm_avis")
    if langues.empty:
        st.caption("Aucun avis commenté.")
    else:
        tot = langues["avis"].sum()
        couleurs = {"derja": "#5B8DB8"}
        st.markdown('<div style="display:flex;border-radius:10px;overflow:hidden;color:#FFF;font-weight:600;'
                    'font-size:.95rem;margin-bottom:.8rem">' + "".join(
                        f'<div style="width:{100 * r["avis"] / tot:.1f}%;background:{couleurs.get(r["langue"], ui.CANARD)};'
                        f'padding:.55rem .8rem;white-space:nowrap">{ui.e(str(r["langue"]).capitalize())} · {nombre(r["avis"])}</div>'
                        for _, r in langues.iterrows()) + "</div>", unsafe_allow_html=True)
        ex = donnees.tm_expressions_derja(cat, an, 5)
        if not ex.empty:
            st.markdown("**Expressions derja les plus fréquentes**")
            ton = {"positif": "vert", "négatif": "rouge", "neutre": "gris"}
            ui.tableau([("Expression", ""), ("Sens", ""), ("Polarité", ""), ("Avis", "num")],
                       [[f"<i>{ui.e(r['expression'])}</i>", ui.e(r["sens"]), ui.badge(ui.e(r["polarite"]), ton.get(r["polarite"], "gris")),
                         nombre(r["avis"])] for _, r in ex.iterrows()])

# ---------------------------------------------------------------------------
# 4. Le texte suit-il les faits ?
# ---------------------------------------------------------------------------
with st.container(border=True):
    ui.titre_carte("Le texte suit-il les faits ?", "retards et retours réels · pbi.v_tm_verification_faits")
    if r_liv is not None and r_neg_autres is not None:
        debut = (f"<b>Conclusion.</b> Les avis négatifs ont plus de retards que les positifs "
                 f"({pct(r_neg_autres)} contre {pct(r_pos)}). " if r_pos is not None else "<b>Conclusion.</b> ")
        if suit_la_note:
            txt = (debut + f"Mais un avis qui <i>parle</i> de livraison n'en a pas plus qu'un autre avis négatif : "
                   f"{pct(r_liv)} contre {pct(r_neg_autres)}. Le texte suit la note, pas l'événement vécu.")
        else:
            txt = (debut + f"Et un avis qui parle de livraison en a nettement plus : {pct(r_liv)} contre "
                   f"{pct(r_neg_autres)}. Les plaintes de livraison reflètent de vrais retards.")
        ui.encadre(txt, alerte=True)
    if verif.empty:
        st.caption("Confrontation non publiée.")
    else:
        ton = {"positif": "vert", "négatif": "rouge", "neutre": "gris", "toutes": "bleu"}
        ordre = {"négatif": 0, "neutre": 1, "positif": 2, "toutes": 3}
        v = verif.assign(o=verif["polarite"].map(ordre).fillna(4)).sort_values(["o", "avis"], ascending=[True, False])

        def motif(r) -> str:
            if pd.isna(r["part_retour_motif_lie"]):
                return "—"
            codes = ", ".join(m.strip().replace("_", " ") for m in str(r["motifs_lies"]).split(",")) if pd.notna(r["motifs_lies"]) else ""
            return pct(r["part_retour_motif_lie"]) + (f'<br><span style="color:#8A94A3;font-size:.8rem">{ui.e(codes)}</span>'
                                                       if codes else "")

        def gras(r, texte) -> str:
            return f"<b>{texte}</b>" if r["polarite"] == "toutes" or r["theme"] == "Livraison" else texte

        ui.tableau([("Thème", ""), ("Polarité", ""), ("Avis", "num"), ("Colis en retard", "num"),
                    ("Retour", "num"), ("Retour pour le motif lié", "num")],
                   [[gras(r, ui.e(r["theme"])), ui.badge(ui.e(r["polarite"]), ton.get(r["polarite"], "gris")),
                     nombre(r["avis"]), gras(r, pct(r["part_colis_en_retard"])), pct(r["part_retour"]), motif(r)]
                    for _, r in v.iterrows()])
        st.caption("Toutes catégories, toute la période : la confrontation n'est pas recalculée par filtre. "
                   "Retour pour le motif lié : par exemple, retour pour « taille inadaptée » quand l'avis parle de taille.")
