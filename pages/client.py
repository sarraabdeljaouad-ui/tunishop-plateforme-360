"""
TuniShop - Plateforme vue 360
Fiche Client (maquette 02, v2) : bandeau « À retenir », chiffres clés de l'année, prédiction de churn
et ce qui pèse dans le modèle, CA mensuel, parcours RFM, dernières commandes, avis,
puis le détail (produits achetés, habitudes, expérience) dans un volet repliable.

Adresse : /client?id=CLI004074
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import donnees, regles, ui
from src.format import date_fr, ecart_points, nombre, pct, tnd, variation
from src.liens import identifiant_demande
from src.masquage import masquer


def entete_vide(message: str, erreur: bool = False) -> None:
    ui.en_tete("Accueil › Fiche client", "Fiche client")
    (st.error if erreur else st.info)(message)
    st.page_link("pages/recherche.py", label="Aller à la recherche", icon=":material/search:")
    st.stop()


ident = identifiant_demande()
if ident is None:
    entete_vide("Choisis un client depuis la recherche.")
idt = donnees.client_identite(ident)
if idt.empty:
    entete_vide(f"Aucun client ne porte l'identifiant {ident}.", erreur=True)

c = idt.iloc[0]
ref = donnees.date_reference()
an, prec = ref.year, ref.year - 1
annees = donnees.client_annees(ident).set_index("annee")
kpi = donnees.client_kpi(ident)
rfm = donnees.client_rfm(ident)
exp = donnees.client_experience(ident)
avis = donnees.client_avis(ident)
hab = donnees.client_habitudes(ident)
cmd = donnees.client_commandes(ident, 6)
k = kpi.iloc[0] if not kpi.empty else None
xp = exp.iloc[0] if not exp.empty else None
score = pd.notna(c["proba_churn"])
niveau = regles.niveau_risque(c["decile_risque"]) if score else None

COULEUR_SEGMENT = {"Champions": "vert", "Fidèles": "vert", "Fidèles potentiels": "bleu", "Nouveaux": "bleu",
                   "Prometteurs": "bleu", "À surveiller": "orange", "À risque": "orange",
                   "Hibernants": "rouge", "Perdus": "rouge"}
POINT = {"vert": ui.VERT, "bleu": "#1F4E79", "orange": ui.ORANGE, "rouge": ui.ROUGE, "gris": "#8A94A3"}


def manque(x) -> bool:
    return x is None or pd.isna(x)


def trimestre(d) -> str:
    d = pd.Timestamp(d)
    return f"T{(d.month - 1) // 3 + 1} {d:%y}"


# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
pastilles = [ui.badge(ui.e(c["ville"]), "bleu")]
if pd.notna(c["date_inscription"]):
    pastilles.append(ui.badge(f"Client depuis {pd.Timestamp(c['date_inscription']):%m/%Y}", "gris"))
if pd.notna(c["cluster"]):
    pastilles.append(ui.badge(f"Groupe : {ui.e(c['cluster'])}", "gris"))
if str(c["type_client"]).lower() != "particulier":
    pastilles.append(ui.badge(ui.e(c["type_client"]), "gris"))

liens = []
if k is not None:
    liens.append(f'<a class="ts-lien-bouton" href="#dernieres-commandes" target="_self">↗ {nombre(k["nb_commandes"])} commandes</a>')
liens.append(f'<a class="ts-lien-bouton" href="#ses-avis" target="_self">↗ {len(avis)} avis</a>')
transp = hab[hab["dimension"] == "transporteur"].sort_values("nb_commandes", ascending=False)
if not transp.empty:
    liens.append(ui.lien_bouton(transp.iloc[0]["valeur"], "transporteur", transp.iloc[0]["valeur"]))
ui.en_tete("Accueil › Fiche client", masquer(c["nom_complet"], c["type_client"]), ident, pastilles=pastilles, liens=liens)

# ---------------------------------------------------------------------------
# 2. À retenir
# ---------------------------------------------------------------------------
constats = []
if score:
    constats.append(f"<b>Risque de départ {niveau}</b> : {pct(c['proba_churn'], 0)}, décile {int(c['decile_risque'])} "
                    f"sur 10 (1 = le plus risqué)")
jours = (ref - pd.Timestamp(k["derniere_commande"])).days if k is not None and pd.notna(k["derniere_commande"]) else None
if jours is not None and jours >= regles.JOURS_SANS_COMMANDE:
    constats.append(f"Aucun achat depuis le <b>{date_fr(k['derniere_commande'])}</b> ({nombre(jours)} jours)")
if not cmd.empty:
    trois = cmd.head(3)
    n_ret = int((trois["retard_j"].fillna(0) > 0).sum())
    if n_ret:
        constats.append(f"{n_ret} de ses {len(trois)} dernières commandes livrées <b>en retard</b>")
if len(constats) < 3 and len(rfm) >= 2 and rfm.iloc[-2]["segment_rfm"] != rfm.iloc[-1]["segment_rfm"]:
    constats.append(f"Segment passé de « {ui.e(rfm.iloc[-2]['segment_rfm'])} » à « {ui.e(rfm.iloc[-1]['segment_rfm'])} »")
if not constats:
    constats.append("Rien d'inquiétant à la date des données")
ton = {"élevé": "rouge", "moyen": "orange"}.get(niveau, "neutre")
ui.a_retenir(constats, ui.e(c["action_recommandee"]) if pd.notna(c["action_recommandee"]) and score else None, ton)

# ---------------------------------------------------------------------------
# 3. Chiffres clés
# ---------------------------------------------------------------------------
ui.section(f"Chiffres clés {an}")
a = annees.loc[an] if an in annees.index else None
p = annees.loc[prec] if prec in annees.index else None


def v(serie, col):
    return None if serie is None else serie[col]


def carte(label, col, valeur, bon_si_hausse=True, points=False):
    x, y = v(a, col), v(p, col)
    delta = None if manque(x) or manque(y) else (ecart_points(x, y) if points else variation(x, y))
    return ui.kpi(label, valeur, ui.delta_html(delta, ui.sens(x, y), bon_si_hausse=bon_si_hausse, suffixe=f"vs {prec}"))


na, np_ = v(a, "note_moyenne"), v(p, "note_moyenne")
dn = None if manque(na) or manque(np_) else na - np_
ui.rangee_kpi([
    carte("CA", "ca_reconnu_ttc", tnd(v(a, "ca_reconnu_ttc"))),
    carte("Commandes", "nb_commandes", nombre(v(a, "nb_commandes"))),
    carte("Panier moyen", "panier_moyen_ttc", tnd(v(a, "panier_moyen_ttc"))),
    ui.kpi("Note moyenne donnée", "—" if manque(na) else f"{nombre(na, 1)} / 5",
           ui.delta_html(None if dn is None else ("+" if dn >= 0 else "-") + nombre(abs(dn), 1),
                         ui.sens(dn, 0) if dn is not None else 0, suffixe=f"vs {prec}")),
    carte("Taux de retour", "taux_retour", pct(v(a, "taux_retour")), bon_si_hausse=False, points=True),
], colonnes=5)
if a is None:
    st.info(f"Aucune commande en {an}.")

# ---------------------------------------------------------------------------
# 4. Prédiction et explication
# ---------------------------------------------------------------------------
ui.section("Prédiction et explication")
c1, c2, c3 = st.columns([1, 1.3, 1.7], gap="medium")
with c1, st.container(border=True):
    ui.titre_carte("Churn", "pbi.v_ml_scores_churn")
    if not score:
        st.info("Pas de score récent : le modèle ne note que les clients actifs à la date de scoring.")
    else:
        alerte = "alerte" if c["alerte_churn"] == 1 else "pas d'alerte"
        st.plotly_chart(ui.jauge(c["proba_churn"], f"Décile {int(c['decile_risque'])} · {alerte}"),
                        width="stretch", config={"displayModeBar": False})
        st.caption(f"Gradient boosting ({ui.e(c['version_modele'])}) · scoré au {date_fr(c['date_scoring'])}")
        test = donnees.client_churn_test(ident)
        if not test.empty:
            t = test.iloc[-1]
            juste = t["prediction"] == t["churn_reel"]
            st.markdown(ui.badge(f"Test {pd.Timestamp(t['date_observation']).year} : prédiction "
                                 + ("juste" if juste else "fausse"), "vert" if juste else "rouge"),
                        unsafe_allow_html=True)

with c2, st.container(border=True):
    ui.titre_carte("Ce qui pèse dans le score", "ana.ml03_importance")
    imp = donnees.importance_churn(5)
    if imp.empty or not score:
        st.caption("Pas de score pour ce client.")
    else:
        anciennete = (ref - pd.Timestamp(c["date_inscription"])).days if pd.notna(c["date_inscription"]) else None
        valeur = {"recence_j": ("Récence", f"{nombre(c['recence_j'])} j"),
                  "nb_livraisons": ("Livraisons reçues", nombre(xp["nb_livrees"]) if xp is not None else "—"),
                  "anciennete_j": ("Ancienneté", f"{nombre(anciennete)} j" if anciennete is not None else "—"),
                  "montant_reconnu_ttc": ("Montant acheté", tnd(c["montant_reconnu_ttc"])),
                  "segment_rfm": ("Segment RFM", ui.e(c["segment_rfm"])),
                  "frequence": ("Fréquence", f"{nombre(c['frequence'])} commandes")}
        part = imp["perte_auc"] / imp["perte_auc"].sum()
        lignes = []
        for (_, r), w in zip(imp.iterrows(), part):
            libelle, val = valeur.get(r["variable"], (r["variable"], "—"))
            lignes.append((f"{libelle} : {val}", w, pct(w, 0)))
        ui.barres(lignes, maximum=1)
        st.caption("Poids de chaque variable dans le modèle (perte d'AUC par permutation, test 2025), "
                   "avec la valeur de ce client. Ce n'est pas une contribution calculée client par client.")

with c3, st.container(border=True):
    ui.titre_carte("CA mensuel", f"{an} face à {prec}")
    vm = donnees.client_ventes_mois(ident)
    vm["mois"] = pd.to_datetime(vm["mois"])
    fig = go.Figure()
    for annee, couleur in [(prec, ui.CLAIR), (an, ui.FONCE)]:
        sel = vm[vm["mois"].dt.year == annee]
        serie = pd.Series(sel["ca_reconnu_ttc"].values, index=sel["mois"].dt.month).reindex(range(1, 13)).fillna(0)
        fig.add_trace(go.Scatter(x=list(range(1, 13)), y=serie.values, name=str(annee), mode="lines",
                                 line=dict(color=couleur, width=3),
                                 hovertemplate="%{y:,.0f} TND<extra>" + str(annee) + "</extra>"))
    ui.styler(fig, 260).update_xaxes(tickmode="array", tickvals=list(range(1, 13)),
                                     ticktext=["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Un mois sans achat compte 0 : l'absence d'achat est l'information.")

# ---------------------------------------------------------------------------
# 5. Historique
# ---------------------------------------------------------------------------
ui.section("Historique")
c1, c2, c3 = st.columns([1, 1.2, 1.3], gap="medium")
with c1, st.container(border=True):
    ui.titre_carte("Parcours RFM", "app.v_client_rfm")
    if rfm.empty:
        st.caption("Aucune observation RFM.")
    else:
        # un point par changement de segment (les trimestres identiques sont regroupés), 5 derniers
        r = rfm.sort_values("date_observation")
        etapes = r[r["segment_rfm"] != r["segment_rfm"].shift()].tail(5)
        points = "".join(
            f'<div style="text-align:center;flex:1"><div style="width:16px;height:16px;border-radius:99px;margin:0 auto;'
            f'border:3px solid {POINT[COULEUR_SEGMENT.get(s.segment_rfm, "gris")]};background:#FFF"></div>'
            f'<div style="font-size:.84rem;font-weight:600;color:{POINT[COULEUR_SEGMENT.get(s.segment_rfm, "gris")]};'
            f'margin-top:.3rem">{ui.e(s.segment_rfm)}</div>'
            f'<div style="font-size:.78rem;color:#8A94A3">{trimestre(s.date_observation)}</div></div>'
            for s in etapes.itertuples())
        st.markdown(f'<div style="display:flex;gap:.3rem;align-items:flex-start;position:relative;'
                    f'background:linear-gradient(#E3E8EE,#E3E8EE) no-repeat center 8px/80% 2px">{points}</div>',
                    unsafe_allow_html=True)
        der = r.iloc[-1]
        if len(etapes) >= 2:
            avant = etapes.iloc[-2]
            depuis = trimestre(etapes.iloc[-1]["date_observation"])
            phrase = f"« {avant['segment_rfm']} » avant le {depuis}, « {der['segment_rfm']} » depuis le {depuis}."
        else:
            phrase = f"« {der['segment_rfm']} » sur toute la période observée."
        ui.encadre(ui.e(phrase))

with c2, st.container(border=True):
    st.markdown('<a id="dernieres-commandes"></a>', unsafe_allow_html=True)
    ui.titre_carte("Dernières commandes", "clic → fiche")

    def livraison(r) -> str:
        if pd.isna(r["statut_livraison"]):
            return ui.badge(ui.e(r["libelle_statut"]), "gris")
        if r["est_livree"] != 1:
            return ui.badge(ui.e(str(r["statut_livraison"]).replace("_", " ")), "orange")
        if pd.notna(r["retard_j"]) and r["retard_j"] > 0:
            return ui.badge(f"+{nombre(r['retard_j'])} j", "rouge")
        return ui.badge("À temps", "vert")

    if cmd.empty:
        st.caption("Aucune commande.")
    else:
        ui.tableau([("Commande", ""), ("Date", ""), ("Montant", "num"), ("Livraison", "")],
                   [[ui.lien(r["id"], "commande", r["id"]), date_fr(r["date_commande"]),
                     tnd(r["montant_total_ttc"]), livraison(r)] for _, r in cmd.iterrows()])

with c3, st.container(border=True):
    st.markdown('<a id="ses-avis"></a>', unsafe_allow_html=True)
    ui.titre_carte("Ses avis", "thème · langue · note")
    if avis.empty:
        st.caption("Aucun avis commenté.")
    else:
        def ton_note(n):
            return "rouge" if n <= 2 else "orange" if n == 3 else "vert"
        ui.tableau([("Avis", ""), ("Thème", ""), ("Note", "num")],
                   [[f"<i>« {ui.e(r['texte_nettoye'])} »</i>"
                     + (" " + ui.badge("derja", "bleu") if str(r["langue"]).lower() == "derja" else "")
                     + f'<br><span style="color:#8A94A3;font-size:.8rem">{date_fr(r["date_avis"])}</span>',
                     ui.e(str(r["themes"]).split(";")[0]) if pd.notna(r["themes"]) else "—",
                     ui.badge(nombre(r["note"]), ton_note(r["note"])) if pd.notna(r["note"]) else "—"]
                    for _, r in avis.head(4).iterrows()])
        st.caption("La note moyenne des chiffres clés compte aussi les avis sans commentaire.")

# ---------------------------------------------------------------------------
# 6. Détail (replié)
# ---------------------------------------------------------------------------
with st.expander("Produits achetés, habitudes et expérience"):
    c1, c2 = st.columns([1.3, 1], gap="medium")
    with c1:
        prod = donnees.client_produits(ident, 6)
        if prod.empty:
            st.caption("Aucun produit acheté.")
        else:
            ui.tableau([("Produit", ""), ("Catégorie", ""), ("Quantité", "num"), ("Montant TTC", "num"), ("Dernier achat", "")],
                       [[ui.lien(r["nom_produit"], "produit", r["id"]), ui.e(r["categorie"]), nombre(r["quantite"]),
                         tnd(r["montant_ttc"]), date_fr(r["dernier_achat"])] for _, r in prod.iterrows()])
    with c2:
        lignes = []
        for dim in ["canal", "appareil", "mode de paiement"]:
            h = hab[hab["dimension"] == dim].sort_values("nb_commandes", ascending=False)
            if not h.empty:
                lignes.append([dim.capitalize(), f"{ui.e(h.iloc[0]['valeur'])} ({pct(h.iloc[0]['nb_commandes'] / h['nb_commandes'].sum(), 0)})"])
        if xp is not None:
            lignes += [["Coupons", f"{nombre(xp['nb_commandes_avec_coupon'])} commande(s) sur {nombre(xp['nb_commandes'])}"],
                       ["Livraisons en retard", f"{nombre(xp['nb_livrees_en_retard'])} sur {nombre(xp['nb_livrees'])}"],
                       ["Paiements échoués", f"{nombre(xp['nb_paiements_echoues'])} sur {nombre(xp['nb_tentatives_paiement'])}"],
                       ["Remboursements", f"{nombre(xp['nb_remboursements'])} ({tnd(xp['montant_rembourse_ttc'])})"]]
        ui.tableau([("Habitude", ""), ("Valeur", "")], lignes)
    if k is not None:
        st.caption(f"Depuis le début : {nombre(k['nb_commandes'])} commandes, {tnd(k['ca_reconnu_ttc'])} de CA reconnu, "
                   f"1re commande le {date_fr(k['premiere_commande'])}, dernière le {date_fr(k['derniere_commande'])}.")
