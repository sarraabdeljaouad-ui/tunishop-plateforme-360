"""
TuniShop - Plateforme vue 360
ui.py : composants visuels communs à toutes les pages, d'après les maquettes (dossier Maquettes).

Les couleurs et les formes générales sont dans .streamlit/config.toml. Ce module ajoute ce que le
thème ne couvre pas : cartes KPI, badges, tableaux à liens, en-tête de page, titres de carte,
jauge, style des graphiques Plotly, menu latéral (recherche et fraîcheur des données).

Les composants renvoient du HTML simple ; les valeurs sont échappées (html.escape) avant affichage.
Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

VERSION = "v0.14.1"

# Palette des maquettes
FONCE, CANARD, CLAIR = "#0F4C5C", "#1B7F8C", "#9CC3C9"
ROUGE, VERT, ORANGE, BLEU, GRIS = "#B42318", "#1E7B4F", "#B45309", "#1F4E79", "#5B6675"
TONS = {  # fond, texte
    "rouge": ("#FDECEC", "#B42318"), "vert": ("#E3F4EA", "#1E7B4F"), "orange": ("#FFF2DC", "#B45309"),
    "bleu": ("#E6F0FA", "#1F4E79"), "gris": ("#EEF0F3", "#344054"), "canard": ("#DCEBEE", "#0F4C5C"),
}

CSS = """
<style>
/* largeur et respiration de la page */
.block-container {padding-top: 2.2rem; max-width: 1500px;}
/* cartes : conteneurs à bord (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px; border-color: #E3E8EE; background: #FFFFFF;}
/* en-tête de page */
.ts-fil {font-size: .86rem; color: #5B6675; margin-bottom: .1rem;}
.ts-titre {font-size: 2rem; font-weight: 700; color: #1F2A37; line-height: 1.2; margin: 0;}
.ts-titre .ts-id {white-space: nowrap; font-size: 1.35rem; font-weight: 400; color: #8A94A3;}
.ts-sous-titre {color: #5B6675; font-size: 1.02rem; margin: .25rem 0 .2rem 0;}
.ts-pastilles {display: flex; flex-wrap: wrap; gap: .45rem; margin: .55rem 0 .3rem 0;}
/* badges */
.ts-badge {display: inline-block; padding: .14rem .62rem; border-radius: 999px; font-size: .86rem;
           font-weight: 600; white-space: nowrap; line-height: 1.5;}
/* liens d'en-tête (boutons contour) */
.ts-liens {display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; margin-top: 1.4rem;}
.ts-lien-bouton {display: inline-block; border: 1px solid #D0D7DE; border-radius: 10px; padding: .32rem .8rem;
                 color: #0F4C5C !important; text-decoration: none !important; font-size: .92rem; background: #FFF;}
.ts-lien-bouton:hover {background: #F4F6F9;}
/* cartes KPI */
.ts-kpis {display: grid; gap: .9rem; margin: .4rem 0 .9rem 0;}
.ts-kpi {border: 1px solid #E3E8EE; border-radius: 14px; padding: .95rem 1.1rem; background: #FFF;}
.ts-kpi-label {color: #5B6675; font-size: .92rem; line-height: 1.25;}
.ts-kpi-valeur {font-size: clamp(1.25rem, 1.7vw, 1.75rem); font-weight: 700; color: #1F2A37; margin: .2rem 0 .1rem 0; white-space: nowrap;}
.ts-kpi-delta {font-size: .84rem; color: #5B6675; white-space: nowrap;}
.ts-kpi-note {font-size: .85rem; color: #5B6675;}
/* titre de carte : titre à gauche, source à droite */
.ts-carte-titre {display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-bottom: .35rem;}
.ts-carte-titre b {font-size: 1.12rem; color: #1F2A37;}
.ts-carte-titre span {font-size: .84rem; color: #8A94A3; text-align: right;}
/* tableaux */
.ts-table {width: 100%; border-collapse: collapse; font-size: .95rem;}
.ts-table th {text-align: left; font-size: .78rem; letter-spacing: .04em; text-transform: uppercase; color: #5B6675;
              font-weight: 600; padding: .45rem .55rem; border-bottom: 1px solid #E3E8EE;}
.ts-table td {padding: .55rem .55rem; border-bottom: 1px solid #EEF1F4; vertical-align: middle;}
.ts-table td.num, .ts-table th.num {text-align: right; white-space: nowrap;}
.ts-table a {color: #0F4C5C; text-decoration: underline; text-underline-offset: 2px;}
.ts-table tr.fort td {font-weight: 700;}
/* barres horizontales (volumes) */
.ts-barre {background: #EEF1F4; border-radius: 99px; height: 9px; width: 100%;}
.ts-barre > div {background: #1B7F8C; border-radius: 99px; height: 9px;}
/* encadrés */
.ts-kv {display: flex; justify-content: space-between; gap: 1rem; padding: .32rem 0; font-size: .97rem;}
.ts-kv b {white-space: nowrap;}
.ts-section {display: flex; align-items: center; gap: .8rem; margin: 1.3rem 0 .6rem 0;
  font-size: .8rem; font-weight: 650; letter-spacing: .08em; color: #5B6675; text-transform: uppercase;}
.ts-section::after {content: ""; flex: 1; height: 1px; background: #E3E8EE;}
.ts-retenir {display: flex; gap: 0; border-radius: 14px; padding: .95rem 1.1rem; margin: .4rem 0 .2rem 0;
  border: 1px solid; font-size: .97rem; line-height: 1.45;}
.ts-retenir .t {font-weight: 700; letter-spacing: .05em; padding-right: 1.1rem; white-space: nowrap;}
.ts-retenir .c {flex: 1; padding: 0 1.1rem; border-left: 1px solid rgba(31,42,55,.12);}
.ts-retenir.rouge {background: #FDF1F0; border-color: #F4C7C3;} .ts-retenir.rouge .t {color: #B42318;}
.ts-retenir.orange {background: #FFF7EA; border-color: #F6D9A8;} .ts-retenir.orange .t {color: #B45309;}
.ts-retenir.neutre {background: #F4F8FA; border-color: #D5E3E7;} .ts-retenir.neutre .t {color: #0F4C5C;}
.ts-visite {display: flex; align-items: center; gap: .9rem; border: 1px solid #E3E8EE; border-radius: 14px;
  padding: .8rem 1rem; background: #FFF; height: 100%;}
.ts-visite .n {flex: none; width: 2.1rem; height: 2.1rem; border-radius: 99px; background: #0F4C5C; color: #FFF;
  display: flex; align-items: center; justify-content: center; font-weight: 700;}
.ts-visite .x {flex: 1; line-height: 1.3;} .ts-visite .x b {display: block; font-size: 1rem;}
.ts-visite .x span {color: #5B6675; font-size: .9rem;}
.ts-statut {border: 1px solid #E3E8EE; border-radius: 12px; background: #FFF; padding: .7rem .85rem;
  font-size: .88rem; color: #5B6675; line-height: 1.7;}
.ts-statut b {color: #1F2A37;}
.ts-resultat {display: flex; align-items: center; gap: .9rem; padding: .7rem .2rem; border-bottom: 1px solid #EEF1F4;}
.ts-resultat .ic {flex: none; width: 2.3rem; height: 2.3rem; border-radius: 10px; background: #EEF3F5;
  display: flex; align-items: center; justify-content: center; font-size: 1.05rem;}
.ts-resultat .x {flex: 1; line-height: 1.35;} .ts-resultat .x b {font-size: 1.02rem;}
.ts-resultat .x span {color: #5B6675; font-size: .88rem;}
.ts-resultat mark {background: #FFE9A8; padding: 0 .12rem; border-radius: 3px;}
.ts-id-dessous {font-size: 1.05rem; color: #8A94A3; margin-top: .1rem;}
.ts-suivi {display: flex; align-items: flex-start; padding: .4rem 0 .2rem 0;
  background: linear-gradient(#CFE3E6,#CFE3E6) no-repeat center 15px/80% 3px;}
.ts-suivi .e {flex: 1; text-align: center;}
.ts-suivi .p {width: 30px; height: 30px; border-radius: 99px; margin: 0 auto; color: #FFF; font-weight: 800;
  display: flex; align-items: center; justify-content: center; font-size: .95rem;}
.ts-suivi .l {font-weight: 650; margin-top: .35rem;} .ts-suivi .d {font-size: .86rem; color: #5B6675;}
.ts-encadre {border-left: 4px solid #1B7F8C; background: #F4F8FA; border-radius: 8px; padding: .75rem 1rem; margin: .5rem 0;}
.ts-encadre.alerte {border-left-color: #D97706; background: #FFF8EC;}
/* menu latéral : pied de page */
.ts-pied {font-size: .88rem; color: #5B6675; line-height: 1.55;}
.ts-pied b {color: #1F2A37;}
.ts-signature {font-size: .82rem; color: #8A94A3; margin-top: .4rem;}
</style>
"""


def e(v) -> str:
    """Échappe une valeur pour l'afficher dans du HTML ('—' si vide)."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "—"
    return html.escape(str(v))


# ---------------------------------------------------------------------------
# Thème et menu latéral
# ---------------------------------------------------------------------------
def appliquer_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.logo("assets/logo_tunishop.svg", size="large", icon_image="assets/icone_tunishop.svg")


def _recherche_laterale() -> None:
    q = st.session_state.get("recherche_laterale", "")
    if q:
        st.session_state["recherche_laterale"] = ""
        st.session_state["_aller_recherche"] = q


def menu_lateral(fraicheur: dict | None) -> None:
    """Champ de recherche (ouvre la page Recherche avec ?q=) et carte d'état de la chaîne."""
    with st.sidebar:
        st.text_input("Rechercher", placeholder="Rechercher…", key="recherche_laterale",
                      label_visibility="collapsed", on_change=_recherche_laterale)
        q = st.session_state.pop("_aller_recherche", None)
        if q:
            st.switch_page("pages/recherche.py", query_params={"q": q})
        st.markdown("<br>", unsafe_allow_html=True)
        if fraicheur:
            etat = badge("● Chaîne OK", "vert") if fraicheur["ok"] else badge("● Chaîne à vérifier", "orange")
            st.markdown(
                f"""<div class="ts-statut">{etat} {e(fraicheur['execution'])}<br>
                Données au <b>{e(fraicheur['date_donnees'])}</b><br>
                Comparaison : {e(fraicheur['comparaison'])}
                {"<br>" + e(fraicheur['mode']) if fraicheur['mode'].startswith("Instantané") else ""}</div>
                <div class="ts-signature">Sarra Abdeljaouad · {VERSION}</div>""",
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Briques HTML
# ---------------------------------------------------------------------------
def badge(texte: str, ton: str = "gris") -> str:
    fond, couleur = TONS.get(ton, TONS["gris"])
    return f'<span class="ts-badge" style="background:{fond};color:{couleur}">{texte}</span>'


def lien(texte: str, page: str, ident: str) -> str:
    """Lien vers une fiche : même onglet, adresse partageable (/client?id=...)."""
    return f'<a href="{page}?id={html.escape(str(ident))}" target="_self">{e(texte)}</a>'


def lien_bouton(texte: str, page: str, ident: str) -> str:
    return f'<a class="ts-lien-bouton" href="{page}?id={html.escape(str(ident))}" target="_self">↗ {e(texte)}</a>'


def sens(x, y) -> int:
    """+1 si x > y, -1 si x < y, 0 sinon ou si une valeur manque (fonctionne avec les types numpy)."""
    try:
        if x is None or y is None or pd.isna(x) or pd.isna(y):
            return 0
    except (TypeError, ValueError):
        return 0
    return int(x > y) - int(x < y)


def delta_html(texte: str | None, sens: int, bon_si_hausse: bool = True, suffixe: str = "vs 2024") -> str:
    """Variation colorée : ▲ / ▼, vert si favorable, rouge sinon. sens = +1, -1 ou 0."""
    if not texte:
        return ""
    if sens == 0:
        return f'<span class="ts-kpi-delta">{e(texte)} {e(suffixe)}</span>'
    favorable = (sens > 0) == bon_si_hausse
    couleur = VERT if favorable else ROUGE
    fleche = "▲" if sens > 0 else "▼"
    return (f'<span class="ts-kpi-delta"><span style="color:{couleur};font-weight:600">{fleche} {e(texte)}</span> '
            f'{e(suffixe)}</span>')


def kpi(label: str, valeur: str, delta: str = "", note: str = "") -> str:
    """Une carte KPI (HTML). delta : sortie de delta_html ; note : petite ligne grise."""
    bas = delta or (f'<span class="ts-kpi-note">{note}</span>' if note else "")
    return (f'<div class="ts-kpi"><div class="ts-kpi-label">{e(label)}</div>'
            f'<div class="ts-kpi-valeur">{e(valeur)}</div>{bas}</div>')


def rangee_kpi(cartes: list[str], colonnes: int | None = None) -> None:
    n = colonnes or len(cartes)
    st.markdown(f'<div class="ts-kpis" style="grid-template-columns:repeat({n}, minmax(0,1fr))">'
                + "".join(cartes) + "</div>", unsafe_allow_html=True)


def en_tete(fil: str, titre: str, ident: str = "", sous_titre: str = "", pastilles: list[str] | None = None,
            liens: list[str] | None = None) -> None:
    """Fil d'Ariane, titre (et identifiant gris), sous-titre, pastilles, liens à droite."""
    g, d = st.columns([3, 2], vertical_alignment="top")
    with g:
        st.markdown(
            f'<div class="ts-fil">{e(fil)}</div>'
            + (f'<div class="ts-titre">{e(titre)}' + (f' <span class="ts-id">· {e(ident)}</span>' if ident else "") + "</div>"
             if len(titre) + len(ident) <= 48 else          # titre long : l'identifiant passe dessous, en petit
             f'<div class="ts-titre">{e(titre)}</div><div class="ts-id-dessous">{e(ident)}</div>')
            + (f'<div class="ts-sous-titre">{sous_titre}</div>' if sous_titre else "")
            + (f'<div class="ts-pastilles">{"".join(pastilles)}</div>' if pastilles else ""),
            unsafe_allow_html=True)
    with d:
        if liens:
            st.markdown(f'<div class="ts-liens">{"".join(liens)}</div>', unsafe_allow_html=True)


def titre_carte(titre: str, source: str = "") -> None:
    st.markdown(f'<div class="ts-carte-titre"><b>{e(titre)}</b><span>{e(source)}</span></div>',
                unsafe_allow_html=True)


def tableau(entetes: list[tuple[str, str]], lignes: list[list[str]], classes: list[str] | None = None) -> None:
    """Tableau HTML. entetes = [(libellé, 'num' ou '')] ; les cellules sont déjà du HTML sûr."""
    th = "".join(f'<th class="{c}">{e(t)}</th>' for t, c in entetes)
    corps = ""
    for i, l in enumerate(lignes):
        cls = f' class="{classes[i]}"' if classes and classes[i] else ""
        corps += f"<tr{cls}>" + "".join(f'<td class="{c}">{v}</td>' for v, (_, c) in zip(l, entetes)) + "</tr>"
    st.markdown(f'<table class="ts-table"><thead><tr>{th}</tr></thead><tbody>{corps}</tbody></table>',
                unsafe_allow_html=True)


def barres(lignes: list[tuple[str, float, str]], maximum: float | None = None) -> None:
    """Volumes en barres horizontales : (libellé, valeur, valeur affichée)."""
    m = maximum or max((v for _, v, _ in lignes), default=1) or 1
    html_l = "".join(
        f'<tr><td style="width:38%">{e(l)}</td><td style="width:47%"><div class="ts-barre">'
        f'<div style="width:{100 * v / m:.1f}%"></div></div></td><td class="num">{e(t)}</td></tr>'
        for l, v, t in lignes)
    st.markdown(f'<table class="ts-table" style="border:none"><tbody>{html_l}</tbody></table>', unsafe_allow_html=True)


def section(titre: str) -> None:
    """Intertitre en capitales avec un filet (« L'ANNÉE 2025 EN CHIFFRES »)."""
    st.markdown(f'<div class="ts-section">{e(titre)}</div>', unsafe_allow_html=True)


def a_retenir(constats: list[str], action: str | None = None, ton: str = "neutre") -> None:
    """Bandeau de conclusion : 3 ou 4 constats (HTML sûr), puis l'action. ton : rouge, orange ou neutre."""
    blocs = [f'<div class="c">{c}</div>' for c in constats[:3]]
    if action:
        blocs.append(f'<div class="c">Action : <b>{action}</b></div>')
    st.markdown(f'<div class="ts-retenir {ton}"><div class="t">À RETENIR</div>{"".join(blocs)}</div>',
                unsafe_allow_html=True)


def carte_visite(numero: int, titre: str, detail: str, page: str, ident: str) -> None:
    """Carte cliquable de la visite guidée (accueil)."""
    st.markdown(f'<div class="ts-visite"><div class="n">{numero}</div><div class="x"><b>{e(titre)}</b>'
                f'<span>{e(detail)}</span></div>'
                f'<a class="ts-lien-bouton" href="{page}?id={html.escape(str(ident))}" target="_self">Voir</a></div>',
                unsafe_allow_html=True)


def suivi(etapes: list[tuple[str, str, str]]) -> None:
    """Frise de suivi : (libellé, détail, état) ; état = ok, ko, attente ou annule."""
    style = {"ok": (VERT, "✓"), "ko": (ROUGE, "!"), "attente": ("#B9C3CE", "…"), "annule": ("#5B6675", "✕")}
    html_e = "".join(
        f'<div class="e"><div class="p" style="background:{style[etat][0]}">{style[etat][1]}</div>'
        f'<div class="l">{e(lib)}</div><div class="d">{e(det)}</div></div>' for lib, det, etat in etapes)
    st.markdown(f'<div class="ts-suivi">{html_e}</div>', unsafe_allow_html=True)


def cle_valeur(paires: list[tuple[str, str]]) -> None:
    """Lignes « libellé ...... valeur » ; la valeur est du HTML sûr (gras, couleur)."""
    st.markdown("".join(f'<div class="ts-kv"><span>{e(c)}</span><b>{v}</b></div>' for c, v in paires),
                unsafe_allow_html=True)


def encadre(texte_html: str, alerte: bool = False) -> None:
    st.markdown(f'<div class="ts-encadre{" alerte" if alerte else ""}">{texte_html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Graphiques
# ---------------------------------------------------------------------------
def styler(fig: go.Figure, hauteur: int = 300, legende: bool = True) -> go.Figure:
    fig.update_layout(
        height=hauteur, margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#5B6675", size=12), separators=", ",
        showlegend=legende, legend=dict(orientation="h", y=1.08, x=0, yanchor="bottom", font=dict(size=13, color="#344054")),
        bargap=0.25, hoverlabel=dict(bgcolor="#FFFFFF"))
    fig.update_xaxes(showgrid=False, linecolor="#E3E8EE", ticks="")
    fig.update_yaxes(gridcolor="#EEF1F4", zeroline=False, ticks="")
    return fig


def jauge(valeur: float, legende: str, hauteur: int = 210, rouge: float = 0.6, orange: float = 0.3) -> go.Figure:
    """Demi-jauge 0-100 % : rouge à partir de `rouge`, orange à partir de `orange`, vert en dessous."""
    couleur = ROUGE if valeur >= rouge else ORANGE if valeur >= orange else VERT
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=100 * valeur, number=dict(suffix=" %", valueformat=".0f", font=dict(size=40, color="#1F2A37")),
        domain=dict(x=[0, 1], y=[0.2, 1]),               # le bas (20 %) est réservé à la légende : pas de chevauchement
        gauge=dict(shape="angular", axis=dict(range=[0, 100], visible=False), bar=dict(color=couleur, thickness=0.32),
                   bgcolor="#EEF1F5", borderwidth=0)))
    fig.update_layout(height=hauteur, margin=dict(l=20, r=20, t=10, b=0), paper_bgcolor="#FFFFFF",
                      font=dict(family="Inter, Segoe UI, sans-serif"),
                      annotations=[dict(text=legende, x=0.5, y=0, yanchor="bottom", xref="paper", yref="paper",
                                        showarrow=False, font=dict(size=13, color="#5B6675"))])
    return fig
