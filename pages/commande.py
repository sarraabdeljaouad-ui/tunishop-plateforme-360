"""
TuniShop - Plateforme vue 360
Fiche Commande (maquette 05, v2) : bandeau « À retenir », suivi en étapes (passée, payée, expédiée, livrée),
5 chiffres, lignes avec leur retour, avis laissé confronté aux faits, risque de retard prédit à l'expédition
et taux de retard réels du trajet (transporteur, région, jour d'expédition).

Adresse : /commande?id=CMD0047890
Auteure : Sarra Abdeljaouad
"""
import pandas as pd
import streamlit as st

from src import donnees, ui
from src.format import date_fr, nombre, pct, tnd
from src.liens import identifiant_demande
from src.masquage import masquer

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def entete_vide(message: str, erreur: bool = False) -> None:
    ui.en_tete("Accueil › Fiche commande", "Fiche commande")
    (st.error if erreur else st.info)(message)
    st.page_link("pages/recherche.py", label="Aller à la recherche", icon=":material/search:")
    st.stop()


ident = identifiant_demande()
if ident is None:
    entete_vide("Saisis un numéro de commande (CMD…) dans la recherche.")
fiche = donnees.commande_fiche(ident)
if fiche.empty:
    entete_vide(f"Aucune commande ne porte le numéro {ident}.", erreur=True)

c = fiche.iloc[0]
lignes = donnees.commande_lignes(ident)
avis = donnees.commande_avis(ident)
ref = donnees.date_reference()


def manque(x) -> bool:
    return x is None or pd.isna(x)


annulee = pd.notna(c["date_annulation"]) or str(c["statut_commande"]).lower().startswith("annul")
livree = not manque(c["est_livree"]) and int(c["est_livree"]) == 1
retard = int(c["retard_j"]) if livree and not manque(c["retard_j"]) and c["retard_j"] > 0 else 0
nb_retour = int(lignes["quantite_retournee"].sum()) if not lignes.empty else 0

pred = donnees.prediction_retard(c["livraison_id"]) if pd.notna(c["livraison_id"]) else pd.DataFrame()
pr = pred.iloc[0] if not pred.empty else None
seuil = donnees.seuil_retard()
alerte = pr is not None and seuil is not None and pr["proba_retard"] >= seuil

# ---------------------------------------------------------------------------
# 1. En-tête
# ---------------------------------------------------------------------------
pastilles = [ui.badge(date_fr(c["date_commande"]), "gris")]
if pd.notna(c["libelle_mode_paiement"]):
    pastilles.append(ui.badge(ui.e(c["libelle_mode_paiement"]), "gris"))
if pd.notna(c["gouvernorat"]):
    pastilles.append(ui.badge(ui.e(c["gouvernorat"]), "bleu"))
if pd.notna(c["libelle_canal"]):
    pastilles.append(ui.badge(ui.e(c["libelle_canal"]), "gris"))
pastilles.append(ui.badge(ui.e(c["libelle_statut"]), "orange" if annulee else "gris"))
liens = []
if pd.notna(c["client_id"]):
    liens.append(ui.lien_bouton(f"Client {masquer(c['client'], c['type_client'])}", "client", c["client_id"]))
if pd.notna(c["transporteur"]):
    liens.append(ui.lien_bouton(c["transporteur"], "transporteur", c["transporteur"]))
ui.en_tete("Accueil › Fiche commande", f"Commande {ident}", pastilles=pastilles, liens=liens)

# ---------------------------------------------------------------------------
# 2. À retenir
# ---------------------------------------------------------------------------
constats, action = [], None
if annulee:
    constats.append(f"Commande <b>annulée</b> le {date_fr(c['date_annulation'])}")
elif livree:
    constats.append(f"Livrée avec <b>{retard} jour{'s' if retard > 1 else ''} de retard</b>" if retard
                    else "Livrée <b>à temps</b>")
elif pd.notna(c["statut_livraison"]):
    constats.append(f"Colis <b>{ui.e(str(c['statut_livraison']).replace('_', ' '))}</b>, prévu le {date_fr(c['date_prevue'])}")
if pr is not None:
    p100 = pct(pr["proba_retard"], 0)
    if pr["source"] == "test":
        if alerte and retard:
            constats.append(f"Le modèle l'avait <b>prédit</b> à l'expédition ({p100})")
        elif alerte:
            constats.append(f"Le modèle prévoyait un retard ({p100}) : <b>fausse alerte</b>")
        elif retard:
            constats.append(f"Le modèle <b>ne l'avait pas vu</b> ({p100}, seuil {pct(seuil, 0)})")
    elif alerte:
        constats.append(f"Risque de retard prédit : <b>{p100}</b>")
        action = "prévenir le client"
if nb_retour:
    motifs = ", ".join(sorted({str(m).lower() for m in lignes.loc[lignes["quantite_retournee"] > 0, "motif_retour"].dropna()}))
    constats.append(f"{nb_retour} article{'s' if nb_retour > 1 else ''} <b>retourné{'s' if nb_retour > 1 else ''}</b>"
                    + (f" ({ui.e(motifs)})" if motifs else ""))
liv_neg = avis[avis["themes"].fillna("").str.contains("Livraison") & (avis["polarite_globale"] == "négatif")]
if not liv_neg.empty:
    a0 = liv_neg.iloc[0]
    constats.append(f"Avis {nombre(a0['note'])}/5 sur la livraison, "
                    + ("<b>confirmé par les faits</b>" if retard else "<b>non confirmé</b> : livrée à temps"))
ton = "rouge" if retard or (alerte and not livree and not annulee) else "orange" if nb_retour or annulee else "neutre"
ui.a_retenir(constats[:3] or ["Commande sans incident"], action, ton)

# ---------------------------------------------------------------------------
# 3. Suivi
# ---------------------------------------------------------------------------
with st.container(border=True):
    ui.titre_carte("Suivi")
    etapes = [("Passée", date_fr(c["date_commande"]), "ok")]
    if pd.notna(c["date_paiement"]):
        etapes.append(("Payée", date_fr(c["date_paiement"]), "ok"))
    elif "livraison" in str(c["libelle_mode_paiement"]).lower():
        etapes.append(("Payée", "à la livraison", "ok" if livree else "attente"))
    else:
        etapes.append(("Payée", "non payée", "annule" if annulee else "attente"))
    if annulee:
        etapes.append(("Annulée", date_fr(c["date_annulation"]), "annule"))
    else:
        exp = date_fr(c["date_expedition"]) + (f" · {c['transporteur']}" if pd.notna(c["transporteur"]) else "")
        etapes.append(("Expédiée", exp if pd.notna(c["date_expedition"]) else "à venir",
                       "ok" if pd.notna(c["date_expedition"]) else "attente"))
        prevu = f" · prévu {date_fr(c['date_prevue'])}" if pd.notna(c["date_prevue"]) else ""
        if livree:
            etapes.append(("Livrée", date_fr(c["date_livraison_colis"]) + prevu, "ko" if retard else "ok"))
        elif str(c["statut_livraison"]).lower().startswith("echec"):
            etapes.append(("Livraison", "en échec" + prevu, "ko"))
        else:
            etapes.append(("Livrée", "à venir" + prevu, "attente"))
    ui.suivi(etapes)

# ---------------------------------------------------------------------------
# 4. Chiffres
# ---------------------------------------------------------------------------
delai = c["delai_livraison_j"]
ui.rangee_kpi([
    ui.kpi("Montant TTC", tnd(c["montant_total_ttc"]),
           note=f"dont remise {tnd(c['remise_coupon_ttc'])}" if c["remise_coupon_ttc"] and c["remise_coupon_ttc"] > 0 else ""),
    ui.kpi("Articles", nombre(c["nb_articles"]), note=f"{nombre(c['nb_lignes'])} produit(s)"),
    ui.kpi("Frais de livraison", tnd(c["frais_livraison_ttc"])),
    ui.kpi("Délai réel", "—" if manque(delai) or not livree else f"{nombre(delai)} j",
           ui.delta_html(f"+{retard} j", 1, bon_si_hausse=False, suffixe="vs prévu") if retard
           else (ui.delta_html("à temps", 0, suffixe="") if livree else "")),
    ui.kpi("Retour / remboursement",
           f"{nb_retour} article{'s' if nb_retour > 1 else ''}" if nb_retour
           else (tnd(c["montant_rembourse_ttc"]) if c["montant_rembourse_ttc"] else "Aucun"),
           note=(f"{tnd(c['montant_rembourse_ttc'])} remboursés" if nb_retour and c["montant_rembourse_ttc"]
                 else "remboursés, sans article retourné" if c["montant_rembourse_ttc"] else "")),
], colonnes=5)

# ---------------------------------------------------------------------------
# 5. Lignes et avis | risque de retard prédit
# ---------------------------------------------------------------------------
g, d = st.columns([1.6, 1], gap="medium")
with g, st.container(border=True):
    ui.titre_carte("Lignes", "clic → fiche produit")

    def statut(r) -> str:
        if r["quantite_retournee"] > 0:
            motif = f" · {ui.e(str(r['motif_retour']).lower())}" if pd.notna(r["motif_retour"]) else ""
            return ui.badge(f"Retourné{motif}", "rouge")
        if annulee:
            return ui.badge("Annulé", "gris")
        return ui.badge("Livré", "vert") if livree else ui.badge("En cours", "orange")

    ui.tableau([("Produit", ""), ("Qté", "num"), ("Prix unit.", "num"), ("Total", "num"), ("Statut", "")],
               [[ui.lien(r["nom_produit"], "produit", r["id"]), nombre(r["quantite"]), tnd(r["prix_unitaire_ttc"]),
                 tnd(r["montant_ttc"]), statut(r)] for _, r in lignes.iterrows()])
    if not avis.empty:
        st.markdown("**Avis laissé" + ("s" if len(avis) > 1 else "") + "**")
        for _, a in avis.iterrows():
            theme = str(a["themes"]).split(";")[0] if pd.notna(a["themes"]) else "—"
            txt = f"<i>« {ui.e(a['texte_nettoye'])} »</i> · {nombre(a['note'])}/5 · thème {ui.e(theme)}"
            if str(a["langue"]).lower() == "derja":
                txt += " " + ui.badge("derja", "bleu")
            if "Livraison" in str(a["themes"]) and a["polarite_globale"] == "négatif":
                txt += " " + (ui.badge(f"confirmé : retard mesuré {retard} j", "vert") if retard
                              else ui.badge("non confirmé : livrée à temps", "orange") if livree else "")
            ui.encadre(txt)

with d, st.container(border=True):
    ui.titre_carte("Risque de retard prédit", "pbi.v_ml_retard · pbi.v_ml_scores_retard")
    if pr is None:
        st.caption("Pas de prédiction pour cette livraison : le modèle note les expéditions de 2025 "
                   "et les colis en transit.")
    else:
        quand = (f"Prédit à l'expédition du {date_fr(pr['date_expedition'])}" if pr["source"] == "test"
                 else f"Colis en transit · scoré le {date_fr(pr['date_scoring'])}")
        s = seuil if seuil is not None else 0.5
        st.plotly_chart(ui.jauge(pr["proba_retard"], quand, rouge=s, orange=s),
                        width="stretch", config={"displayModeBar": False})
        if pr["source"] == "test" and pd.notna(pr["retard_reel"]):
            juste = bool(alerte) == bool(pr["retard_reel"])
            st.markdown(ui.badge("✓ Prédiction juste" if juste else "✕ Prédiction fausse", "vert" if juste else "rouge"),
                        unsafe_allow_html=True)
        st.caption(f"Alerte au-delà de {pct(seuil, 0)} : seuil du modèle retenu (régression logistique), "
                   "choisi sur la validation.")

    # Ce qu'on sait du trajet : taux de retard réels de l'année d'expédition
    if pd.notna(c["date_expedition"]):
        an_exp = pd.Timestamp(c["date_expedition"]).year
        fx = donnees.taux_retard_facteurs(an_exp)
        jour = JOURS[pd.Timestamp(c["date_expedition"]).weekday()]

        def taux(facteur, valeur):
            t = fx[(fx["facteur"] == facteur) & (fx["valeur"].astype(str).str.lower() == str(valeur).lower())]
            return None if t.empty else float(t["taux"].iloc[0])

        moy = taux("ensemble", "toutes")
        lignes_f = [(f"Transporteur {c['transporteur']}", taux("transporteur", c["transporteur"])),
                    (f"Région {c['region']}", taux("region", c["region"])),
                    (f"Expédié un {jour}", taux("jour", jour))]
        lignes_f = [(l, t) for l, t in lignes_f if t is not None]
        if lignes_f and moy is not None:
            st.markdown("**Ce qu'on sait de ce trajet**")
            m = max([t for _, t in lignes_f] + [moy]) * 1.15
            ui.barres([(l, t, pct(t, 0)) for l, t in lignes_f] + [(f"Moyenne {an_exp}", moy, pct(moy, 0))], maximum=m)
            st.caption(f"Taux de retard réels des livraisons {an_exp}. Ce ne sont pas les poids du modèle.")
