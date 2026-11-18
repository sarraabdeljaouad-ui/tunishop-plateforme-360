"""
TuniShop - Plateforme vue 360
Page Recherche (maquette 00) : résultats de la recherche floue, filtres par type avec leur nombre,
mots surlignés, score de correspondance, « Vouliez-vous dire ? » et recherches récentes.

Adresse : /recherche?q=carthgo
Auteure : Sarra Abdeljaouad
"""
import time

import pandas as pd
import streamlit as st

from src import donnees, recherche, ui
from src.format import mois_fr, nombre, pct
from src.liens import ouvrir

URL = {"Client": "client", "Produit": "produit", "Fournisseur": "fournisseur"}
ICONE = {"Client": "👤", "Produit": "▣", "Fournisseur": "🚚"}
PLURIEL = {"Client": "Clients", "Produit": "Produits", "Fournisseur": "Fournisseurs"}

q_url = st.query_params.get("q", "")
if st.session_state.get("_q_url") != q_url:          # arrivée par un lien : on recopie ?q= dans le champ
    st.session_state["_q_url"] = q_url
    st.session_state["saisie_recherche"] = q_url

saisie = st.session_state.get("saisie_recherche", "").strip()

# Identifiant exact : la fiche s'ouvre directement, sans passer par la liste
if saisie:
    cmd = recherche.commande_exacte(saisie)
    if cmd:
        ouvrir("Commande", cmd)
    t0 = time.perf_counter()
    index = donnees.index_recherche()
    tous = recherche.rechercher(saisie, index, limite=20)
    duree = time.perf_counter() - t0
    if len(tous) == 1 and tous.loc[0, "score"] == 100 and recherche._RE_ID.match(saisie):
        ouvrir(tous.loc[0, "type"], tous.loc[0, "id"])
else:
    tous, duree = pd.DataFrame(columns=["type"]), 0.0

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
if saisie:
    sugg = recherche.suggestion(saisie, recherche.vocabulaire(donnees.index_recherche()))
    sous = (f"Recherche tolérante aux fautes (rapidfuzz) · {len(tous)} résultat(s) en "
            f"{nombre(duree, 2)} s")
    if sugg:
        sous += f' · Vouliez-vous dire <a href="recherche?q={ui.e(sugg)}" target="_self"><b>« {ui.e(sugg)} »</b></a> ?'
    ui.en_tete("Accueil › Recherche", f"Résultats pour « {saisie} »", sous_titre=sous)
else:
    ui.en_tete("Accueil › Recherche", "Recherche",
               sous_titre="Un client, un produit, un fournisseur ou une commande. Les fautes de frappe sont tolérées.")

cs, cf = st.columns([3, 2], vertical_alignment="center")
cs.text_input("Rechercher", key="saisie_recherche", label_visibility="collapsed",
              placeholder="ex. « nexra evasion », « CLI004074 », « CMD0047890 »")
nb = tous["type"].value_counts() if len(tous) else pd.Series(dtype=int)
options = [f"Tous · {len(tous)}"] + [f"{PLURIEL[t]} · {nb[t]}" for t in ["Client", "Produit", "Fournisseur"] if t in nb]
choix = cf.segmented_control("Type", options, default=options[0], label_visibility="collapsed", key=f"filtre_{saisie}")
if st.session_state["saisie_recherche"].strip() != q_url:   # nouvelle saisie : on met l'adresse à jour
    st.query_params["q"] = st.session_state["saisie_recherche"].strip()

# ---------------------------------------------------------------------------
# Résultats | aide
# ---------------------------------------------------------------------------
g, d = st.columns([1.75, 1], gap="medium")
with g, st.container(border=True):
    if not saisie:
        st.caption("Tape un nom, un identifiant ou un SKU.")
    elif tous.empty:
        st.info("Aucun résultat. Essaie un autre mot, ou moins de mots.")
    else:
        recentes = st.session_state.setdefault("recherches_recentes", [])
        if saisie in recentes:
            recentes.remove(saisie)
        recentes.insert(0, saisie)
        del recentes[6:]

        filtre = None if not choix or choix.startswith("Tous") else \
            next(t for t, pl in PLURIEL.items() if choix.startswith(pl))
        res = tous if filtre is None else tous[tous["type"] == filtre]
        ui.titre_carte("Meilleurs résultats", "triés par score de correspondance")

        prod = donnees.etat_produits().set_index("produit_id")
        four = donnees.resume_fournisseurs().set_index("fournisseur_id")
        cli = donnees.resume_clients().set_index("client_id")

        def detail(r) -> str:
            morceaux = [ui.e(r["id"])]
            if r["type"] == "Produit" and r["id"] in prod.index:
                p = prod.loc[r["id"]]
                morceaux.append(ui.e(p["categorie"]))
                if pd.notna(p["stock_depart"]):
                    rouge = pd.notna(p["mois_rupture"])
                    stock = f"stock {nombre(p['stock_depart'])} u."
                    morceaux.append(f'<span style="color:{ui.ROUGE}">{stock}</span>' if rouge else stock)
                    if rouge:
                        morceaux.append(f'<span style="color:{ui.ROUGE}">épuisé prévu en {mois_fr(p["mois_rupture"])}</span>')
            elif r["type"] == "Fournisseur" and r["id"] in four.index:
                f = four.loc[r["id"]]
                morceaux += [ui.e(f["pays"]), f"{nombre(f['nb_produits'])} produits"]
                if pd.notna(f["fiabilite_reelle"]):
                    ecart = f["fiabilite_reelle"] - f["fiabilite_annoncee"]
                    txt = f"fiabilité réelle {pct(f['fiabilite_reelle'], 0)}"
                    morceaux.append(f'<span style="color:{ui.ORANGE}">{txt}</span>' if ecart < -0.05 else txt)
            elif r["type"] == "Client":
                morceaux.append(ui.e(r["detail"]))
                if r["id"] in cli.index:
                    morceaux.append(ui.e(cli.loc[r["id"], "segment_rfm"]))
            else:
                morceaux.append(ui.e(r["detail"]))
            return " · ".join(m for m in morceaux if m)

        lignes = "".join(
            f'<div class="ts-resultat"><div class="ic">{ICONE[r["type"]]}</div>'
            f'<div class="x"><b>{recherche.surligner(r["libelle"], saisie)}</b><br><span>{detail(r)}</span></div>'
            f'{ui.badge(r["type"], "gris")}'
            f'<a class="ts-lien-bouton" href="{URL[r["type"]]}?id={ui.e(r["id"])}" target="_self">'
            f'Ouvrir · {r["score"]:.0f} %</a></div>'
            for _, r in res.iterrows())
        st.markdown(lignes, unsafe_allow_html=True)

with d:
    with st.container(border=True):
        ui.titre_carte("Formats acceptés")
        ui.cle_valeur([("CLI004074", "fiche client"), ("PRD0094 ou SKU TS-03-00094", "fiche produit"),
                       ("FRN002", "fiche fournisseur"), ("CMD0047890", "fiche commande"),
                       ("Un nom, même mal orthographié", "liste de résultats")])
    recentes = st.session_state.get("recherches_recentes", [])
    if recentes:
        with st.container(border=True):
            ui.titre_carte("Recherches récentes")
            st.markdown(" ".join(f'<a href="recherche?q={ui.e(r)}" target="_self">{ui.badge(ui.e(r), "gris")}</a>'
                                 for r in recentes), unsafe_allow_html=True)
    ui.encadre("Un identifiant exact ouvre directement la fiche, sans passer par cette page.")
