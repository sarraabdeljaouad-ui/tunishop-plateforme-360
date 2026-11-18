"""
TuniShop - Plateforme vue 360
Fiche Transporteur (maquette 06, v2) : bandeau « À retenir », 5 chiffres de l'année face à la précédente,
retard par semestre face à la moyenne, retard par région, comparaison des transporteurs,
colis en cours à risque de retard.

Adresse : /transporteur?id=SahelLog (nom) ou /transporteur?id=TRP03 (identifiant)
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import donnees, ui
from src.format import date_fr, ecart_points, nombre, pct, variation
from src.liens import identifiant_demande


def entete_vide(message: str, erreur: bool = False) -> None:
    ui.en_tete("Accueil › Fiche transporteur", "Fiche transporteur")
    (st.error if erreur else st.info)(message)
    st.page_link("pages/recherche.py", label="Aller à la recherche", icon=":material/search:")
    st.stop()


ident = identifiant_demande()
ref_t = donnees.transporteurs()
if ident is None:
    ui.en_tete("Accueil › Fiche transporteur", "Fiche transporteur")
    st.caption("Choisis un transporteur.")
    st.markdown(" ".join(ui.lien_bouton(r["nom_transporteur"], "transporteur", r["transporteur_id"])
                         for _, r in ref_t.iterrows()), unsafe_allow_html=True)
    st.stop()
trouve = ref_t[(ref_t["transporteur_id"].str.upper() == ident.upper()) |
               (ref_t["nom_transporteur"].str.lower() == ident.lower())]
if trouve.empty:
    entete_vide(f"Aucun transporteur ne correspond à « {ident} ».", erreur=True)

t = trouve.iloc[0]
nom = t["nom_transporteur"]
ref = donnees.date_reference()
an, prec = ref.year, ref.year - 1
tab_an = donnees.transporteurs_annee(an).set_index("transporteur")
tab_prec = donnees.transporteurs_annee(prec).set_index("transporteur")
a = tab_an.loc[nom] if nom in tab_an.index else None
p = tab_prec.loc[nom] if nom in tab_prec.index else None
moy = tab_an.loc["ensemble"] if "ensemble" in tab_an.index else None
sem = donnees.retard_semestres()
regions = donnees.retard_regions(nom, an)
colis = donnees.colis_en_cours(nom)
seuil = donnees.seuil_retard()
a_risque = colis[colis["alerte_retard"] == 1] if not colis.empty else colis


def manque(x) -> bool:
    return x is None or pd.isna(x)


def v(serie, col):
    return None if serie is None else serie[col]


def libelle_sem(an_, s_) -> str:
    return f"S{int(s_)} {int(an_) % 100:02d}"


# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
pastilles = []
if pd.notna(t["couverture"]):
    pastilles.append(ui.badge(f"Couverture {ui.e(str(t['couverture']).lower())}", "gris"))
if pd.notna(t["cout_base_ht"]):
    pastilles.append(ui.badge(f"Coût de base {nombre(t['cout_base_ht'], 1)} TND HT", "gris"))
liens = [f'<a class="ts-lien-bouton" href="#colis-en-cours" target="_self">↗ {len(colis)} colis en cours</a>',
         '<a class="ts-lien-bouton" href="#comparaison" target="_self">↗ Comparer</a>']
ui.en_tete("Accueil › Fiche transporteur", nom, t["transporteur_id"], pastilles=pastilles, liens=liens)

# ---------------------------------------------------------------------------
# 2. À retenir
# ---------------------------------------------------------------------------
constats = []
autres = tab_an.drop(index="ensemble", errors="ignore").sort_values("taux_reel", ascending=False)
if a is not None and moy is not None and not manque(a["taux_reel"]):
    rang = list(autres.index).index(nom) + 1
    debut = "Le plus en retard" if rang == 1 else "Le moins en retard" if rang == len(autres) else f"{rang}e sur {len(autres)}"
    constats.append(f"{debut} : <b>{pct(a['taux_reel'])}</b> contre {pct(moy['taux_reel'])} en moyenne")
s_t = sem[sem["transporteur"] == nom].sort_values(["annee", "semestre"]).tail(4)
if len(s_t) >= 3:
    x = s_t["taux"].tolist()
    hausse = all(x[i] < x[i + 1] for i in range(len(x) - 1))
    baisse = all(x[i] > x[i + 1] for i in range(len(x) - 1))
    depuis = libelle_sem(s_t.iloc[0]["annee"], s_t.iloc[0]["semestre"]).replace(" ", " 20")
    # Rupture : un saut d'au moins 10 pt, au moins deux fois plus grand que chacune des autres variations
    sauts = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    i_max = max(range(len(sauts)), key=lambda i: abs(sauts[i]))
    autres_sauts = [abs(d) for i, d in enumerate(sauts) if i != i_max]
    rupture = abs(sauts[i_max]) >= 0.10 and all(abs(sauts[i_max]) >= 2 * d for d in autres_sauts)
    if rupture:
        quand = libelle_sem(s_t.iloc[i_max + 1]["annee"], s_t.iloc[i_max + 1]["semestre"]).replace(" ", " 20")
        debut = "Rupture" if sauts[i_max] > 0 else "Amélioration nette"
        constats.append(f"{debut} au <b>{quand}</b> : retard passé de {pct(x[i_max], 0)} à {pct(x[i_max + 1], 0)}")
    elif hausse:
        constats.append(f"Dégradation continue depuis <b>{depuis}</b>")
    elif baisse:
        constats.append(f"Amélioration continue depuis <b>{depuis}</b>")
    else:
        constats.append(f"{pct(x[-1])} au dernier semestre, contre {pct(x[-2])} au précédent")
if not regions.empty and a is not None and not manque(a["taux_reel"]):
    r0 = regions.iloc[0]
    if r0["taux"] >= 1.25 * a["taux_reel"]:
        constats.append(f"Retards concentrés dans la région <b>{ui.e(r0['region'])}</b> ({pct(r0['taux'])})")
    else:
        constats.append("Retards répartis, sans région dominante")
action = f"prévenir les {len(a_risque)} clients des colis à risque" if len(a_risque) > 1 else \
    "prévenir le client du colis à risque" if len(a_risque) == 1 else None
ecart = None if a is None or moy is None or manque(a["taux_reel"]) else a["taux_reel"] - moy["taux_reel"]
ton = "rouge" if ecart is not None and ecart > 0.05 else "orange" if ecart is not None and ecart > 0 else "neutre"
ui.a_retenir(constats[:3] or [f"Aucune livraison en {an}"], action, ton)

# ---------------------------------------------------------------------------
# 3. Chiffres de l'année
# ---------------------------------------------------------------------------
ui.section(f"Chiffres clés {an}")


def carte(label, col, valeur, bon_si_hausse=True, points=False, jours=False, note=""):
    x, y = v(a, col), v(p, col)
    if manque(x) or manque(y):
        return ui.kpi(label, valeur, note=note)
    if points:
        delta = ecart_points(x, y)
    elif jours:
        d = round(x - y, 1)
        if d == 0:                                       # pas d'évolution : pas de flèche
            return ui.kpi(label, valeur, ui.delta_html("stable", 0, suffixe=f"vs {prec}"))
        delta = ("+" if d > 0 else "-") + nombre(abs(d), 1) + " j"
    else:
        delta = variation(x, y)
    return ui.kpi(label, valeur, ui.delta_html(delta, ui.sens(x, y), bon_si_hausse=bon_si_hausse, suffixe=f"vs {prec}"))


ecart_modele = None if a is None or manque(a["taux_predit"]) or manque(a["taux_reel"]) else a["taux_predit"] - a["taux_reel"]
note_pred = "" if ecart_modele is None else \
    f"le modèle {'sous-estime' if ecart_modele < 0 else 'surestime'} de {nombre(abs(100 * ecart_modele), 1)} pt"
ui.rangee_kpi([
    carte(f"Colis livrés {an}", "colis_livres", nombre(v(a, "colis_livres"))),
    carte("Retard réel", "taux_reel", pct(v(a, "taux_reel")), bon_si_hausse=False, points=True),
    ui.kpi("Retard prédit", pct(v(a, "taux_predit")),
           note=f'<span style="color:{ui.ORANGE}">{note_pred}</span>' if ecart_modele is not None and abs(ecart_modele) >= 0.02
           else note_pred),
    carte("Retard moyen", "retard_moyen_j", "—" if manque(v(a, "retard_moyen_j")) else f"{nombre(a['retard_moyen_j'], 1)} j",
          bon_si_hausse=False, jours=True, note="parmi les colis en retard"),
    carte("Avis négatifs livraison", "part_avis_negatifs", pct(v(a, "part_avis_negatifs")), bon_si_hausse=False, points=True),
], colonnes=5)
st.caption("Retard prédit : moyenne des probabilités du modèle à l'expédition (test 2025). "
           "Avis négatifs : part des avis commentés qui critiquent la livraison.")

# ---------------------------------------------------------------------------
# 4. Semestres | régions | comparaison
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns([1.1, 1, 1.15], gap="medium")
with c1, st.container(border=True):
    ui.titre_carte("Retard par semestre", "face à la moyenne")
    s_m = sem[sem["transporteur"] == "ensemble"].sort_values(["annee", "semestre"])
    s_all = sem[sem["transporteur"] == nom].sort_values(["annee", "semestre"])
    s_all = s_all[s_all["annee"] >= prec]
    s_m = s_m[s_m["annee"] >= prec]
    fig = go.Figure([
        go.Bar(name=nom, x=[libelle_sem(r.annee, r.semestre) for r in s_all.itertuples()], y=s_all["taux"],
               marker_color=ui.FONCE, hovertemplate="%{y:.1%}<extra></extra>"),
        go.Bar(name="Moyenne", x=[libelle_sem(r.annee, r.semestre) for r in s_m.itertuples()], y=s_m["taux"],
               marker_color="#CBD3DD", hovertemplate="%{y:.1%}<extra></extra>")])
    ui.styler(fig, 260).update_yaxes(tickformat=".0%", rangemode="tozero")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with c2, st.container(border=True):
    ui.titre_carte("Retard par région", str(an))
    if regions.empty:
        st.caption(f"Aucune livraison en {an}.")
    else:
        m = regions["taux"].max() * 1.1
        ui.barres([(r["region"], r["taux"], pct(r["taux"])) for _, r in regions.iterrows()], maximum=m)
        st.caption("Colis livrés en retard, parmi les colis livrés de la région.")

with c3, st.container(border=True):
    st.markdown('<a id="comparaison"></a>', unsafe_allow_html=True)
    ui.titre_carte("Comparaison des transporteurs", str(an))
    if autres.empty:
        st.caption("Aucune donnée.")
    else:
        def ton_reel(x):
            if moy is None or manque(x):
                return "gris"
            return "rouge" if x > moy["taux_reel"] + 0.03 else "orange" if x > moy["taux_reel"] else "vert"

        ident_de = dict(zip(ref_t["nom_transporteur"], ref_t["transporteur_id"]))
        lignes = []
        for n_, r in autres.iterrows():
            lib = f"<b>{ui.e(n_)}</b>" if n_ == nom else ui.lien(n_, "transporteur", ident_de.get(n_, n_))
            lignes.append([lib, ui.badge(pct(r["taux_reel"]), ton_reel(r["taux_reel"])), pct(r["taux_predit"]),
                           pct(r["part_avis_negatifs"])])
        ui.tableau([("Transporteur", ""), ("Réel", "num"), ("Prédit", "num"), ("Avis nég.", "num")], lignes)

# ---------------------------------------------------------------------------
# 5. Colis en cours
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown('<a id="colis-en-cours"></a>', unsafe_allow_html=True)
    ui.titre_carte("Colis en cours, du plus risqué au moins risqué",
                   f"pbi.v_ml_scores_retard · au {date_fr(ref)} · alerte au-delà de {pct(seuil, 0)}")
    if colis.empty:
        st.caption("Aucun colis en transit à la date des données.")
    else:
        def ton_p(x):
            return "rouge" if seuil is not None and x >= max(0.5, seuil) else "orange" if seuil is not None and x >= seuil else "gris"

        ui.tableau([("Commande", ""), ("Client", ""), ("Destination", ""), ("Expédié le", ""), ("Prévu le", ""),
                    ("Risque", "num"), ("", "")],
                   [[ui.lien(r["id"], "commande", r["id"]),
                     ui.lien(r["client_id"], "client", r["client_id"]) if pd.notna(r["client_id"]) else "—",
                     ui.e(r["gouvernorat"] if pd.notna(r["gouvernorat"]) else r["region"]), date_fr(r["date_expedition"]),
                     date_fr(r["date_prevue"]), ui.badge(nombre(r["proba_retard"], 2), ton_p(r["proba_retard"])),
                     f'<a class="ts-lien-bouton" href="commande?id={ui.e(r["id"])}" target="_self">Fiche</a>']
                    for _, r in colis.head(10).iterrows()])
        st.caption(f"{len(a_risque)} colis en alerte sur {len(colis)} en transit"
                   + (" · 10 premiers affichés" if len(colis) > 10 else ""))
