"""
TuniShop - Plateforme vue 360
liens.py : une seule table de correspondance entre un type d'entité et sa page.

Chaque fiche a sa propre adresse : /client?id=CLI004074. Un lien est donc un vrai lien,
partageable, qu'on peut ouvrir dans un nouvel onglet.

Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import streamlit as st

PAGES = {
    "Client": "pages/client.py",
    "Produit": "pages/produit.py",
    "Fournisseur": "pages/fournisseur.py",
    "Commande": "pages/commande.py",
    "Transporteur": "pages/transporteur.py",
}
ICONES = {
    "Client": ":material/person:",
    "Produit": ":material/inventory_2:",
    "Fournisseur": ":material/local_shipping:",
    "Commande": ":material/receipt_long:",
    "Transporteur": ":material/conveyor_belt:",
}


def lien(type_entite: str, identifiant: str, libelle: str) -> None:
    """Affiche un lien vers la fiche d'une entité."""
    st.page_link(PAGES[type_entite], label=libelle, icon=ICONES[type_entite],
                 query_params={"id": identifiant})


def ouvrir(type_entite: str, identifiant: str) -> None:
    """Ouvre directement la fiche d'une entité (arrête le script en cours)."""
    st.switch_page(PAGES[type_entite], query_params={"id": identifiant})


def identifiant_demande() -> str | None:
    """Identifiant lu dans l'adresse de la page (?id=...), ou None."""
    v = st.query_params.get("id")
    return v.strip() if v else None
