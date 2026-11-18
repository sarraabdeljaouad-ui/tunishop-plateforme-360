"""
TuniShop - Plateforme vue 360
Fiche Produit (maquette 03, v2) : bandeau « À retenir », chiffres clés de l'année, demande mensuelle
prévue face au réel, projection du stock jour par jour sans réapprovisionnement (rupture, date limite
de commande, ventes perdues), catégories achetées ensemble, thèmes et exemples d'avis.

Adresse : /produit?id=PRD0001
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import donnees, regles, ui
from src.format import date_fr, ecart_points, mois_fr, nombre, pct, tnd, tnd_compact, variation
from src.liens import identifiant_demande


def entete_vide(message: str, erreur: bool = False) -> None:
    ui.en_tete("Accueil › Fiche produit", "Fiche produit")
    (st.error if erreur else st.info)(message)
    st.page_link("pages/recherche.py", label="Aller à la recherche", icon=":material/search:")
    st.stop()


ident = identifiant_demande()
if ident is None:
    entete_vide("Choisis un produit depuis la recherche.")
idt = donnees.produit_identite(ident)
if idt.empty:
    entete_vide(f"Aucun produit ne porte l'identifiant {ident}.", erreur=True)

p = idt.iloc[0]
ref = donnees.date_reference()
an, prec = ref.year, ref.year - 1
annees = donnees.produit_annees(ident).set_index("annee")
kpi = donnees.produit_kpi(ident)
stock = donnees.produit_stock_mois(ident)
demande = donnees.produit_demande(ident)
four = donnees.fournisseur_fiche(p["fournisseur_id"]) if pd.notna(p["fournisseur_id"]) else pd.DataFrame()
k = kpi.iloc[0] if not kpi.empty else None
f = four.iloc[0] if not four.empty else None
a = annees.loc[an] if an in annees.index else None
pa = annees.loc[prec] if prec in annees.index else None
rupture = regles.date_rupture(demande)


def v(serie, col):
    return None if serie is None else serie[col]


def manque(x) -> bool:
    return x is None or pd.isna(x)


# ---------------------------------------------------------------------------
# Calculs de la fiche : prévision, stock, fournisseur
# ---------------------------------------------------------------------------
dm = demande.assign(mois=pd.to_datetime(demande["mois"])) if not demande.empty else demande
stock_dep = float(demande["stock_depart"].iloc[0]) if not demande.empty else None
t1 = dm[(dm["mois"].dt.year == an + 1) & (dm["mois"].dt.month <= 3)]["quantite_prevue"].sum() if not demande.empty else None
couv = regles.couverture_mois(stock_dep, t1)
delai = float(f["delai_reel_moyen_j"]) if f is not None and not manque(f["delai_reel_moyen_j"]) else None
annonce = float(f["delai_annonce_j"]) if f is not None and not manque(f["delai_annonce_j"]) else None
lent = delai is not None and annonce is not None and round(delai) > annonce
limite = rupture - pd.Timedelta(days=round(delai)) if rupture is not None and delai is not None else None
trop_tard = limite is not None and limite <= ref

# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
pastilles = [ui.badge(f"{ui.e(p['categorie'])} › {ui.e(p['sous_categorie'])}", "bleu"),
             ui.badge(tnd(p["prix_catalogue_ttc"]), "gris")]
if not manque(v(a, "taux_marge")):
    pastilles.append(ui.badge(f"Marge {pct(a['taux_marge'], 0)}", "gris"))
if pd.notna(p["statut_produit"]) and str(p["statut_produit"]).lower() != "actif":
    pastilles.append(ui.badge(ui.e(p["statut_produit"]), "orange"))
liens = []
if pd.notna(p["fournisseur_id"]):
    liens.append(ui.lien_bouton(p["nom_fournisseur"], "fournisseur", p["fournisseur_id"]))
if k is not None:
    liens.append(f'<a class="ts-lien-bouton" href="#avis-produit" target="_self">↗ {nombre(k["nb_avis"])} avis</a>')
ident_affiche = ident + (f" · SKU {p['sku']}" if pd.notna(p["sku"]) else "")
ui.en_tete("Accueil › Fiche produit", p["nom_produit"], ident_affiche, pastilles=pastilles, liens=liens)

# ---------------------------------------------------------------------------
# 2. À retenir
# ---------------------------------------------------------------------------
constats = []
if not demande.empty:
    prevu = dm[dm["mois"].dt.year == an + 1]
    mois_prevus = prevu["mois"].dt.month.tolist()
    vm_an = donnees.produit_ventes_mois(ident)
    vm_an["mois"] = pd.to_datetime(vm_an["mois"])
    reel_meme = vm_an[(vm_an["mois"].dt.year == an) & vm_an["mois"].dt.month.isin(mois_prevus)]["quantite"].sum()
    tot = prevu["quantite_prevue"].sum()
    periode = "" if len(mois_prevus) == 12 else f" sur {len(mois_prevus)} mois"
    var = variation(tot, reel_meme) if reel_meme else None
    constats.append(f"Demande {an + 1} prévue{periode} " + (f"<b>{var}</b> " if var else "") + f"({nombre(tot)} u.)")
    if rupture is not None:
        constats.append(f"Stock de <b>{nombre(stock_dep)} u.</b> : rupture vers le <b>{date_fr(rupture)}</b>")
    else:
        constats.append(f"Stock de <b>{nombre(stock_dep)} u.</b> : couvre toute la période prévue")
if lent:
    constats.append(f"Fournisseur lent : <b>{nombre(delai)} j réels</b> pour {nombre(annonce)} annoncés")
elif couv is not None:
    constats.append(f"Couverture de stock : <b>{nombre(couv, 1)} mois</b>")
if rupture is None:
    action, ton = None, "neutre"
elif trop_tard:
    action, ton = "commander dès maintenant", "rouge"
elif limite is not None:
    action, ton = f"commander avant le {date_fr(limite)}", "orange"
else:
    action, ton = "réapprovisionner avant la rupture", "orange"
ui.a_retenir(constats or ["Pas de prévision de demande pour ce produit"], action, ton)

# ---------------------------------------------------------------------------
# 3. Chiffres clés
# ---------------------------------------------------------------------------
ui.section(f"Chiffres clés {an}")


def carte(label, col, valeur, bon_si_hausse=True, points=False):
    x, y = v(a, col), v(pa, col)
    delta = None if manque(x) or manque(y) else (ecart_points(x, y) if points else variation(x, y))
    return ui.kpi(label, valeur, ui.delta_html(delta, ui.sens(x, y), bon_si_hausse=bon_si_hausse,
                                                suffixe=f"vs {prec}"))


na, np_ = v(a, "note_moyenne"), v(pa, "note_moyenne")
dn = None if manque(na) or manque(np_) else na - np_
if couv is None:
    note_couv = "pas de prévision"
elif couv < 1:
    note_couv = f'<span style="color:{ui.ROUGE}">sous le seuil de 1 mois</span>'
else:
    note_couv = f"au rythme prévu du T1 {an + 1}"
ui.rangee_kpi([
    carte("CA", "ca_ttc", tnd_compact(v(a, "ca_ttc"))),
    carte("Unités vendues", "quantite_vendue", nombre(v(a, "quantite_vendue"))),
    carte("Marge brute HT", "marge_brute_ht", tnd_compact(v(a, "marge_brute_ht"))),
    ui.kpi("Couverture de stock", "—" if couv is None else f"{nombre(couv, 1)} mois", note=note_couv),
    ui.kpi("Note moyenne", "—" if manque(na) else f"{nombre(na, 1)} / 5",
           ui.delta_html(None if dn is None else ("+" if dn >= 0 else "-") + nombre(abs(dn), 1),
                         ui.sens(dn, 0) if dn is not None else 0, suffixe=f"vs {prec}")),
    carte("Taux de retour", "taux_retour", pct(v(a, "taux_retour")), bon_si_hausse=False, points=True),
], colonnes=6)
if a is None:
    st.info(f"Aucune vente en {an}.")

# ---------------------------------------------------------------------------
# 4. Prévision et stock
# ---------------------------------------------------------------------------
ui.section("Prévision et stock")
g, d = st.columns([1.5, 1], gap="medium")
with g, st.container(border=True):
    ui.titre_carte(f"Demande mensuelle : prévu {an + 1} et réel {an}", "pbi.v_ml_scores_demande · modèle v2")
    vm = donnees.produit_ventes_mois(ident)
    vm["mois"] = pd.to_datetime(vm["mois"])
    reel = vm[vm["mois"].dt.year == an]
    reel = pd.Series(reel["quantite"].values, index=reel["mois"].dt.month).reindex(range(1, 13)).fillna(0)
    fig = go.Figure(go.Scatter(x=list(range(1, 13)), y=reel.values, name=f"Réel {an}", mode="lines",
                               line=dict(color=ui.CLAIR, width=3), hovertemplate="%{y:,.0f} u.<extra>" + str(an) + "</extra>"))
    if not demande.empty:
        dp = dm[dm["mois"].dt.year == an + 1]
        fig.add_trace(go.Scatter(x=dp["mois"].dt.month, y=dp["quantite_prevue"], name=f"Prévu {an + 1}", mode="lines",
                                 line=dict(color=ui.FONCE, width=3, dash="dash"),
                                 hovertemplate="%{y:,.0f} u.<extra>" + str(an + 1) + "</extra>"))
    ui.styler(fig, 280).update_xaxes(tickmode="array", tickvals=list(range(1, 13)), range=[0.7, 12.3],
                                     ticktext=["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Modèle de demande v2 (WAPE 47,5 %) : à lire comme un ordre de grandeur, pas au mois près.")

with d, st.container(border=True):
    ui.titre_carte("Projection du stock sans réapprovisionnement", f"à partir du 01/01/{an + 1}")
    proj = regles.projection_stock(demande)
    if proj.empty:
        st.caption("Pas de prévision de demande : pas de projection.")
    else:
        fig = go.Figure(go.Scatter(x=proj["jour"], y=proj["stock"], mode="lines", name="Stock projeté (u.)",
                                   line=dict(color=ui.ROUGE, width=3), fill="tozeroy", fillcolor="rgba(180,35,24,0.07)",
                                   hovertemplate="%{x|%d/%m} · %{y:,.0f} u.<extra></extra>"))
        if rupture is not None:
            fig.add_vrect(x0=rupture, x1=proj["jour"].iloc[-1], fillcolor="rgba(180,35,24,0.06)", line_width=0)
            fig.add_vline(x=rupture, line=dict(color=ui.ROUGE, dash="dash", width=1.5))
            fig.add_annotation(x=rupture, y=1.06, yref="paper", text=f"Rupture le {rupture:%d/%m}", showarrow=False,
                               font=dict(color=ui.ROUGE, size=12), xanchor="left")
            perdues = proj.loc[proj["jour"] >= rupture, "perdu"].sum()
            fig.add_annotation(x=proj["jour"].iloc[-1], y=max(stock_dep, 1) * 0.25, xanchor="right", showarrow=False,
                               text=f"≈ {nombre(perdues)} ventes perdues<br>jusqu'au {proj['jour'].iloc[-1]:%d/%m}",
                               font=dict(color=ui.ROUGE, size=12))
        if limite is not None and limite >= proj["jour"].iloc[0]:
            fig.add_vline(x=limite, line=dict(color=ui.ORANGE, dash="dash", width=1.5))
            fig.add_annotation(x=limite, y=0.94, yref="paper", text=f"Commander le {limite:%d/%m}", showarrow=False,
                               font=dict(color=ui.ORANGE, size=12), xanchor="left")
        ui.styler(fig, 280, legende=False).update_xaxes(tickformat="%d/%m")
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        par_jour = proj["demande"].iloc[: min(31, len(proj))].mean()
        txt = f"Demande prévue ≈ {nombre(par_jour, 1)} u./jour en janvier"
        if delai is not None:
            txt += f" · délai réel du fournisseur {nombre(delai)} j" + (f" (annoncé {nombre(annonce)} j)" if annonce else "")
        if trop_tard:
            txt += f" · la commande aurait dû partir le {date_fr(limite)}"
        st.caption(txt + ". Demande supposée régulière dans le mois.")

# ---------------------------------------------------------------------------
# 5. Ce que disent les clients et ce qu'ils achètent avec
# ---------------------------------------------------------------------------
ui.section("Ce que disent les clients et ce qu'ils achètent avec")
c1, c2, c3 = st.columns([1, 1.05, 1.25], gap="medium")
with c1, st.container(border=True):
    ui.titre_carte("Catégories achetées avec", "pbi.v_dm_regles · règles stables")
    rg = donnees.regles_categorie(p["categorie"], p["sous_categorie"])
    if rg.empty:
        st.caption(f"Aucune règle stable sur 2025 pour « {p['categorie']} ».")
    else:
        ui.tableau([("Achetée avec", ""), ("Confiance", "num"), ("Lift", "num")],
                   [[ui.e(r["consequents"]), pct(r["confidence_2025"], 0), nombre(r["lift_2025"], 2)]
                    for _, r in rg.head(4).iterrows()])
    st.caption("Mesures 2025. Entre produits, les règles ne tiennent pas sur 2025 (notebook DM03) : "
               "on montre les catégories.")

with c2, st.container(border=True):
    sy = donnees.produit_synthese_avis(ident)
    s = sy.iloc[0] if not sy.empty else None
    n_com = f" {nombre(s['nb_commentes'])}" if s is not None and "nb_commentes" in s and pd.notna(s["nb_commentes"]) else ""
    ui.titre_carte(f"Thèmes de ses{n_com} avis commentés", "text mining")
    th = donnees.produit_themes(ident)
    if th.empty:
        st.caption("Aucun avis commenté.")
    else:
        ui.barres([(r["theme"], r["nb_avis"], nombre(r["nb_avis"])) for _, r in th.head(5).iterrows()])
    if s is not None:
        pastilles = [ui.badge(f"Derja {pct(s['part_derja'], 0)}", "bleu")]
        n_inc = int(s["nb_incoherents"] or 0)
        pastilles.append(ui.badge(f"{n_inc} avis incohérent{'s' if n_inc > 1 else ''}", "orange" if n_inc else "gris"))
        st.markdown(" ".join(pastilles), unsafe_allow_html=True)

with c3, st.container(border=True):
    st.markdown('<a id="avis-produit"></a>', unsafe_allow_html=True)
    ui.titre_carte("Exemples d'avis", "les plus récents")
    av = donnees.produit_avis(ident, 4)
    if av.empty:
        st.caption("Aucun avis commenté.")
    else:
        def ton_note(n):
            return "rouge" if n <= 2 else "orange" if n == 3 else "vert"

        def texte_avis(r) -> str:
            t = f"<i>« {ui.e(r['texte_nettoye'])} »</i>"
            if str(r["langue"]).lower() == "derja":
                t += " " + ui.badge("derja", "bleu")
            if isinstance(r["coherence"], str) and r["coherence"] not in ("cohérent", "non évaluable"):
                t += " " + ui.badge("incohérent", "orange")
            return t + f'<br><span style="color:#8A94A3;font-size:.8rem">{date_fr(r["date_avis"])}</span>'

        ui.tableau([("Avis", ""), ("Note", "num")],
                   [[texte_avis(r), ui.badge(nombre(r["note"]), ton_note(r["note"])) if pd.notna(r["note"]) else "—"]
                    for _, r in av.iterrows()])
    if k is not None:
        st.caption(f"Depuis le début : {nombre(k['quantite_vendue'])} unités vendues à {nombre(k['nb_clients'])} clients, "
                   f"{nombre(k['nb_avis'])} avis (commentés ou non).")
