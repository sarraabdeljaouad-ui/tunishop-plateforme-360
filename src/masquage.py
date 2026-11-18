"""
TuniShop - Plateforme vue 360
masquage.py : masquage des noms des particuliers à l'affichage (comme dans les maquettes : « S*** M*** »).

- Seul l'affichage est masqué : la recherche fonctionne toujours sur les vrais noms.
- Les entreprises (raison sociale) ne sont pas masquées : c'est une information publique.
- Réglage dans .streamlit/secrets.toml :  [affichage]  masquer_noms = true  (false par défaut : noms en clair).

Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import streamlit as st

FORMES_SOCIETE = ("sarl", "suarl", "sa", "sas", "sasu", "eurl", "sci", "snc")


def actif() -> bool:
    try:
        return bool(st.secrets.get("affichage", {}).get("masquer_noms", False))
    except Exception:            # pas de secrets.toml : noms en clair
        return False


def est_entreprise(nom: str, type_client: str | None = None) -> bool:
    if type_client:
        return type_client.lower() != "particulier"
    return any(m.strip(".").lower() in FORMES_SOCIETE for m in str(nom).split())


def masquer(nom, type_client: str | None = None, forcer: bool | None = None) -> str:
    """'Riadh Belhadj' -> 'R*** B***' ; une entreprise reste en clair."""
    if nom is None or str(nom).strip() == "":
        return "—"
    nom = str(nom)
    masque = actif() if forcer is None else forcer
    if not masque or est_entreprise(nom, type_client):
        return nom
    return " ".join(f"{m[0]}***" for m in nom.split() if m)
