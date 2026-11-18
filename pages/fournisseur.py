"""
TuniShop - Plateforme vue 360
Fiche Fournisseur (maquette 04, v2) : bandeau « À retenir », chiffres clés de l'année dont le score sur 100,
le score en détail (promesse face à la réalité), achats et délai réel par mois face au délai annoncé,
produits fournis avec leur stock et leur rupture prévue.

Adresse : /fournisseur?id=FRN002
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import donnees, regles, ui
from src.format import date_fr, ecart_points, nombre, pct, tnd_compact, variation
from src.liens import identifiant_demande


def entete_vide(message: str, erreur: bool = False) -> None:
    ui.en_tete("Accueil › Fiche fournisseur", "Fiche fournisseur")
    (st.error if erreur else st.info)(message)
    st.page_link("pages/recherche.py", label="Aller à la recherche", icon=":material/search:")
    st.stop()


ident = identifiant_demande()
if ident is None:
    entete_vide("Choisis un fournisseur depuis la recherche.")
fiche = donnees.fournisseur_fiche(ident)
if fiche.empty:
    entete_vide(f"Aucun fournisseur ne porte l'identifiant {ident}.", erreur=True)

f = fiche.iloc[0]
ref = donnees.date_reference()
an, prec = ref.year, ref.year - 1


def manque(x) -> bool:
    return x is None or pd.isna(x)


def ligne_annee(annee: int):
    t = regles.score_fournisseurs(donnees.fournisseurs_annee(annee))
    t = t[t["fournisseur_id"] == ident]
    return t.iloc[0] if not t.empty else None


a, p = ligne_annee(an), ligne_annee(prec)
produits = donnees.fournisseur_produits(ident, an)
demande = donnees.fournisseur_demande(ident)
ruptures = {}
for pid, d in demande.groupby("produit_id"):
    jour = regles.date_rupture(d)
    if jour is not None and jour.year == an + 1 and jour.month <= 3:      # rupture au 1er trimestre
        ruptures[pid] = jour
achats = donnees.fournisseur_achats_mois(ident)
achats["mois"] = pd.to_datetime(achats["mois"])


def v(serie, col):
    return None if serie is None else serie[col]


score = v(a, "score")
niveau = regles.niveau_fournisseur(score)

# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
pastilles = [ui.badge(ui.e(f["pays"]), "bleu"), ui.badge("Local" if f["est_local"] == 1 else "Import", "gris")]
cats = produits["categorie"].value_counts()
if not cats.empty:
    pastilles.append(ui.badge(ui.e(cats.index[0]) + (f" + {len(cats) - 1}" if len(cats) > 1 else ""), "gris"))
if not achats.empty:
    pastilles.append(ui.badge(f"Partenaire depuis {achats['mois'].min():%Y}", "gris"))
if pd.notna(f["conditions_paiement"]):
    pastilles.append(ui.badge(f"Paiement : {ui.e(f['conditions_paiement'])}", "gris"))
liens = [f'<a class="ts-lien-bouton" href="#produits-fournis" target="_self">↗ {len(produits)} produits</a>']
if ruptures:
    liens.append(f'<a class="ts-lien-bouton" href="#produits-fournis" target="_self">↗ {len(ruptures)} rupture'
                 f'{"s" if len(ruptures) > 1 else ""} prévue{"s" if len(ruptures) > 1 else ""}</a>')
ui.en_tete("Accueil › Fiche fournisseur", f["nom_fournisseur"], ident, pastilles=pastilles, liens=liens)

# ---------------------------------------------------------------------------
# 2. À retenir
# ---------------------------------------------------------------------------
constats = []
if a is not None and not manque(a["fiabilite_reelle"]):
    constats.append(f"Annonce <b>{pct(f['fiabilite_annoncee'], 0)}</b> de ponctualité, en tient <b>{pct(a['fiabilite_reelle'], 0)}</b>"
                    f" en {an}")
if a is not None and not manque(a["delai_reel_moyen_j"]):
    txt = f"Délai réel <b>{nombre(a['delai_reel_moyen_j'])} j</b> pour {nombre(f['delai_annonce_j'])} annoncés"
    if p is not None and not manque(p["delai_reel_moyen_j"]):
        dd = round(a["delai_reel_moyen_j"]) - round(p["delai_reel_moyen_j"])
        if dd:
            txt += f", en {'hausse' if dd > 0 else 'baisse'} de {abs(dd)} j"
    constats.append(txt)
if ruptures:
    pr = produits[produits["id"].isin(ruptures)].sort_values("ca_ttc", ascending=False).iloc[0]
    rang = f", n°{int(pr['rang_categorie'])} de sa catégorie" if pd.notna(pr["rang_categorie"]) and pr["rang_categorie"] <= 3 else ""
    constats.append(f"{len(ruptures)} produit{'s' if len(ruptures) > 1 else ''} épuisé{'s' if len(ruptures) > 1 else ''} "
                    f"au T1 {an + 1}, dont <b>{ui.e(pr['nom_produit'])}</b>{rang}")
elif score is not None:
    constats.append(f"Score <b>{nombre(score)}/100</b> : {niveau}")
action = None
if a is not None and not manque(a["delai_reel_moyen_j"]) and round(a["delai_reel_moyen_j"]) > f["delai_annonce_j"]:
    action = f"planifier avec {nombre(a['delai_reel_moyen_j'])} j au lieu de {nombre(f['delai_annonce_j'])} j"
ton = {"à risque": "rouge", "à surveiller": "orange"}.get(niveau, "neutre")
ui.a_retenir(constats or [f"Aucun achat en {an}"], action, ton)

# ---------------------------------------------------------------------------
# 3. Chiffres clés
# ---------------------------------------------------------------------------
ui.section(f"Chiffres clés {an}")


def carte(label, col, valeur, bon_si_hausse=True, points=False, jours=False):
    x, y = v(a, col), v(p, col)
    if manque(x) or manque(y):
        delta = None
    elif points:
        delta = ecart_points(x, y)
    elif jours:
        dj = round(x) - round(y)
        delta = ("+" if dj >= 0 else "-") + f"{abs(dj)} j"
    else:
        delta = variation(x, y)
    s = ui.sens(round(x), round(y)) if jours and delta else ui.sens(x, y)
    return ui.kpi(label, valeur, ui.delta_html(delta, s, bon_si_hausse=bon_si_hausse, suffixe=f"vs {prec}"))


couleur_score = {"fiable": ui.VERT, "à surveiller": ui.ORANGE, "à risque": ui.ROUGE}.get(niveau, "#1F2A37")
carte_score = (f'<div class="ts-kpi" style="text-align:center"><div class="ts-kpi-label">Score</div>'
               f'<div style="font-size:2.6rem;font-weight:800;color:{couleur_score};line-height:1.1">'
               f'{"—" if manque(score) else nombre(score)}</div><div class="ts-kpi-note">sur 100 · {niveau or "—"}</div></div>')
ui.rangee_kpi([
    carte_score,
    carte("Achats HT", "montant_achete_ht", tnd_compact(v(a, "montant_achete_ht"))),
    carte("Bons de commande", "nb_commandes", nombre(v(a, "nb_commandes"))),
    carte("Délai réel moyen", "delai_reel_moyen_j", "—" if manque(v(a, "delai_reel_moyen_j")) else f"{nombre(a['delai_reel_moyen_j'])} j",
          bon_si_hausse=False, jours=True),
    carte("Réception complète", "taux_reception", pct(v(a, "taux_reception"), 0), points=True),
    carte("CA généré en aval", "ca_aval_ttc", tnd_compact(v(a, "ca_aval_ttc"))),
], colonnes=6)

# ---------------------------------------------------------------------------
# 4. Promesse et réalité
# ---------------------------------------------------------------------------
ui.section("Promesse et réalité")
g, d = st.columns([1, 1.7], gap="medium")
with g, st.container(border=True):
    ui.titre_carte("Le score en détail", "moyenne de 3 notes")
    if a is None:
        st.caption(f"Aucun achat en {an}.")
    else:
        ui.barres([("Ponctualité", a["ponctualite"], nombre(a["ponctualite"])),
                   ("Complétude", a["completude"], nombre(a["completude"])),
                   ("Qualité (rang des retours)", a["qualite"], nombre(a["qualite"]))], maximum=100)
        ecart = None if manque(a["fiabilite_reelle"]) else a["fiabilite_reelle"] - f["fiabilite_annoncee"]
        rouge = ecart is not None and ecart < donnees.SEUIL_ECART_FIABILITE
        st.markdown(
            '<div style="display:flex;justify-content:space-around;text-align:center;border-top:1px solid #E3E8EE;'
            'padding-top:.7rem;margin-top:.3rem">'
            f'<div><div class="ts-kpi-label">Annoncé</div><div style="font-size:1.6rem;font-weight:700">{pct(f["fiabilite_annoncee"], 0)}</div></div>'
            f'<div><div class="ts-kpi-label">Réel {an}</div><div style="font-size:1.6rem;font-weight:700;color:{ui.ROUGE if rouge else "#1F2A37"}">'
            f'{pct(a["fiabilite_reelle"], 0)}</div></div>'
            f'<div><div class="ts-kpi-label">Écart</div><div style="font-size:1.6rem;font-weight:700;color:{ui.ROUGE if rouge else "#1F2A37"}">'
            f'{"—" if ecart is None else ecart_points(a["fiabilite_reelle"], f["fiabilite_annoncee"], 0)}</div></div></div>',
            unsafe_allow_html=True)
        st.caption("Ponctualité : livraisons dans la tolérance (3 j ou 25 % du délai annoncé). Complétude : quantités "
                   "reçues / commandées. Qualité : 100 = le moins de retours parmi les fournisseurs. "
                   "80 et plus : fiable ; 60 à 79 : à surveiller.")

with d, st.container(border=True):
    ui.titre_carte("Achats et délai réel par mois", str(an))
    m = achats[achats["mois"].dt.year == an]
    m = m.set_index(m["mois"].dt.month)
    m = m.reindex(range(1, 13))
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=list(range(1, 13)), y=m["montant_ht"] / 1000, name="Achats (k TND, axe gauche)",
                         marker_color=ui.CLAIR, hovertemplate="%{y:,.1f} k TND<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=list(range(1, 13)), y=m["delai_reel_moyen_j"], name="Délai réel (j, axe droit)",
                             mode="lines+markers", line=dict(color=ui.ORANGE, width=2.5), marker=dict(size=6),
                             connectgaps=True, hovertemplate="%{y:,.1f} j<extra></extra>"), secondary_y=True)
    fig.add_trace(go.Scatter(x=[0.6, 12.4], y=[f["delai_annonce_j"]] * 2, name=f"Délai annoncé ({nombre(f['delai_annonce_j'])} j)",
                             mode="lines", line=dict(color=ui.VERT, width=2, dash="dash"), hoverinfo="skip"), secondary_y=True)
    ui.styler(fig, 310).update_xaxes(tickmode="array", tickvals=list(range(1, 13)), range=[0.4, 12.6],
                                     ticktext=["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    hauts = [x for x in [m["delai_reel_moyen_j"].max(), f["delai_annonce_j"]] if not manque(x)]
    fig.update_yaxes(rangemode="tozero", secondary_y=False)
    haut = 1.2 * max(hauts) if hauts else 10
    pas = 5 if haut <= 30 else 10 if haut <= 60 else 20                     # graduations rondes : 0, 10, 20 j…
    fig.update_yaxes(range=[0, haut], dtick=pas, showgrid=False, ticksuffix=" j", secondary_y=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Mois sans commande : pas de barre, la courbe relie les mois voisins.")

# ---------------------------------------------------------------------------
# 5. Portefeuille
# ---------------------------------------------------------------------------
ui.section("Portefeuille")
with st.container(border=True):
    st.markdown('<a id="produits-fournis"></a>', unsafe_allow_html=True)
    ui.titre_carte("Produits fournis", f"chiffres {an} · ruptures prévues au T1 {an + 1} · clic → fiche produit")
    if produits.empty:
        st.caption("Aucun produit référencé.")
    else:
        t = produits.copy()
        t["rupture"] = t["id"].map(ruptures)
        t = t.sort_values(["rupture", "ca_ttc"], ascending=[True, False], na_position="last")

        def stock(r) -> str:
            if manque(r["stock_depart"]):
                return "—"
            ton_s = "rouge" if pd.notna(r["rupture"]) else "orange" if r["stock_depart"] < 50 else "vert"
            return ui.badge(nombre(r["stock_depart"]), ton_s)

        ui.tableau([("Produit", ""), ("Catégorie", ""), (f"CA {an}", "num"), ("Marge", "num"), ("Retours", "num"),
                    ("Stock", "num"), ("Rupture prévue", "")],
                   [[ui.lien(r["nom_produit"], "produit", r["id"]), ui.e(r["categorie"]),
                     tnd_compact(r["ca_ttc"]).replace(" TND", "") if pd.notna(r["ca_ttc"]) else "—",
                     pct(r["taux_marge"], 0), pct(r["taux_retour"]), stock(r),
                     ui.badge(date_fr(r["rupture"]), "rouge") if pd.notna(r["rupture"]) else ui.badge(f"Aucune au T1", "gris")]
                    for _, r in t.head(12).iterrows()])
        if len(t) > 12:
            st.caption(f"12 premiers sur {len(t)} : ceux qui seront épuisés d'abord, puis par CA.")
