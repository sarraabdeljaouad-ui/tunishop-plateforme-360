"""
TuniShop - Plateforme vue 360
Page d'accueil (maquette 01, v2) : recherche, visite guidée en 3 cartes, l'année en chiffres,
un tableau à onglets « à traiter » et le CA prévu par catégorie.

Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import streamlit as st

from src import donnees, recherche, regles, ui
from src.format import date_fr, ecart_points, mois_fr, nombre, pct, tnd, tnd_compact, variation
from src.liens import ouvrir

ref = donnees.date_reference()
an, prec = ref.year, ref.year - 1

n_churn, churn = donnees.alertes_churn(8)
n_eleve = donnees.churn_risque_eleve()
n_rupt, rupt = donnees.alertes_rupture(8)
n_four, four = donnees.alertes_fournisseurs(8)
n_colis, colis = donnees.alertes_colis(8)

# ---------------------------------------------------------------------------
# 1. En-tête et recherche
# ---------------------------------------------------------------------------
ui.en_tete("TuniShop · Vue 360", "Bonjour, que cherches-tu ?",
           sous_titre="Client, produit, fournisseur ou commande. Les fautes de frappe sont tolérées.")

def _chercher() -> None:
    st.session_state["_q_accueil"] = st.session_state.get("saisie_accueil", "").strip()


exemple_cli = churn.iloc[0]["id"] if not churn.empty else "CLI004074"
exemple_cmd = colis.iloc[0]["id"] if not colis.empty else "CMD0047890"
st.text_input("Rechercher", key="saisie_accueil", label_visibility="collapsed", on_change=_chercher,
              placeholder=f"Essaie « nexra evasion », « {exemple_cli} » ou « {exemple_cmd} »")
q = st.session_state.pop("_q_accueil", None) or st.query_params.get("q", "")
if q:
    st.query_params.clear()
    cmd = recherche.commande_exacte(q)
    if cmd:
        ouvrir("Commande", cmd)
    exact = recherche.rechercher(q, donnees.index_recherche()) if recherche._RE_ID.match(q) else pd.DataFrame()
    if len(exact) == 1:
        ouvrir(exact.loc[0, "type"], exact.loc[0, "id"])
    st.switch_page("pages/recherche.py", query_params={"q": q})

# Visite guidée : les trois cas les plus parlants du moment, cliquables
cartes = []
if not churn.empty:
    r = churn.iloc[0]
    cartes.append(("Un client sur le départ", f"{r['id']} · churn {pct(r['proba_churn'], 0)}", "client", r["id"]))
if not rupt.empty:
    r = rupt.iloc[0]
    jour = regles.date_rupture(donnees.produit_demande(r["id"]))
    quand = f"rupture le {date_fr(jour)}" if jour is not None else f"rupture en {mois_fr(r['mois_rupture'])}"
    cartes.append(("Un produit bientôt épuisé", f"{r['produit']} · {quand}", "produit", r["id"]))
if not four.empty:
    r = four.iloc[0]
    cartes.append(("Un fournisseur qui promet trop",
                   f"{pct(r['fiabilite_annoncee'], 0)} annoncé, {pct(r['fiabilite_reelle'], 0)} réel", "fournisseur", r["id"]))
if cartes:
    for col, (i, (titre, detail, page, ident)) in zip(st.columns(len(cartes), gap="medium"), enumerate(cartes, 1)):
        with col:
            ui.carte_visite(i, titre, detail, page, ident)

# ---------------------------------------------------------------------------
# 2. L'année en chiffres
# ---------------------------------------------------------------------------
ui.section(f"L'année {an} en chiffres")
ens = donnees.vue_ensemble().set_index("annee")
if an in ens.index and prec in ens.index:
    a, p = ens.loc[an], ens.loc[prec]

    def carte(label, col, valeur, bon_si_hausse=True, points=False):
        delta = ecart_points(a[col], p[col]) if points else variation(a[col], p[col])
        return ui.kpi(label, valeur, ui.delta_html(delta, ui.sens(a[col], p[col]), bon_si_hausse=bon_si_hausse,
                                                    suffixe=f"vs {prec}"))

    dn = a["note_moyenne"] - p["note_moyenne"]
    ui.rangee_kpi([
        carte("Chiffre d'affaires", "ca_reconnu_ttc", tnd_compact(a["ca_reconnu_ttc"])),
        carte("Commandes", "commandes_reconnues", nombre(a["commandes_reconnues"])),
        carte("Clients actifs", "clients_actifs", nombre(a["clients_actifs"])),
        carte("Panier moyen", "panier_moyen_ttc", tnd(a["panier_moyen_ttc"])),
        carte("Livraisons en retard", "taux_retard", pct(a["taux_retard"]), bon_si_hausse=False, points=True),
        ui.kpi("Note moyenne", f"{nombre(a['note_moyenne'], 1)} / 5",
               ui.delta_html(("+" if dn >= 0 else "-") + nombre(abs(dn), 2), ui.sens(dn, 0), suffixe=f"vs {prec}")),
    ], colonnes=6)

# ---------------------------------------------------------------------------
# 3. À traiter (onglets) | CA prévu par catégorie
# ---------------------------------------------------------------------------
ui.section(f"À traiter, à la date des données ({date_fr(ref)})")


def ton_score(v: float) -> str:
    return "rouge" if v >= 0.7 else "orange" if v >= 0.5 else "gris"


def bouton_fiche(page: str, ident: str) -> str:
    return f'<a class="ts-lien-bouton" href="{page}?id={ui.e(ident)}" target="_self">Fiche</a>'


g, d = st.columns([1.6, 1], gap="medium")
with g, st.container(border=True):
    o1, o2, o3, o4 = st.tabs([f"Churn · {nombre(n_eleve)}", f"Ruptures T1 · {nombre(n_rupt)}",
                              f"Fournisseurs · {nombre(n_four)}", f"Colis à risque · {nombre(n_colis)}"])
    with o1:
        lignes = []
        for _, r in churn.head(5).iterrows():
            seg = r["segment_rfm"] if pd.isna(r["segment_precedent"]) or r["segment_precedent"] == r["segment_rfm"] \
                else f"{r['segment_precedent']} → {r['segment_rfm']}"
            lignes.append([ui.lien(r["id"], "client", r["id"]), ui.e(seg), date_fr(r["derniere_commande"]),
                           ui.e(str(r["action_recommandee"]).split(":")[0].strip())        # le détail est sur la fiche
                           if pd.notna(r["action_recommandee"]) else "—",
                           ui.badge(nombre(r["proba_churn"], 2), ton_score(r["proba_churn"])), bouton_fiche("client", r["id"])])
        ui.tableau([("Client", ""), ("Segment", ""), ("Dernier achat", ""), ("Action recommandée", ""),
                    ("Score", "num"), ("", "")], lignes)
        st.caption(f"pbi.v_ml_scores_churn · déciles 1-2 (risque élevé), triés par CA en jeu · 5 premiers sur "
                   f"{nombre(n_eleve)}. L'alerte du modèle (seuil 0,37) concerne {nombre(n_churn)} clients.")
    with o2:
        lignes = [[ui.lien(r["produit"], "produit", r["id"]), nombre(r["stock_depart"]), nombre(r["demande_t1"]),
                   ui.badge(mois_fr(r["mois_rupture"]), "rouge" if pd.Timestamp(r["mois_rupture"]).month == 1 else "orange"),
                   f"Commander chez {ui.lien(r['nom_fournisseur'], 'fournisseur', r['fournisseur_id'])}"
                   if pd.notna(r["fournisseur_id"]) else "—", bouton_fiche("produit", r["id"])]
                  for _, r in rupt.head(5).iterrows()]
        ui.tableau([("Produit", ""), ("Stock", "num"), ("Demande T1", "num"), ("Épuisé en", ""),
                    ("Action recommandée", ""), ("", "")], lignes)
        st.caption(f"pbi.v_ml_scores_demande · sans réapprovisionnement · 5 premiers sur {nombre(n_rupt)}")
    with o3:
        lignes = [[ui.lien(r["fournisseur"], "fournisseur", r["id"]), ui.e(r["pays"]), pct(r["fiabilite_annoncee"], 0),
                   pct(r["fiabilite_reelle"], 0), ui.badge(ecart_points(r["ecart_fiabilite"], 0), "rouge"),
                   f"Planifier avec {nombre(r['delai_reel_moyen_j'])} j au lieu de {nombre(r['delai_annonce_j'])} j",
                   bouton_fiche("fournisseur", r["id"])]
                  for _, r in four.head(5).iterrows()]
        if lignes:
            ui.tableau([("Fournisseur", ""), ("Pays", ""), ("Annoncée", "num"), ("Réelle", "num"), ("Écart", "num"),
                        ("Action recommandée", ""), ("", "")], lignes)
        else:
            st.success("Aucun fournisseur sous le seuil.")
        st.caption("app.v_fournisseur_fiche · retard compté au-delà de 3 j ou 25 % du délai annoncé · écart ≥ 5 pt · "
                   "action : délai réel moyen à utiliser pour planifier les commandes")
    with o4:
        lignes = [[ui.lien(r["id"], "commande", r["id"]), ui.e(r["transporteur"]), ui.e(r["region"]),
                   date_fr(r["date_expedition"]), ui.badge(nombre(r["proba_retard"], 2), ton_score(r["proba_retard"])),
                   "Prévenir le client", bouton_fiche("commande", r["id"])]
                  for _, r in colis.head(5).iterrows()]
        if lignes:
            ui.tableau([("Commande", ""), ("Transporteur", ""), ("Région", ""), ("Expédié le", ""), ("Risque", "num"),
                        ("Action recommandée", ""), ("", "")], lignes)
        else:
            st.success("Aucun colis en alerte.")
        st.caption(f"pbi.v_ml_scores_retard · alerte_retard = 1 · 5 premiers sur {nombre(n_colis)}")

with d, st.container(border=True):
    vc = donnees.ventes_categories(an)
    ui.titre_carte(f"CA {an + 1} prévu par catégorie", "ana.ml_pred_ventes_2026")
    if vc.empty:
        st.info("Prévision non publiée.")
    else:
        vc = vc.sort_values("prevu", ascending=False)
        ui.barres([(r["categorie"], r["prevu"], tnd_compact(r["prevu"]).replace(" TND", ""))
                   for _, r in vc.iterrows()])
        total_p, total_r = vc["prevu"].sum(), vc["reel"].sum()
        ui.cle_valeur([(f"Total prévu {an + 1}",
                        f"{tnd_compact(total_p)} {ui.delta_html(variation(total_p, total_r), ui.sens(total_p, total_r), suffixe='')}")])
        st.caption(f"Variation face au réel {an} de la série du modèle (pbi.v_ml_ventes), "
                   "à environ 1 % du CA reconnu.")
