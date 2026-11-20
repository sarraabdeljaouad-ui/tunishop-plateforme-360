"""Données factices pour tester les pages sans SQL Server.

Le fixture `donnees_factices` remplace les fonctions de src.donnees par des tableaux fabriqués.
Les pages appellent donnees.<fonction>() : elles reçoivent ces tableaux au lieu d'interroger la base.
"""
from pathlib import Path

import pandas as pd
import pytest

DOSSIER = Path(__file__).parent / "donnees"


@pytest.fixture
def donnees_factices(monkeypatch):
    from src import donnees, recherche
    lire = lambda n: pd.read_csv(DOSSIER / n, dtype=str)
    idx = recherche.construire_index(lire("clients_test.csv"), lire("produits_test.csv"), lire("fournisseurs_test.csv"))
    monkeypatch.setattr(donnees, "index_recherche", lambda: idx)
    monkeypatch.setattr(donnees, "vue_ensemble", lambda: pd.DataFrame({
        "annee": [2024, 2025], "commandes_passees": [30000, 36000], "commandes_reconnues": [28000, 33000],
        "ca_reconnu_ttc": [4.9e6, 6.1e6], "clients_actifs": [9000, 10500], "panier_moyen_ttc": [175.0, 184.8],
        "taux_retard": [0.19, 0.173], "note_moyenne": [4.11, 4.15]}))
    monkeypatch.setattr(donnees, "prevision_ca", lambda: pd.DataFrame(
        {"annee": [2026], "prevision_ca_ttc": [7.2e6], "categories": [9]}))
    monkeypatch.setattr(donnees, "alertes_churn", lambda n=10: (2, pd.DataFrame({
        "id": ["CLI004074", "CLI000001"], "client": ["Riadh Belhadj", "Omar Sfar"],
        "type_client": ["particulier"] * 2, "ville": ["Tabarka", "Gafsa"],
        "segment_rfm": ["À risque", "Hibernants"], "segment_precedent": ["Fidèles", None],
        "decile_risque": [1, 2], "action_recommandee": ["Relance avec un coupon personnalisé", None],
        "derniere_commande": [pd.Timestamp("2025-09-02"), pd.Timestamp("2025-09-27")], "proba_churn": [0.81, 0.77],
        "montant_reconnu_ttc": [5200.0, 3100.0], "recence_j": [120, 95], "ca_en_jeu": [4212.0, 2387.0]})))
    monkeypatch.setattr(donnees, "alertes_rupture", lambda n=10: (1, pd.DataFrame({
        "id": ["PRD0001"], "produit": ["Smartphone Nexora Évasion 15"], "categorie": ["Électronique & High-Tech"],
        "mois_rupture": [pd.Timestamp("2026-02-01")], "stock_depart": [12.0], "demande_t1": [40.0],
        "fournisseur_id": ["FRN002"], "nom_fournisseur": ["Torino Elettro"]})))
    monkeypatch.setattr(donnees, "etat_produits", lambda: pd.DataFrame({
        "produit_id": ["PRD0001"], "categorie": ["Électronique & High-Tech"], "stock_depart": [12.0],
        "mois_rupture": [pd.Timestamp("2026-02-01")]}))
    monkeypatch.setattr(donnees, "resume_fournisseurs", lambda: pd.DataFrame({
        "fournisseur_id": ["FRN002"], "pays": ["Italie"], "fiabilite_annoncee": [0.97], "fiabilite_reelle": [0.87],
        "nb_produits": [34]}))
    monkeypatch.setattr(donnees, "resume_clients", lambda: pd.DataFrame({
        "client_id": ["CLI004074"], "segment_rfm": ["À risque"], "proba_churn": [0.81], "decile_risque": [1]}))
    monkeypatch.setattr(donnees, "importance_churn", lambda n=5: pd.DataFrame({
        "variable": ["recence_j", "nb_livraisons", "anciennete_j", "montant_reconnu_ttc", "segment_rfm"],
        "perte_auc": [0.242, 0.008, 0.006, 0.005, 0.004]}))
    monkeypatch.setattr(donnees, "churn_risque_eleve", lambda: 1475)
    monkeypatch.setattr(donnees, "ventes_categories", lambda a: pd.DataFrame({
        "categorie": ["Électronique & High-Tech", "Mode"], "reel": [2.1e6, 1.2e6], "prevu": [2.4e6, 1.3e6]}))
    monkeypatch.setattr(donnees, "fraicheur", lambda: {"mode": "Direct · SQL Server", "execution": "13/11/2026 · 23:39",
        "ok": True, "date_donnees": "31/12/2025", "comparaison": "2025 face à 2024"})
    monkeypatch.setattr(donnees, "alertes_fournisseurs", lambda n=10: (0, pd.DataFrame(columns=[
        "id", "fournisseur", "pays", "fiabilite_annoncee", "fiabilite_reelle", "ecart_fiabilite",
        "delai_annonce_j", "delai_reel_moyen_j", "tolerance_retard_j"])))
    monkeypatch.setattr(donnees, "alertes_colis", lambda n=10: (1, pd.DataFrame({
        "id": ["CMD0000010"], "livraison_id": ["LIV0000010"], "transporteur": ["SahelLog"], "region": ["Sud"],
        "date_expedition": [pd.Timestamp("2025-12-30")], "proba_retard": [0.62]})))
    monkeypatch.setattr(donnees, "derniere_execution", lambda: pd.DataFrame({
        "notebook": ["a", "b"], "statut": ["OK", "OK"],
        "debut": [pd.Timestamp("2026-11-13 22:05")] * 2, "fin": [pd.Timestamp("2026-11-13 23:39")] * 2}))
    # --- fiche client (CLI004074 : client complet ; CLI000001 : sans score de churn)
    ts = pd.Timestamp
    identite = pd.DataFrame({
        "client_id": ["CLI004074", "CLI000001"], "nom_complet": ["Riadh Belhadj", "Omar Sfar"],
        "type_client": ["particulier"] * 2, "genre": ["M"] * 2, "tranche_age": ["35-44", "55-64"],
        "gouvernorat": ["Jendouba", "Gafsa"], "region": ["Nord-Ouest", "Sud-Ouest"], "ville": ["Tabarka", "Gafsa"],
        "canal_inscription": ["moteur_recherche_payant", "acces_direct"],
        "date_inscription": [ts("2023-04-07"), ts("2021-06-20")], "cohorte_inscription": ["2023-04", "2021-06"],
        "segment_fidelite": ["aucun", "aucun"], "opt_in_email": [1, 1], "opt_in_sms": [0, 1],
        "date_scoring": [ts("2025-12-31"), pd.NaT], "proba_churn": [0.81, float("nan")],
        "alerte_churn": [1, float("nan")], "decile_risque": [1, float("nan")],
        "segment_rfm": ["À risque", None], "cluster": ["Réguliers", None], "recence_j": [120, float("nan")],
        "frequence": [5, float("nan")], "montant_reconnu_ttc": [1900.0, float("nan")],
        "version_modele": ["churn_production v1.2", None],
        "action_recommandee": ["Relance avec un coupon personnalisé", None]})
    par_id = lambda df, col="client_id": (lambda i, *a, **k: df[df[col] == i].reset_index(drop=True))
    monkeypatch.setattr(donnees, "date_reference", lambda: ts("2025-12-31"))
    monkeypatch.setattr(donnees, "client_identite", par_id(identite))
    monkeypatch.setattr(donnees, "client_kpi", par_id(pd.DataFrame({
        "client_id": ["CLI004074", "CLI000001"], "nb_commandes": [9, 1], "nb_commandes_reconnues": [8, 1],
        "ca_reconnu_ttc": [2400.0, 120.0], "panier_moyen_ttc": [300.0, 120.0], "montant_rembourse_ttc": [80.0, 0.0],
        "taux_livre_a_temps": [0.75, 1.0], "premiere_commande": [ts("2023-07-29"), ts("2021-07-01")],
        "derniere_commande": [ts("2025-09-02"), ts("2021-07-01")]})))
    monkeypatch.setattr(donnees, "client_annees", par_id(pd.DataFrame({
        "client_id": ["CLI004074"] * 2, "annee": [2024, 2025], "nb_commandes": [5, 3], "nb_commandes_reconnues": [5, 2],
        "ca_reconnu_ttc": [1600.0, 600.0], "panier_moyen_ttc": [320.0, 300.0], "taux_annulation": [0.0, 0.333],
        "marge_brute_ht": [300.0, 110.0], "quantite_vendue": [9, 4], "quantite_retournee": [0, 1],
        "taux_retour": [0.0, 0.25], "montant_rembourse_ttc": [0.0, 80.0], "nb_avis": [1, 1], "note_moyenne": [4.0, 1.0]})))
    monkeypatch.setattr(donnees, "client_ventes_mois", par_id(pd.DataFrame({
        "client_id": ["CLI004074"] * 3, "mois": [ts("2024-03-01"), ts("2024-11-01"), ts("2025-09-01")],
        "nb_commandes": [2, 3, 2], "ca_reconnu_ttc": [700.0, 900.0, 600.0]})))
    monkeypatch.setattr(donnees, "client_commandes", lambda i, n=10: pd.DataFrame({
        "id": ["CMD0000033"], "date_commande": [ts("2025-09-02")], "libelle_statut": ["Livrée"], "nb_articles": [2],
        "montant_total_ttc": [300.0], "remise_coupon_ttc": [0.0], "montant_rembourse_ttc": [80.0],
        "statut_livraison": ["livree"], "retard_j": [4.0], "est_livree": [1], "transporteur": ["SahelLog"]}) if i == "CLI004074" else pd.DataFrame())
    monkeypatch.setattr(donnees, "client_produits", lambda i, n=10: pd.DataFrame({
        "id": ["PRD0001"], "nom_produit": ["Smartphone Nexora Évasion 15"], "categorie": ["Électronique & High-Tech"],
        "quantite": [1], "montant_ttc": [783.9], "dernier_achat": [ts("2025-09-02")]}) if i == "CLI004074" else pd.DataFrame())
    monkeypatch.setattr(donnees, "client_habitudes", lambda i: pd.DataFrame({
        "dimension": ["canal", "appareil", "mode de paiement", "catégorie", "transporteur"],
        "valeur": ["Site web", "mobile", "Paiement à la livraison", "Électronique & High-Tech", "SahelLog"],
        "nb_commandes": [9, 9, 9, 3, 8], "montant_ttc": [2400.0, 2400.0, 2400.0, 783.9, None]}) if i == "CLI004074"
        else pd.DataFrame(columns=["dimension", "valeur", "nb_commandes", "montant_ttc"]))
    monkeypatch.setattr(donnees, "client_experience", lambda i: pd.DataFrame({
        "client_id": [i], "nb_commandes": [9], "nb_commandes_avec_coupon": [2], "part_commandes_coupon": [0.22],
        "remise_coupon_ttc": [25.0], "nb_livrees": [8], "nb_livrees_en_retard": [3], "taux_retard": [0.375],
        "nb_echecs_livraison": [0], "nb_tentatives_paiement": [10], "nb_paiements_echoues": [1],
        "nb_remboursements": [1], "montant_rembourse_ttc": [80.0], "nb_avis": [2], "note_moyenne": [2.5]})
        if i == "CLI004074" else pd.DataFrame())
    monkeypatch.setattr(donnees, "client_remboursements", lambda i: pd.DataFrame({
        "commande_id": ["CMD0000033"], "produit_id": ["PRD0001"], "nom_produit": ["Smartphone Nexora Évasion 15"],
        "date_demande": [ts("2025-09-10")], "libelle_motif": ["Taille inadaptée"], "responsabilite": ["client"],
        "statut": ["rembourse"], "montant_rembourse_ttc": [80.0]}))
    monkeypatch.setattr(donnees, "client_rfm", lambda i: pd.DataFrame({
        "date_observation": [ts("2025-06-30"), ts("2025-09-30")], "periode": ["2025-T2", "2025-T3"],
        "segment_rfm": ["Fidèles", "À risque"], "code_rfm": ["344", "244"], "cluster": ["Réguliers"] * 2})
        if i == "CLI004074" else pd.DataFrame(columns=["date_observation", "periode", "segment_rfm", "code_rfm", "cluster"]))
    monkeypatch.setattr(donnees, "client_churn_test", lambda i: pd.DataFrame({
        "date_observation": [ts("2025-03-31")], "proba_churn": [0.42], "prediction": [0], "churn_reel": [0]}))
    monkeypatch.setattr(donnees, "client_avis", lambda i: pd.DataFrame({
        "avis_id": ["AVI000033"], "date_avis": [ts("2025-09-20")], "produit_id": ["PRD0001"],
        "nom_produit": ["Smartphone Nexora Évasion 15"], "note": [1], "langue": ["derja"],
        "texte_nettoye": ["Khayeb, ma3jebnich."], "texte_fr": ["mauvais, ne m'a pas plu."],
        "themes": ["Satisfaction générale"], "polarite_globale": ["négatif"]}) if i == "CLI004074"
        else pd.DataFrame(columns=["avis_id", "date_avis", "produit_id", "nom_produit", "note", "langue",
                                   "texte_nettoye", "texte_fr", "themes", "polarite_globale"]))
    # --- fiche produit (PRD0001 : complet, rupture en janvier)
    ts = pd.Timestamp
    prod = pd.DataFrame({
        "produit_id": ["PRD0001"], "sku": ["NX-SM-015"], "nom_produit": ["Smartphone Nexora Évasion 15"],
        "marque": ["Nexora"], "categorie": ["Électronique & High-Tech"], "sous_categorie": ["Smartphones"],
        "gamme_prix": ["haut"], "statut_produit": ["actif"], "prix_catalogue_ttc": [789.0],
        "cout_achat_unitaire_ht": [520.0], "taux_tva": [0.19], "marge_brute_cible": [0.22], "taux_retour_cible": [0.03],
        "fournisseur_id": ["FRN002"], "nom_fournisseur": ["Torino Elettro"], "pays_fournisseur": ["Italie"]})
    monkeypatch.setattr(donnees, "produit_identite", lambda i: prod[prod["produit_id"] == i].reset_index(drop=True))
    monkeypatch.setattr(donnees, "produit_kpi", lambda i: pd.DataFrame({
        "produit_id": [i], "quantite_vendue": [400], "nb_commandes": [380], "nb_clients": [350], "ca_ht": [2.6e5],
        "marge_brute_ht": [6.0e4], "taux_marge": [0.23], "nb_avis": [60], "note_moyenne": [4.1],
        "quantite_retournee": [12], "taux_retour": [0.03], "montant_rembourse_ttc": [9000.0]}))
    monkeypatch.setattr(donnees, "produit_annees", lambda i: pd.DataFrame({
        "produit_id": [i] * 2, "annee": [2024, 2025], "ca_ttc": [1.0e5, 1.2e5], "ca_ht": [8.4e4, 1.0e5],
        "quantite_vendue": [130, 150], "marge_brute_ht": [1.9e4, 2.4e4], "taux_marge": [0.226, 0.24],
        "nb_commandes": [125, 140], "quantite_retournee": [5, 3], "taux_retour": [0.0385, 0.02],
        "montant_rembourse_ttc": [3900.0, 2300.0], "nb_avis": [20, 25], "note_moyenne": [4.0, 4.2]}))
    monkeypatch.setattr(donnees, "produit_ventes_mois", lambda i: pd.DataFrame({
        "mois": [ts("2025-01-01"), ts("2025-06-01"), ts("2025-12-01")], "quantite": [10, 12, 20],
        "ca_ht": [6600.0, 7900.0, 13200.0]}))
    monkeypatch.setattr(donnees, "produit_stock_mois", lambda i: pd.DataFrame({
        "mois": [ts("2024-12-01"), ts("2025-12-01")], "stock_fin_mois": [40, 12], "quantite_en_commande": [0, 0]}))
    monkeypatch.setattr(donnees, "produit_demande", lambda i: pd.DataFrame({
        "mois": [ts("2026-01-01"), ts("2026-02-01"), ts("2026-03-01")], "quantite_prevue": [8.0, 9.0, 10.0],
        "stock_depart": [12.0] * 3, "demande_cumulee": [8.0, 17.0, 27.0], "rupture_sans_reappro": [0, 1, 1]}))
    monkeypatch.setattr(donnees, "fournisseur_fiche", lambda i: pd.DataFrame({
        "fournisseur_id": [i], "nom_fournisseur": ["Torino Elettro"], "pays": ["Italie"], "est_local": [0],
        "conditions_paiement": ["60 jours"], "delai_annonce_j": [10], "delai_reel_moyen_j": [16.0],
        "fiabilite_annoncee": [0.97], "fiabilite_reelle": [0.87]}) if i == "FRN002" else pd.DataFrame())
    # --- fiche fournisseur (FRN002) : 3 fournisseurs par année pour le rang de qualité
    def annee_fournisseurs(an):
        k = 1 if an == 2025 else 0
        return pd.DataFrame({
            "fournisseur_id": ["FRN001", "FRN002", "FRN003"], "annee": [an] * 3, "nb_commandes": [20, 30 + 8 * k, 10],
            "montant_achete_ht": [1e5, 2.0e5 + 4e4 * k, 5e4], "delai_reel_moyen_j": [7.0, 13.0 + 3 * k, 5.0],
            "taux_reception": [0.99, 0.93 - 0.02 * k, 1.0], "fiabilite_reelle": [0.95, 0.70 - 0.16 * k, 0.98],
            "ca_aval_ttc": [3e5, 1.5e6 + 2e5 * k, 1e5], "quantite_vendue": [500, 2000, 200],
            "quantite_retournee": [10, 70, 2], "taux_retour": [0.02, 0.035, 0.01],
            "nom_fournisseur": ["A", "Torino Elettro", "C"], "fiabilite_annoncee": [0.95, 0.97, 0.98],
            "delai_annonce_j": [7, 10, 5]})
    monkeypatch.setattr(donnees, "fournisseurs_annee", annee_fournisseurs)
    monkeypatch.setattr(donnees, "fournisseur_achats_mois", lambda i: pd.DataFrame({
        "mois": [ts("2020-03-01"), ts("2025-01-01"), ts("2025-06-01")], "nb_commandes": [2, 3, 4],
        "montant_ht": [9000.0, 20000.0, 30000.0], "delai_reel_moyen_j": [11.0, 15.0, 17.0]}))
    monkeypatch.setattr(donnees, "fournisseur_produits", lambda i, a: pd.DataFrame({
        "id": ["PRD0001", "PRD0002"], "nom_produit": ["Smartphone Nexora Évasion 15", "Câble USB-C"],
        "categorie": ["Électronique & High-Tech"] * 2, "statut_produit": ["actif"] * 2, "ca_ttc": [1.2e5, 8e3],
        "taux_marge": [0.24, 0.40], "taux_retour": [0.02, 0.05], "rang_categorie": [2, 40],
        "stock_depart": [12.0, 380.0], "mois_rupture": [ts("2026-02-01"), pd.NaT]}))
    monkeypatch.setattr(donnees, "fournisseur_demande", lambda i: pd.DataFrame({
        "produit_id": ["PRD0001"] * 3 + ["PRD0002"] * 3, "mois": [ts("2026-01-01"), ts("2026-02-01"), ts("2026-03-01")] * 2,
        "quantite_prevue": [8.0, 9.0, 10.0, 20.0, 20.0, 20.0], "stock_depart": [12.0] * 3 + [380.0] * 3}))
    monkeypatch.setattr(donnees, "regles_categorie", lambda c, s: pd.DataFrame({
        "niveau": ["catégorie"], "consequents": ["Maison & Cuisine"], "confidence_2025": [0.18], "lift_2025": [1.31]}))
    monkeypatch.setattr(donnees, "produit_themes", lambda i: pd.DataFrame({
        "theme": ["Qualité / conformité", "Livraison"], "nb_avis": [7, 3], "nb_negatifs": [1, 2]}))
    monkeypatch.setattr(donnees, "produit_synthese_avis", lambda i: pd.DataFrame({
        "produit_id": [i], "part_derja": [0.24], "nb_incoherents": [1]}))
    monkeypatch.setattr(donnees, "produit_avis", lambda i, n=5: pd.DataFrame({
        "avis_id": ["AVI1", "AVI2"], "date_avis": [ts("2025-11-02"), ts("2025-10-01")], "client_id": ["CLI1", "CLI2"],
        "note": [5, 1], "langue": ["derja", "français"], "texte_nettoye": ["Behi barcha", "Très bon produit"],
        "themes": ["Qualité / conformité", "Satisfaction générale"], "polarite_globale": ["positif", "positif"],
        "coherence": ["cohérent", "texte positif, note basse"]}))
    # --- fiche commande (CMD0000033 : livrée 4 j en retard, 1 retour, avis livraison négatif ; CMD0000040 : annulée)
    base_cmd = {
        "date_commande": ts("2025-09-02"), "date_expedition": ts("2025-09-04"), "date_livraison": ts("2025-09-12"),
        "date_annulation": pd.NaT, "date_paiement": ts("2025-09-02"), "client_id": "CLI004074",
        "client": "Riadh Belhadj", "type_client": "particulier", "gouvernorat": "Jendouba", "region": "Nord-Ouest",
        "zone_livraison": "Z3", "libelle_canal": "Site web / mobile", "libelle_mode_paiement": "Carte bancaire",
        "statut_commande": "livree", "libelle_statut": "Livrée", "famille_statut": "aboutie", "nb_lignes": 2,
        "nb_articles": 3, "sous_total_ttc": 295.0, "remise_coupon_ttc": 0.0, "frais_livraison_ttc": 7.0,
        "montant_total_ttc": 302.0, "montant_rembourse_ttc": 80.0, "nb_tentatives_paiement": 1,
        "delai_livraison_j": 8.0, "est_livree_a_temps": 0, "est_ca_reconnu": 1, "livraison_id": "LIV0000033",
        "transporteur": "SahelLog", "statut_livraison": "livree", "est_livree": 1, "retard_j": 4.0,
        "date_prevue": ts("2025-09-08"), "date_livraison_colis": ts("2025-09-12")}
    cmds = {"CMD0000033": base_cmd,
            "CMD0000040": {**base_cmd, "date_expedition": pd.NaT, "date_livraison": pd.NaT, "date_paiement": pd.NaT,
                           "date_annulation": ts("2025-10-03"), "statut_commande": "annulee", "libelle_statut": "Annulée",
                           "est_ca_reconnu": 0, "montant_rembourse_ttc": 0.0, "livraison_id": None, "transporteur": None,
                           "statut_livraison": None, "est_livree": None, "retard_j": None, "date_prevue": pd.NaT,
                           "date_livraison_colis": pd.NaT}}
    monkeypatch.setattr(donnees, "commande_fiche", lambda i: pd.DataFrame([{"commande_id": i, **cmds[i]}])
                        if i in cmds else pd.DataFrame())
    monkeypatch.setattr(donnees, "commande_lignes", lambda i: pd.DataFrame({
        "id": ["PRD0001", "PRD0002"], "nom_produit": ["Smartphone Nexora Évasion 15", "Câble USB-C"],
        "quantite": [1, 2], "prix_unitaire_ttc": [255.0, 20.0], "montant_ttc": [255.0, 40.0],
        "quantite_retournee": [1, 0], "montant_rembourse_ttc": [80.0, 0.0], "motif_retour": ["Défectueux", None],
        "statut_retour": ["rembourse", None]}))
    monkeypatch.setattr(donnees, "commande_avis", lambda i: pd.DataFrame({
        "avis_id": ["AVI9"], "produit_id": ["PRD0001"], "date_avis": [ts("2025-09-20")], "note": [1],
        "langue": ["français"], "texte_nettoye": ["Livraison très en retard, aucun suivi."],
        "themes": ["Livraison"], "polarite_globale": ["négatif"]}) if i == "CMD0000033" else pd.DataFrame(
        columns=["avis_id", "produit_id", "date_avis", "note", "langue", "texte_nettoye", "themes", "polarite_globale"]))
    monkeypatch.setattr(donnees, "prediction_retard", lambda i: pd.DataFrame({
        "source": ["test"], "proba_retard": [0.41], "retard_reel": [1], "date_expedition": [ts("2025-09-04")],
        "date_scoring": [pd.NaT]}))
    monkeypatch.setattr(donnees, "seuil_retard", lambda: 0.13)
    monkeypatch.setattr(donnees, "taux_retard_facteurs", lambda a: pd.DataFrame({
        "facteur": ["transporteur", "region", "jour", "ensemble"], "valeur": ["SahelLog", "Nord-Ouest", "Jeudi", "toutes"],
        "n": [900, 400, 700, 9000], "taux": [0.37, 0.21, 0.19, 0.17]}))
    # --- fiche transporteur (SahelLog : le plus en retard, en dégradation, concentré dans le Sud)
    monkeypatch.setattr(donnees, "transporteurs", lambda: pd.DataFrame({
        "transporteur_id": ["TRP01", "TRP02", "TRP03"], "nom_transporteur": ["SahelLog", "Rapid Colis", "Poste Colis Plus"],
        "couverture": ["Nationale"] * 3, "cout_base_ht": [6.5, 7.0, 5.0]}))

    def transp_annee(an):
        k = 1 if an == 2025 else 0
        return pd.DataFrame({
            "transporteur": ["SahelLog", "Rapid Colis", "Poste Colis Plus", "ensemble"],
            "colis_livres": [3000 + 600 * k, 4000, 5000, 12000 + 600 * k],
            "taux_reel": [0.30 + 0.07 * k, 0.15, 0.12, 0.17], "taux_predit": [0.17 if k else None, 0.15 if k else None, 0.13 if k else None, 0.15 if k else None],
            "retard_moyen_j": [2.2 + 0.4 * k, 1.8, 1.5, 1.9], "nb_avis": [300, 400, 500, 1200],
            "part_avis_negatifs": [0.08 + 0.02 * k, 0.05, 0.04, 0.06]})
    monkeypatch.setattr(donnees, "transporteurs_annee", transp_annee)
    monkeypatch.setattr(donnees, "retard_semestres", lambda: pd.DataFrame({
        "transporteur": ["SahelLog"] * 4 + ["ensemble"] * 4, "annee": [2024, 2024, 2025, 2025] * 2,
        "semestre": [1, 2, 1, 2] * 2, "taux": [0.28, 0.32, 0.35, 0.39, 0.16, 0.17, 0.17, 0.18]}))
    monkeypatch.setattr(donnees, "retard_regions", lambda t, a: pd.DataFrame({
        "region": ["Sud", "Grand Tunis"], "colis": [900, 1200], "taux": [0.52, 0.30]}))
    monkeypatch.setattr(donnees, "colis_en_cours", lambda t: pd.DataFrame({
        "id": ["CMD0066011", "CMD0066012"], "client_id": ["CLI000001", "CLI004074"], "gouvernorat": ["Gabès", "Tunis"],
        "region": ["Sud", "Grand Tunis"], "date_expedition": [ts("2025-12-29")] * 2, "date_prevue": [ts("2025-12-31")] * 2,
        "proba_retard": [0.72, 0.09], "alerte_retard": [1, 0]}))
    # --- voix du client
    monkeypatch.setattr(donnees, "tm_categories", lambda: ["Mode", "Électroménager"])
    monkeypatch.setattr(donnees, "tm_resume", lambda c=None, a=None: pd.Series({
        "nb_avis": 9344, "nb_commentes": 6081, "nb_derja": 1278, "nb_formulations": 19, "nb_incoherents": 0}))
    monkeypatch.setattr(donnees, "tm_themes", lambda c=None, a=None: pd.DataFrame({
        "theme": ["Satisfaction générale", "Livraison", "Taille et retours"], "mentions": [2541, 1567, 106],
        "negatives": [400, 300, 106]}))
    monkeypatch.setattr(donnees, "tm_langues", lambda c=None, a=None: pd.DataFrame({
        "langue": ["français", "derja"], "avis": [4803, 1278]}))
    monkeypatch.setattr(donnees, "tm_expressions_derja", lambda c=None, a=None, n=6: pd.DataFrame({
        "expression": ["Behi barcha, livraison fi wa9tha.", "Khayeb, ma3jebnich."],
        "sens": ["très bien, livraison à l'heure.", "mauvais, ne m'a pas plu."], "polarite": ["positif", "négatif"],
        "avis": [300, 120]}))
    monkeypatch.setattr(donnees, "tm_verification", lambda: pd.DataFrame({
        "theme": ["Livraison", "Taille et retours", "Satisfaction générale", "Satisfaction générale"],
        "polarite": ["négatif", "négatif", "négatif", "positif"], "avis": [116, 106, 183, 4606],
        "part_colis_en_retard": [0.31, 0.208, 0.366, 0.14], "part_retour": [0.009, 0.019, 0.027, 0.03],
        "motifs_lies": [None, "taille inadaptée", None, None], "part_retour_motif_lie": [None, 0.019, None, None]}))
    # --- page Modèles
    monkeypatch.setattr(donnees, "ml_modeles", lambda: pd.DataFrame({
        "cas": ["ventes", "churn", "churn", "demande", "retard"],
        "modele": ["Ridge saisonnier", "Gradient boosting", "Règle récence", "Gradient boosting v2", "Régression logistique"],
        "role": ["retenu", "retenu", "référence", "retenu", "retenu"], "mesure": ["MAPE", "AUC", "AUC", "WAPE", "AUC"],
        "sens": ["min", "max", "max", "min", "max"], "valeur_validation": [0.1, 0.82, 0.79, 0.48, 0.80],
        "valeur_test": [0.095, 0.818, 0.794, 0.475, 0.811], "gain_vs_reference": [0.375, None, None, 0.004, 0.114],
        "retenu": [1, 1, 0, 1, 1]}))
    monkeypatch.setattr(donnees, "ml_registre", lambda: pd.DataFrame({
        "nom": ["churn_production"], "cas": ["churn"], "role": ["production"], "version": ["v1.2"],
        "appris_le": ["2026-11-13"], "periode_apprentissage": ["2023-2024"], "lignes_apprentissage": [40000.0],
        "nb_variables": [30], "seuil": [0.37], "source": ["03_Prediction_Churn"], "notes": [None]}))
    monkeypatch.setattr(donnees, "ml_suivi", lambda: pd.DataFrame({
        "cas": ["retard", "churn"], "objet": ["SahelLog", "global"], "periode": ["2025-12", "2025-T4"],
        "indicateur": ["écart taux prévu / réel", "AUC"], "valeur": [0.20, 0.81], "seuil": [0.05, 0.75],
        "statut": ["alerte", "ok"]}))
    monkeypatch.setattr(donnees, "ml_suivi_historique", lambda: pd.DataFrame({
        "date_donnees": ["2025-12-31", "2025-12-31"], "cas": ["retard", "churn"],
        "indicateurs": [60, 30], "alertes": [14, 1]}))
    return donnees
