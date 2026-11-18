"""
TuniShop - Plateforme vue 360
donnees.py : la seule porte vers les données. Une fonction par bloc de page.

Règles :
    - aucune requête SQL dans les pages : elles appellent ces fonctions ;
    - aucun calcul métier ici : les KPI sont calculés dans les vues SQL (app, pbi, ana).
      Ces fonctions filtrent, trient et limitent, rien de plus ;
    - toutes les vues lues sont dans TuniShop_ANALYTICS (les vues app lisent le DWH elles-mêmes) ;
    - pour la démo en ligne (étape 10), seul ce fichier changera de source.

Auteure : Sarra Abdeljaouad
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import recherche
from src.db import lire

BASE = "analytics"
SEUIL_ECART_FIABILITE = -0.05   # alerte fournisseur : fiabilité réelle plus de 5 points sous l'annoncée
                                # (fiabilité réelle = sans retard au-delà de la tolérance, vue app v1.2)


def _sans_dates_techniques(df: pd.DataFrame) -> pd.DataFrame:
    """Les dates des membres techniques du DWH (« Inconnu », « Non applicable », en 1900) deviennent vides.
    Exemple : une commande sans annulation pointe sur la date technique 02/01/1900, pas sur NULL.
    Les colonnes de dates lues par pyodbc (datetime.date) sont au passage converties en dates pandas."""
    import datetime as _dt
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if s.dtype == object:
            premier = s.dropna().iloc[0] if s.notna().any() else None
            if not isinstance(premier, (_dt.date, _dt.datetime)):
                continue
            s = pd.to_datetime(s, errors="coerce")
        elif not pd.api.types.is_datetime64_any_dtype(s):
            continue
        df[col] = s.where(s.dt.year > 1900)
    return df


def _lire(sql: str, **params) -> pd.DataFrame:
    return _sans_dates_techniques(lire(sql, base=BASE, params=params or None))


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="Chargement de l'index de recherche…")
def index_recherche() -> pd.DataFrame:
    """Index de recherche (clients, produits, fournisseurs) prêt pour recherche.rechercher."""
    vue = _lire("SELECT type_entite, id, libelle, detail, sku FROM app.v_index_recherche")
    return recherche.index_depuis_vue(vue)


# ---------------------------------------------------------------------------
# Accueil
# ---------------------------------------------------------------------------
def vue_ensemble() -> pd.DataFrame:
    """Chiffres globaux par année (CA reconnu, commandes, clients actifs, panier, retard, note)."""
    return _lire("SELECT * FROM pbi.v_eda_vue_ensemble ORDER BY annee")


def prevision_ca() -> pd.DataFrame:
    """Prévision du CA TTC de l'année suivante, totalisée par année (vide si non publiée)."""
    return _lire("""SELECT YEAR(mois) AS annee, SUM(prevision_ca_ttc) AS prevision_ca_ttc,
                           COUNT(DISTINCT categorie) AS categories
                    FROM ana.ml_pred_ventes_2026 GROUP BY YEAR(mois)""")


def ventes_categories(annee_reelle: int) -> pd.DataFrame:
    """CA TTC réel d'une année et prévision de l'année suivante, par catégorie (pour le graphique de l'accueil)."""
    reel = _lire("""SELECT categorie, SUM(ca_reel_ttc) AS reel FROM pbi.v_ml_ventes
                    WHERE YEAR(mois) = :a GROUP BY categorie""", a=annee_reelle)
    prev = _lire("SELECT categorie, SUM(prevision_ca_ttc) AS prevu FROM ana.ml_pred_ventes_2026 GROUP BY categorie")
    return reel.merge(prev, on="categorie", how="outer").sort_values("prevu", ascending=False)


@st.cache_data(ttl=600, show_spinner=False)
def fraicheur() -> dict | None:
    """Pied de page du menu : dernière exécution de la chaîne, date des données, période comparée."""
    try:
        ex = derniere_execution()
        ref = date_reference()
    except Exception:
        return None
    from src import demo
    if demo.actif():
        m = demo.manifeste()
        mode = f"Instantané du {m.get('date_export', '—')}"
    else:
        mode = "Direct · SQL Server"
    return {"mode": mode,
            "execution": ex["fin"].max().strftime("%d/%m/%Y · %H:%M") if not ex.empty else "—",
            "ok": bool(len(ex)) and bool((ex["statut"] == "OK").all()),
            "date_donnees": ref.strftime("%d/%m/%Y"), "comparaison": f"{ref.year} face à {ref.year - 1}"}


def alertes_churn(n: int = 10) -> tuple[int, pd.DataFrame]:
    """Clients en alerte de churn au dernier scoring : nombre total, et les n dont le CA en jeu
    (risque x CA reconnu) est le plus élevé, avec le segment précédent et la date du dernier achat."""
    dernier = "(SELECT MAX(date_scoring) FROM pbi.v_ml_scores_churn)"
    total = int(_lire(f"""SELECT COUNT(*) AS n FROM pbi.v_ml_scores_churn
                          WHERE alerte_churn = 1 AND date_scoring = {dernier}""").iat[0, 0])
    detail = _lire(f"""
        SELECT TOP (:n) s.client_id AS id, i.nom_complet AS client, i.type_client, i.ville,
               s.segment_rfm, prec.segment_rfm AS segment_precedent, k.derniere_commande,
               s.proba_churn, s.decile_risque, s.montant_reconnu_ttc, s.recence_j, i.action_recommandee,
               s.proba_churn * s.montant_reconnu_ttc AS ca_en_jeu
        FROM pbi.v_ml_scores_churn AS s
        JOIN app.v_client_identite AS i ON i.client_id = s.client_id
        LEFT JOIN app.v_client_kpi AS k ON k.client_id = s.client_id
        OUTER APPLY (SELECT segment_rfm FROM app.v_client_rfm AS r      -- avant-dernier segment du client
                     WHERE r.client_id = s.client_id
                     ORDER BY r.date_observation DESC OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY) AS prec
        WHERE s.decile_risque <= 2 AND s.date_scoring = {dernier}      -- risque élevé (cf. churn_risque_eleve)
        ORDER BY s.proba_churn * s.montant_reconnu_ttc DESC""", n=n)
    return total, detail


def churn_risque_eleve() -> int:
    """Clients notés en déciles 1 et 2 au dernier scoring (niveau « élevé » de regles.niveau_risque).
    L'alerte du modèle (seuil constaté 0,37) touche 81 % des clients notés : trop large pour prioriser."""
    return int(_lire("""SELECT COUNT(*) AS n FROM pbi.v_ml_scores_churn
                        WHERE decile_risque <= 2
                          AND date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_churn)""").iat[0, 0])


def alertes_rupture(n: int = 10) -> tuple[int, pd.DataFrame]:
    """Produits épuisés au 1er trimestre de l'année prévue, sans réapprovisionnement."""
    base = """SELECT produit_id, MAX(nom_produit) AS produit, MAX(categorie) AS categorie,
                     MIN(CASE WHEN rupture_sans_reappro = 1 THEN mois END) AS mois_rupture,
                     MAX(stock_depart) AS stock_depart,
                     SUM(CASE WHEN MONTH(mois) <= 3 THEN quantite_prevue ELSE 0 END) AS demande_t1
              FROM pbi.v_ml_scores_demande
              GROUP BY produit_id
              HAVING MONTH(MIN(CASE WHEN rupture_sans_reappro = 1 THEN mois END)) <= 3"""
    total = int(_lire(f"SELECT COUNT(*) AS n FROM ({base}) AS r").iat[0, 0])
    detail = _lire(f"""SELECT TOP (:n) r.produit_id AS id, r.produit, r.categorie, r.mois_rupture, r.stock_depart,
                              r.demande_t1, i.fournisseur_id, i.nom_fournisseur
                       FROM ({base}) AS r
                       LEFT JOIN app.v_produit_identite AS i ON i.produit_id = r.produit_id
                       ORDER BY r.mois_rupture, r.demande_t1 DESC""", n=n)
    return total, detail


def alertes_fournisseurs(n: int = 10) -> tuple[int, pd.DataFrame]:
    """Fournisseurs nettement moins fiables qu'annoncé (écart sous SEUIL_ECART_FIABILITE)."""
    filtre = "FROM app.v_fournisseur_fiche WHERE ecart_fiabilite < :seuil"
    total = int(_lire(f"SELECT COUNT(*) AS n {filtre}", seuil=SEUIL_ECART_FIABILITE).iat[0, 0])
    detail = _lire(f"""SELECT TOP (:n) fournisseur_id AS id, nom_fournisseur AS fournisseur, pays,
                              fiabilite_annoncee, fiabilite_reelle, ecart_fiabilite, delai_annonce_j, delai_reel_moyen_j, tolerance_retard_j
                       {filtre} ORDER BY ecart_fiabilite""", n=n, seuil=SEUIL_ECART_FIABILITE)
    return total, detail


def alertes_colis(n: int = 10) -> tuple[int, pd.DataFrame]:
    """Colis en transit en alerte de retard au dernier scoring."""
    filtre = """FROM pbi.v_ml_scores_retard
                WHERE alerte_retard = 1
                  AND date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_retard)"""
    total = int(_lire(f"SELECT COUNT(*) AS n {filtre}").iat[0, 0])
    detail = _lire(f"""SELECT TOP (:n) commande_id AS id, livraison_id, transporteur, region,
                              date_expedition, proba_retard
                       {filtre} ORDER BY proba_retard DESC""", n=n)
    return total, detail


def derniere_execution() -> pd.DataFrame:
    """Dernière exécution de la chaîne d'analyse, notebook par notebook."""
    return _lire("SELECT notebook, statut, debut, fin FROM ctl.v_derniere_execution")


# ---------------------------------------------------------------------------
# Fiches : recherche d'une entité dans l'index
# ---------------------------------------------------------------------------
def entite(type_entite: str, identifiant: str) -> pd.DataFrame:
    """Ligne de l'index pour une entité (vide si l'identifiant n'existe pas)."""
    idx = index_recherche()
    return idx[(idx["type"] == type_entite) & (idx["id"] == identifiant)]


@st.cache_data(ttl=600, show_spinner=False)
def date_reference() -> pd.Timestamp:
    """Date des dernières données : date du dernier scoring de churn (fin 2025).
    Les « jours depuis » et les comparaisons d'années partent de cette date, pas d'aujourd'hui."""
    return pd.Timestamp(_lire("SELECT MAX(date_scoring) AS d FROM pbi.v_ml_scores_churn").iat[0, 0])


# ---------------------------------------------------------------------------
# Fiche Client (vues app des scripts 01 et 02, vues pbi et ana du projet d'analyse)
# ---------------------------------------------------------------------------
def client_identite(client_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_client_identite WHERE client_id = :id", id=client_id)


def client_kpi(client_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_client_kpi WHERE client_id = :id", id=client_id)


def client_annees(client_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_client_annee WHERE client_id = :id ORDER BY annee", id=client_id)


def client_ventes_mois(client_id: str) -> pd.DataFrame:
    return _lire("SELECT mois, nb_commandes, ca_reconnu_ttc FROM app.v_client_ventes_mois "
                 "WHERE client_id = :id ORDER BY mois", id=client_id)


def client_commandes(client_id: str, n: int = 10) -> pd.DataFrame:
    return _lire("""SELECT TOP (:n) c.commande_id AS id, c.date_commande, c.libelle_statut, c.nb_articles,
                           c.montant_total_ttc, c.remise_coupon_ttc, c.montant_rembourse_ttc,
                           l.statut_livraison, l.retard_j, l.est_livree, l.transporteur
                    FROM app.v_client_commandes AS c
                    LEFT JOIN app.v_commande_livraison AS l ON l.commande_id = c.commande_id
                    WHERE c.client_id = :id
                    ORDER BY c.date_commande DESC, c.commande_id DESC""", id=client_id, n=n)


def client_produits(client_id: str, n: int = 10) -> pd.DataFrame:
    return _lire("""SELECT TOP (:n) produit_id AS id, nom_produit, categorie, quantite, montant_ttc, dernier_achat
                    FROM app.v_client_produits WHERE client_id = :id
                    ORDER BY montant_ttc DESC""", id=client_id, n=n)


def client_habitudes(client_id: str) -> pd.DataFrame:
    return _lire("""SELECT dimension, valeur, nb_commandes, montant_ttc FROM app.v_client_habitudes
                    WHERE client_id = :id ORDER BY dimension, nb_commandes DESC, montant_ttc DESC""", id=client_id)


def client_experience(client_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_client_experience WHERE client_id = :id", id=client_id)


def client_remboursements(client_id: str) -> pd.DataFrame:
    return _lire("""SELECT commande_id, produit_id, nom_produit, date_demande, libelle_motif, responsabilite, statut,
                           montant_rembourse_ttc
                    FROM app.v_client_remboursements WHERE client_id = :id ORDER BY date_demande DESC""", id=client_id)


def client_rfm(client_id: str) -> pd.DataFrame:
    return _lire("""SELECT date_observation, periode, segment_rfm, code_rfm, cluster
                    FROM app.v_client_rfm WHERE client_id = :id ORDER BY date_observation""", id=client_id)


def client_churn_test(client_id: str) -> pd.DataFrame:
    return _lire("""SELECT date_observation, proba_churn, prediction, churn_reel
                    FROM app.v_client_churn_test WHERE client_id = :id ORDER BY date_observation""", id=client_id)


def client_avis(client_id: str) -> pd.DataFrame:
    """Avis commentés du client, avec thèmes, langue et polarité (text mining v1.4)."""
    return _lire("""SELECT a.avis_id, a.date_avis, a.produit_id, p.nom_produit, a.note, a.langue, a.texte_nettoye,
                           a.texte_fr, a.themes, a.polarite_globale
                    FROM pbi.v_tm_avis AS a
                    LEFT JOIN app.v_produit_identite AS p ON p.produit_id = a.produit_id
                    WHERE a.client_id = :id ORDER BY a.date_avis DESC""", id=client_id)


def profil_cluster(cluster: str) -> pd.DataFrame:
    return _lire("SELECT * FROM ana.dm02_profil_clusters WHERE cluster = :c", c=cluster)


# ---------------------------------------------------------------------------
# Fiche Produit
# ---------------------------------------------------------------------------
def produit_identite(produit_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_produit_identite WHERE produit_id = :id", id=produit_id)


def produit_kpi(produit_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_produit_kpi WHERE produit_id = :id", id=produit_id)


def produit_annees(produit_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_produit_annee WHERE produit_id = :id ORDER BY annee", id=produit_id)


def produit_ventes_mois(produit_id: str) -> pd.DataFrame:
    return _lire("""SELECT mois, quantite, ca_ht FROM app.v_produit_ventes_mois
                    WHERE produit_id = :id ORDER BY mois""", id=produit_id)


def produit_stock_mois(produit_id: str) -> pd.DataFrame:
    return _lire("""SELECT mois, stock_fin_mois, quantite_en_commande FROM app.v_produit_stock_mois
                    WHERE produit_id = :id ORDER BY mois""", id=produit_id)


def produit_demande(produit_id: str) -> pd.DataFrame:
    """Prévision de demande mensuelle (dernier scoring) : quantité prévue, stock de départ, rupture."""
    return _lire("""SELECT mois, quantite_prevue, stock_depart, demande_cumulee, rupture_sans_reappro
                    FROM pbi.v_ml_scores_demande
                    WHERE produit_id = :id
                      AND date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_demande)
                    ORDER BY mois""", id=produit_id)


def regles_categorie(categorie: str, sous_categorie: str) -> pd.DataFrame:
    """Règles d'association stables sur 2025 dont l'antécédent est la catégorie ou la sous-catégorie du produit.
    Le niveau produit n'est pas utilisé : ses règles ne tiennent pas sur 2025 (notebook DM03)."""
    return _lire("""SELECT niveau, consequents, confidence_2025, lift_2025
                    FROM pbi.v_dm_regles
                    WHERE stable = 1
                      AND ((niveau = N'catégorie' AND antecedents = :c)
                        OR (niveau = N'sous-catégorie' AND antecedents = :s))
                    ORDER BY lift_2025 DESC""", c=categorie, s=sous_categorie)


def produit_themes(produit_id: str) -> pd.DataFrame:
    """Nombre d'avis par thème (text mining), dont négatifs."""
    return _lire("""SELECT theme, COUNT(*) AS nb_avis,
                           SUM(CASE WHEN polarite = N'négatif' THEN 1 ELSE 0 END) AS nb_negatifs
                    FROM pbi.v_tm_avis_themes WHERE produit_id = :id
                    GROUP BY theme ORDER BY COUNT(*) DESC""", id=produit_id)


def produit_synthese_avis(produit_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM pbi.v_tm_produits WHERE produit_id = :id", id=produit_id)


def produit_avis(produit_id: str, n: int = 5) -> pd.DataFrame:
    """Avis commentés du produit : les plus récents, avec langue, note et cohérence texte / note."""
    return _lire("""SELECT TOP (:n) avis_id, date_avis, client_id, note, langue, texte_nettoye, themes,
                           polarite_globale, coherence
                    FROM pbi.v_tm_avis WHERE produit_id = :id
                    ORDER BY date_avis DESC, avis_id DESC""", id=produit_id, n=n)


def fournisseur_fiche(fournisseur_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_fournisseur_fiche WHERE fournisseur_id = :id", id=fournisseur_id)


# ---------------------------------------------------------------------------
# Page Recherche : détails affichés sous chaque résultat (lus une fois, gardés 10 min)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def etat_produits() -> pd.DataFrame:
    """Par produit : catégorie, stock de départ de la prévision et mois de rupture prévu (ou vide)."""
    return _lire("""SELECT i.produit_id, i.categorie, d.stock_depart, d.mois_rupture
                    FROM app.v_produit_identite AS i
                    LEFT JOIN (SELECT produit_id, MAX(stock_depart) AS stock_depart,
                                      MIN(CASE WHEN rupture_sans_reappro = 1 THEN mois END) AS mois_rupture
                               FROM pbi.v_ml_scores_demande
                               WHERE date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_demande)
                               GROUP BY produit_id) AS d ON d.produit_id = i.produit_id""")


@st.cache_data(ttl=600, show_spinner=False)
def resume_fournisseurs() -> pd.DataFrame:
    """Par fournisseur : pays, nombre de produits, fiabilité annoncée et réelle."""
    return _lire("""SELECT f.fournisseur_id, f.pays, f.fiabilite_annoncee, f.fiabilite_reelle,
                           (SELECT COUNT(*) FROM app.v_produit_identite AS p
                            WHERE p.fournisseur_id = f.fournisseur_id) AS nb_produits
                    FROM app.v_fournisseur_fiche AS f""")


@st.cache_data(ttl=600, show_spinner=False)
def resume_clients() -> pd.DataFrame:
    """Par client noté : segment RFM et risque de churn au dernier scoring."""
    return _lire("""SELECT client_id, segment_rfm, proba_churn, decile_risque FROM app.v_client_identite
                    WHERE proba_churn IS NOT NULL""")


@st.cache_data(ttl=3600, show_spinner=False)
def importance_churn(n: int = 5) -> pd.DataFrame:
    """Variables qui pèsent le plus dans le modèle de churn : perte d'AUC par permutation (test 2025)."""
    return _lire("SELECT TOP (:n) cle AS variable, perte_AUC AS perte_auc FROM ana.ml03_importance "
                 "ORDER BY perte_AUC DESC", n=n)


# ---------------------------------------------------------------------------
# Fiche Fournisseur
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fournisseurs_annee(annee: int) -> pd.DataFrame:
    """Une ligne par fournisseur pour une année, avec ses promesses (pour le score et les comparaisons)."""
    return _lire("""SELECT a.*, f.nom_fournisseur, f.fiabilite_annoncee, f.delai_annonce_j
                    FROM app.v_fournisseur_annee AS a
                    JOIN app.v_fournisseur_fiche AS f ON f.fournisseur_id = a.fournisseur_id
                    WHERE a.annee = :a""", a=annee)


def fournisseur_achats_mois(fournisseur_id: str) -> pd.DataFrame:
    return _lire("""SELECT mois, nb_commandes, montant_ht, delai_reel_moyen_j FROM app.v_fournisseur_achats_mois
                    WHERE fournisseur_id = :id ORDER BY mois""", id=fournisseur_id)


def fournisseur_produits(fournisseur_id: str, annee: int) -> pd.DataFrame:
    """Produits du fournisseur : chiffres de l'année, rang des ventes dans sa catégorie, stock et rupture prévus."""
    return _lire("""
        WITH rang AS (
            SELECT a.produit_id, a.ca_ttc, a.taux_marge, a.taux_retour,
                   RANK() OVER (PARTITION BY i.categorie ORDER BY a.ca_ttc DESC) AS rang_categorie
            FROM app.v_produit_annee AS a
            JOIN app.v_produit_identite AS i ON i.produit_id = a.produit_id
            WHERE a.annee = :a
        ), dem AS (
            SELECT produit_id, MAX(stock_depart) AS stock_depart,
                   MIN(CASE WHEN rupture_sans_reappro = 1 THEN mois END) AS mois_rupture
            FROM pbi.v_ml_scores_demande
            WHERE date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_demande)
            GROUP BY produit_id
        )
        SELECT i.produit_id AS id, i.nom_produit, i.categorie, i.statut_produit,
               r.ca_ttc, r.taux_marge, r.taux_retour, r.rang_categorie, d.stock_depart, d.mois_rupture
        FROM app.v_produit_identite AS i
        LEFT JOIN rang AS r ON r.produit_id = i.produit_id
        LEFT JOIN dem  AS d ON d.produit_id = i.produit_id
        WHERE i.fournisseur_id = :id
        ORDER BY r.ca_ttc DESC""", id=fournisseur_id, a=annee)


def fournisseur_demande(fournisseur_id: str) -> pd.DataFrame:
    """Prévision de demande mensuelle de tous ses produits (pour estimer le jour de rupture de chacun)."""
    return _lire("""SELECT d.produit_id, d.mois, d.quantite_prevue, d.stock_depart
                    FROM pbi.v_ml_scores_demande AS d
                    JOIN app.v_produit_identite AS i ON i.produit_id = d.produit_id
                    WHERE i.fournisseur_id = :id
                      AND d.date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_demande)
                    ORDER BY d.produit_id, d.mois""", id=fournisseur_id)


# ---------------------------------------------------------------------------
# Fiche Commande
# ---------------------------------------------------------------------------
def commande_fiche(commande_id: str) -> pd.DataFrame:
    return _lire("SELECT * FROM app.v_commande_fiche WHERE commande_id = :id", id=commande_id)


def commande_lignes(commande_id: str) -> pd.DataFrame:
    return _lire("""SELECT produit_id AS id, nom_produit, quantite, prix_unitaire_ttc, montant_ttc,
                           quantite_retournee, montant_rembourse_ttc, motif_retour, statut_retour
                    FROM app.v_commande_lignes WHERE commande_id = :id ORDER BY montant_ttc DESC""", id=commande_id)


def commande_avis(commande_id: str) -> pd.DataFrame:
    return _lire("""SELECT avis_id, produit_id, date_avis, note, langue, texte_nettoye, themes, polarite_globale
                    FROM pbi.v_tm_avis WHERE commande_id = :id ORDER BY date_avis""", id=commande_id)


def prediction_retard(livraison_id: str) -> pd.DataFrame:
    """Risque de retard prédit à l'expédition : test 2025 (livraisons terminées, avec le retard réel)
    ou dernier scoring (colis en transit, retard pas encore connu)."""
    return _lire("""SELECT 'test' AS source, proba_retard, retard_reel, date_expedition, CAST(NULL AS date) AS date_scoring
                    FROM pbi.v_ml_retard WHERE livraison_id = :id
                    UNION ALL
                    SELECT 'en cours', proba_retard, CAST(NULL AS int), date_expedition, date_scoring
                    FROM pbi.v_ml_scores_retard WHERE livraison_id = :id""", id=livraison_id)


@st.cache_data(ttl=3600, show_spinner=False)
def seuil_retard() -> float | None:
    """Seuil de décision du modèle de retard retenu (choisi sur la validation)."""
    t = _lire("SELECT TOP (1) seuil FROM ana.ml_metriques_retard WHERE retenu = 1")
    return None if t.empty else float(t.iat[0, 0])


@st.cache_data(ttl=600, show_spinner=False)
def taux_retard_facteurs(annee: int) -> pd.DataFrame:
    """Taux de retard réel des livraisons expédiées dans l'année, par transporteur, région et jour d'expédition.
    Retard = livrée, mais pas à temps (même définition que les fiches Client et Transporteur)."""
    return _lire("""
        WITH l AS (
            SELECT t.nom_transporteur, g.region, d.nom_jour,
                   CASE WHEN f.est_livree_a_temps = 0 THEN 1.0 ELSE 0.0 END AS en_retard
            FROM TuniShop_DWH.bi.v_fact_livraisons AS f
            JOIN TuniShop_DWH.bi.v_dim_date        AS d ON d.date_sk = f.date_expedition_sk
            LEFT JOIN TuniShop_DWH.bi.v_dim_transporteur AS t ON t.transporteur_sk = f.transporteur_sk
            LEFT JOIN TuniShop_DWH.bi.v_dim_geographie   AS g ON g.geographie_sk = f.geographie_sk
            WHERE f.est_livree = 1 AND d.annee = :a
        )
        SELECT 'transporteur' AS facteur, nom_transporteur AS valeur, COUNT(*) AS n, AVG(en_retard) AS taux FROM l GROUP BY nom_transporteur
        UNION ALL SELECT 'region', region, COUNT(*), AVG(en_retard) FROM l GROUP BY region
        UNION ALL SELECT 'jour', nom_jour, COUNT(*), AVG(en_retard) FROM l GROUP BY nom_jour
        UNION ALL SELECT 'ensemble', 'toutes', COUNT(*), AVG(en_retard) FROM l""", a=annee)


# ---------------------------------------------------------------------------
# Fiche Transporteur
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def transporteurs() -> pd.DataFrame:
    """Référentiel des transporteurs (identifiant, nom, couverture, coût de base)."""
    return _lire("""SELECT transporteur_id, nom_transporteur, couverture, cout_base_ht
                    FROM TuniShop_DWH.bi.v_dim_transporteur
                    WHERE transporteur_sk > 0 AND est_supprime = 0""")


@st.cache_data(ttl=600, show_spinner=False)
def _avis_transporteurs() -> pd.DataFrame:
    """Avis commentés par transporteur et par année, avec le nombre de ceux qui critiquent la livraison.
    Lecture directe des tables ana.tm_avis et ana.tm_avis_themes (diagnostic sql/07 du 17/11/2026 :
    l'ancienne requête sur les vues prenait 50 à 94 s)."""
    # Même règle que pbi.v_tm_avis (transporteur de la 1re livraison de la commande), mais en une seule passe :
    # la vue la calcule avis par avis (OUTER APPLY), soit 6 081 recherches dans les livraisons.
    avis = _lire("""SELECT a.avis_id, ISNULL(tr.nom_transporteur, 'inconnu') AS transporteur, YEAR(a.date_avis) AS annee
                    FROM ana.tm_avis AS a
                    LEFT JOIN (SELECT l.commande_id, t.nom_transporteur,
                                      ROW_NUMBER() OVER (PARTITION BY l.commande_id ORDER BY l.livraison_id) AS rang
                               FROM TuniShop_DWH.bi.v_fact_livraisons AS l
                               JOIN TuniShop_DWH.bi.v_dim_transporteur AS t ON t.transporteur_sk = l.transporteur_sk
                              ) AS tr ON tr.commande_id = a.commande_id AND tr.rang = 1""")
    neg = set(_lire("""SELECT DISTINCT avis_id FROM ana.tm_avis_themes
                       WHERE theme = N'Livraison' AND polarite = N'négatif'""")["avis_id"])
    avis["negatif_livraison"] = avis["avis_id"].isin(neg).astype(int)
    par_t = avis.groupby(["annee", "transporteur"], as_index=False).agg(
        nb_avis=("avis_id", "size"), nb_negatifs_livraison=("negatif_livraison", "sum"))
    tout = avis.groupby("annee", as_index=False).agg(nb_avis=("avis_id", "size"),
                                                    nb_negatifs_livraison=("negatif_livraison", "sum"))
    return pd.concat([par_t, tout.assign(transporteur="ensemble")], ignore_index=True)


@st.cache_data(ttl=600, show_spinner=False)
def transporteurs_annee(annee: int) -> pd.DataFrame:
    """Une ligne par transporteur pour une année : colis livrés, retard réel et prédit, retard moyen,
    part d'avis commentés négatifs sur la livraison. Plus une ligne « ensemble » (tous transporteurs)."""
    liv = _lire("""
        WITH l AS (
            SELECT transporteur, est_livree, en_retard, retard_j, proba_retard
            FROM app.v_livraison_detail WHERE annee = :a
        )
        SELECT transporteur, SUM(CASE WHEN est_livree = 1 THEN 1 ELSE 0 END) AS colis_livres,
               AVG(CASE WHEN est_livree = 1 THEN CAST(en_retard AS float) END) AS taux_reel,
               AVG(CASE WHEN est_livree = 1 THEN proba_retard END) AS taux_predit,
               AVG(CAST(retard_j AS float)) AS retard_moyen_j
        FROM l GROUP BY transporteur
        UNION ALL
        SELECT 'ensemble', SUM(CASE WHEN est_livree = 1 THEN 1 ELSE 0 END),
               AVG(CASE WHEN est_livree = 1 THEN CAST(en_retard AS float) END),
               AVG(CASE WHEN est_livree = 1 THEN proba_retard END), AVG(CAST(retard_j AS float))
        FROM l""", a=annee)
    av = _avis_transporteurs()
    av = av[av["annee"] == annee].drop(columns="annee")
    t = liv.merge(av, on="transporteur", how="left")
    t["part_avis_negatifs"] = t["nb_negatifs_livraison"] / t["nb_avis"].where(t["nb_avis"] > 0)
    return t.drop(columns="nb_negatifs_livraison")


@st.cache_data(ttl=600, show_spinner=False)
def retard_semestres() -> pd.DataFrame:
    """Taux de retard réel par transporteur et par semestre d'expédition, plus « ensemble »."""
    return _lire("""SELECT transporteur, annee, semestre, AVG(CAST(en_retard AS float)) AS taux
                    FROM app.v_livraison_detail WHERE est_livree = 1 GROUP BY transporteur, annee, semestre
                    UNION ALL
                    SELECT 'ensemble', annee, semestre, AVG(CAST(en_retard AS float))
                    FROM app.v_livraison_detail WHERE est_livree = 1 GROUP BY annee, semestre""")


def retard_regions(transporteur: str, annee: int) -> pd.DataFrame:
    return _lire("""SELECT region, COUNT(*) AS colis, AVG(CAST(en_retard AS float)) AS taux
                    FROM app.v_livraison_detail
                    WHERE transporteur = :t AND annee = :a AND est_livree = 1 AND region IS NOT NULL
                    GROUP BY region ORDER BY taux DESC""", t=transporteur, a=annee)


def colis_en_cours(transporteur: str) -> pd.DataFrame:
    """Colis en transit du transporteur au dernier scoring, du plus risqué au moins risqué."""
    # Jointure directe sur la livraison du DWH (une ligne par colis), plutôt que sur app.v_commande_fiche :
    # même résultat, sans recalculer la fiche de toutes les commandes.
    return _lire("""SELECT s.commande_id AS id, c.client_id, g.gouvernorat, s.region, s.date_expedition,
                           dp.[date] AS date_prevue, s.proba_retard, s.alerte_retard
                    FROM pbi.v_ml_scores_retard AS s
                    LEFT JOIN TuniShop_DWH.bi.v_fact_livraisons AS l  ON l.livraison_id = s.livraison_id
                    LEFT JOIN TuniShop_DWH.bi.v_dim_client      AS c  ON c.client_sk = l.client_sk
                    LEFT JOIN TuniShop_DWH.bi.v_dim_geographie  AS g  ON g.geographie_sk = l.geographie_sk
                    LEFT JOIN TuniShop_DWH.bi.v_dim_date        AS dp ON dp.date_sk = l.date_prevue_sk
                    WHERE s.transporteur = :t
                      AND s.date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_retard)
                    ORDER BY s.proba_retard DESC""", t=transporteur)


# ---------------------------------------------------------------------------
# Page Voix du client (text mining v1.4)
# Les filtres facultatifs sont ajoutés au texte de la requête (pas de « :x IS NULL », que SQL Server
# ne sait pas typer quand la valeur est vide).
# ---------------------------------------------------------------------------
def _filtres_avis(categorie: str | None, annee: int | None, alias: str = "a") -> tuple[str, dict]:
    clauses, params = [], {}
    if categorie:
        clauses.append(f"{alias}.categorie = :c")
        params["c"] = categorie
    if annee:
        clauses.append(f"YEAR({alias}.date_avis) = :an")
        params["an"] = annee
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@st.cache_data(ttl=3600, show_spinner=False)
def tm_categories() -> list[str]:
    return _lire("SELECT DISTINCT categorie FROM pbi.v_tm_avis WHERE categorie IS NOT NULL ORDER BY categorie")["categorie"].tolist()


@st.cache_data(ttl=600, show_spinner=False)
def tm_resume(categorie: str | None = None, annee: int | None = None) -> pd.Series:
    """Avis (tous, DWH), avis commentés, en derja, formulations distinctes, incohérences texte / note."""
    w, prm = _filtres_avis(categorie, annee)
    com = _lire(f"""SELECT COUNT(*) AS nb_commentes,
                           SUM(CASE WHEN a.langue = 'derja' THEN 1 ELSE 0 END) AS nb_derja,
                           COUNT(DISTINCT a.texte_nettoye) AS nb_formulations,
                           SUM(CASE WHEN a.coherence LIKE 'texte %' THEN 1 ELSE 0 END) AS nb_incoherents
                    FROM pbi.v_tm_avis AS a{w}""", **prm).iloc[0]
    clauses, prm2 = [], {}
    if categorie:
        clauses.append("p.categorie = :c")
        prm2["c"] = categorie
    if annee:
        clauses.append("d.annee = :an")
        prm2["an"] = annee
    w2 = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    tous = _lire(f"""SELECT COUNT(*) AS nb_avis
                     FROM TuniShop_DWH.bi.v_fact_avis AS f
                     JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = f.produit_sk
                     JOIN TuniShop_DWH.bi.v_dim_date AS d ON d.date_sk = f.date_avis_sk{w2}""", **prm2).iloc[0]
    return pd.concat([tous, com])


@st.cache_data(ttl=600, show_spinner=False)
def tm_themes(categorie: str | None = None, annee: int | None = None) -> pd.DataFrame:
    """Mentions par thème (un avis peut en avoir plusieurs), dont négatives."""
    w, prm = _filtres_avis(categorie, annee, alias="t")
    return _lire(f"""SELECT t.theme, COUNT(*) AS mentions,
                            SUM(CASE WHEN t.polarite = N'négatif' THEN 1 ELSE 0 END) AS negatives
                     FROM pbi.v_tm_avis_themes AS t{w}
                     GROUP BY t.theme ORDER BY COUNT(*) DESC""", **prm)


@st.cache_data(ttl=600, show_spinner=False)
def tm_langues(categorie: str | None = None, annee: int | None = None) -> pd.DataFrame:
    w, prm = _filtres_avis(categorie, annee)
    return _lire(f"SELECT a.langue, COUNT(*) AS avis FROM pbi.v_tm_avis AS a{w} GROUP BY a.langue ORDER BY COUNT(*) DESC", **prm)


@st.cache_data(ttl=600, show_spinner=False)
def tm_expressions_derja(categorie: str | None = None, annee: int | None = None, n: int = 6) -> pd.DataFrame:
    """Formulations derja les plus fréquentes, avec leur traduction et leur polarité."""
    w, prm = _filtres_avis(categorie, annee)
    w = (w + " AND " if w else " WHERE ") + "a.langue = 'derja'"
    return _lire(f"""SELECT TOP (:n) a.texte_nettoye AS expression, MAX(a.texte_fr) AS sens,
                            MAX(a.polarite_globale) AS polarite, COUNT(*) AS avis
                     FROM pbi.v_tm_avis AS a{w}
                     GROUP BY a.texte_nettoye ORDER BY COUNT(*) DESC""", n=n, **prm)


@st.cache_data(ttl=3600, show_spinner=False)
def tm_verification() -> pd.DataFrame:
    """Confrontation thème x polarité aux faits du DWH (toutes catégories, toute la période)."""
    return _lire("""SELECT theme, polarite, avis, part_colis_en_retard, part_retour, motifs_lies, part_retour_motif_lie
                    FROM pbi.v_tm_verification_faits ORDER BY avis DESC""")


# ---------------------------------------------------------------------------
# Page Modèles
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def ml_modeles() -> pd.DataFrame:
    """Modèles comparés par cas (référence, candidats, retenu), mesure de validation et de test 2025."""
    return _lire("SELECT cas, modele, role, mesure, sens, valeur_validation, valeur_test, gain_vs_reference, retenu "
                 "FROM pbi.v_ml_modeles")


@st.cache_data(ttl=3600, show_spinner=False)
def ml_registre() -> pd.DataFrame:
    return _lire("""SELECT nom, cas, role, version, appris_le, periode_apprentissage, lignes_apprentissage,
                           nb_variables, seuil, source, notes
                    FROM pbi.v_ml_registre ORDER BY cas, appris_le DESC""")


@st.cache_data(ttl=600, show_spinner=False)
def ml_suivi() -> pd.DataFrame:
    """Indicateurs de suivi de la dernière exécution (le suivi n'est pas historisé)."""
    return _lire("SELECT cas, objet, periode, indicateur, valeur, seuil, statut FROM pbi.v_ml_suivi")

