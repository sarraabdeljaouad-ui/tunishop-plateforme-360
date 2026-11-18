"""
TuniShop - Plateforme vue 360
format.py : affichage des nombres, montants, pourcentages et dates à la française.

Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import math

import pandas as pd


def _vide(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (not isinstance(v, str) and pd.isna(v))


def nombre(v, decimales: int = 0) -> str:
    """12450.5 -> '12 450' ; décimales avec une virgule."""
    if _vide(v):
        return "—"
    texte = f"{float(v):,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")


def tnd(v, decimales: int = 0) -> str:
    """Montant en dinars : '12 450 TND'."""
    return "—" if _vide(v) else f"{nombre(v, decimales)} TND"


def tnd_compact(v) -> str:
    """Grand montant lisible dans une carte KPI : '7,13 M TND', '845 k TND'."""
    if _vide(v):
        return "—"
    v = float(v)
    if abs(v) >= 1e6:
        return f"{nombre(v / 1e6, 2)} M TND"
    if abs(v) >= 1e4:
        return f"{nombre(v / 1e3, 0)} k TND"
    return tnd(v)


def pct(v, decimales: int = 1) -> str:
    """Part entre 0 et 1 -> '18,5 %'."""
    return "—" if _vide(v) else f"{nombre(100 * float(v), decimales)} %"


def variation(nouveau, ancien, decimales: int = 1) -> str | None:
    """Variation relative pour st.metric : '+8,2 %' (None si non calculable)."""
    if _vide(nouveau) or _vide(ancien) or float(ancien) == 0:
        return None
    v = (float(nouveau) - float(ancien)) / abs(float(ancien))
    signe = "+" if v >= 0 else "-"           # tiret ASCII : st.metric ne reconnaît pas le « − » typographique
    return f"{signe}{nombre(abs(100 * v), decimales)} %"


def ecart_points(nouveau, ancien, decimales: int = 1) -> str | None:
    """Écart entre deux parts, en points : '+1,2 pt'."""
    if _vide(nouveau) or _vide(ancien):
        return None
    v = 100 * (float(nouveau) - float(ancien))
    signe = "+" if v >= 0 else "-"
    return f"{signe}{nombre(abs(v), decimales)} pt"


def date_fr(v) -> str:
    """Date ou horodatage -> '14/11/2026' (ou '14/11/2026 15:09' s'il y a une heure)."""
    if _vide(v):
        return "—"
    t = pd.Timestamp(v)
    return t.strftime("%d/%m/%Y %H:%M") if (t.hour, t.minute) != (0, 0) else t.strftime("%d/%m/%Y")


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def mois_fr(v) -> str:
    """2026-03-01 -> 'mars 2026'."""
    if _vide(v):
        return "—"
    t = pd.Timestamp(v)
    return f"{MOIS[t.month - 1]} {t.year}"
