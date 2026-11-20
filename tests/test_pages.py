"""Tests des pages : l'application est exécutée par AppTest, sans navigateur ni SQL Server.
Lancer : pytest -v"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

DELAI = 30
APP = str(Path(__file__).resolve().parents[1] / "app.py")   # chemin absolu du point d'entrée


def lancer(**query):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    for k, v in query.items():
        at.query_params[k] = v
    return at


def texte(at) -> str:
    """Tout le HTML/markdown affiché par la page (les cartes KPI et tableaux sont du HTML), légendes comprises."""
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])


def test_accueil_sans_erreur(donnees_factices):
    at = lancer().run()
    assert not at.exception
    t = texte(at)
    assert "Bonjour, que cherches-tu ?" in t
    assert "Un client sur le départ" in t and "CLI004074 · churn 81 %" in t       # visite guidée
    assert "rupture le 13/02/2026" in t                                         # jour estimé, pas le mois
    assert "6,10 M TND" in t and "+24,5 %" in t                                 # CA 2025 face à 2024
    from src.ui import VERT
    assert f'color:{VERT};font-weight:600">▼ -1,7 pt' in t                      # retard en baisse : en vert
    assert "Relance avec un coupon personnalisé" in t                           # action recommandée
    assert "Fidèles → À risque" in t
    assert "CA 2026 prévu par catégorie" in t and "Total prévu 2026" in t
    assert "Commander chez" in t


def test_onglets_avec_compteurs(donnees_factices):
    at = lancer().run()
    libelles = [o.label for o in at.tabs]
    assert libelles[0] == "Churn · 1 475" and libelles[1] == "Ruptures T1 · 1"


def test_menu_lateral(donnees_factices):
    at = lancer().run()
    t = " ".join(m.value for m in at.sidebar.markdown)
    assert "Chaîne OK" in t and "31/12/2025" in t


def test_alertes_vides_affichent_un_message(donnees_factices):
    at = lancer().run()
    assert any("Aucun fournisseur" in s.value for s in at.success)


def recherche(q):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/recherche.py")
    at.query_params["q"] = q
    return at.run()


def test_recherche_avec_fautes(donnees_factices):
    at = recherche("riadh belhaj")
    assert not at.exception
    t = texte(at)
    assert "Résultats pour « riadh belhaj »" in t
    assert "<mark>Riadh</mark>" in t and "<mark>Belhadj</mark>" in t          # mots surlignés
    assert "client?id=CLI004074" in t and "Ouvrir · " in t
    assert "À risque" in t                                                      # segment sous le résultat


def test_recherche_produit_et_suggestion(donnees_factices):
    at = recherche("nexra evasion")
    t = texte(at)
    assert "Vouliez-vous dire" in t and "nexora evasion" in t
    assert "épuisé prévu en février 2026" in t


def test_recherche_sans_resultat(donnees_factices):
    at = recherche("xqwz")
    assert any("Aucun résultat" in i.value for i in at.info)


def test_accueil_envoie_vers_recherche(donnees_factices):
    at = lancer().run()
    at.main.text_input[0].set_value("riadh belhaj").run()
    assert not at.exception
    assert "Résultats pour « riadh belhaj »" in texte(at)


def fiche_client(ident):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/client.py")
    at.query_params["id"] = ident
    return at.run()


def test_fiche_client_complete(donnees_factices):
    at = fiche_client("CLI004074")
    assert not at.exception
    t = texte(at)
    assert "Riadh Belhadj" in t and "CLI004074" in t
    assert "À RETENIR" in t and "ts-retenir rouge" in t                          # risque élevé : bandeau rouge
    assert "Risque de départ élevé" in t and "décile 1 sur 10" in t
    assert "Aucun achat depuis le <b>02/09/2025</b> (120 jours)" in t
    assert "1 de ses 1 dernières commandes livrées <b>en retard</b>" in t
    assert "Relance avec un coupon personnalisé" in t
    assert "600 TND" in t and "-62,5 %" in t                                     # CA 2025 face à 2024
    assert "Récence : 120 j" in t and "Ce n'est pas une contribution" in " ".join(c.value for c in at.caption)
    assert "« Fidèles » avant le T3 25, « À risque » depuis le T3 25." in t
    assert "+4 j" in t
    assert ">SahelLog<" in t or "SahelLog</a>" in t                              # transporteur principal


def fiche_produit(ident):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/produit.py")
    at.query_params["id"] = ident
    return at.run()


def test_fiche_produit_complete(donnees_factices):
    at = fiche_produit("PRD0001")
    assert not at.exception
    t = texte(at)
    assert "Smartphone Nexora Évasion 15" in t and "SKU NX-SM-015" in t
    assert "Électronique &amp; High-Tech › Smartphones" in t
    assert "ts-retenir orange" in t                                   # rupture, mais commande encore possible
    assert "rupture vers le <b>13/02/2026</b>" in t                   # 8 u. en janvier, puis 4/9 x 28 j = 12 j
    assert "Fournisseur lent : <b>16 j réels</b> pour 10 annoncés" in t
    assert "commander avant le 28/01/2026" in t                       # 16 jours avant la rupture
    assert "+20,0 %" in t                                             # CA 2025 face à 2024
    assert "1,3 mois" in t                                            # couverture : 12 / (27 / 3)
    assert "Maison &amp; Cuisine" in t
    assert "incohérent" in t and "derja" in t and "Derja 24 %" in t


def test_fiche_client_sans_score(donnees_factices):
    at = fiche_client("CLI000001")
    assert not at.exception
    assert any("Pas de score récent" in i.value for i in at.info)
    assert any("Aucune commande en 2025" in i.value for i in at.info)


def test_fiche_sans_identifiant(donnees_factices):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/produit.py").run()
    assert any("Choisis un produit" in i.value for i in at.info)


def test_identifiant_inconnu(donnees_factices):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/fournisseur.py")
    at.query_params["id"] = "FRN999"
    at.run()
    assert any("FRN999" in e.value for e in at.error)


def test_identifiant_exact_ouvre_la_fiche(donnees_factices):
    at = lancer().run()
    at.main.text_input[0].set_value("CLI004074").run()
    assert not at.exception
    assert "À RETENIR" in texte(at) and "Riadh Belhadj" in texte(at)


def test_action_fournisseur_tiree_des_donnees(donnees_factices, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(donnees_factices, "alertes_fournisseurs", lambda n=10: (1, pd.DataFrame({
        "id": ["FRN002"], "fournisseur": ["Torino Elettro"], "pays": ["Italie"], "fiabilite_annoncee": [0.97],
        "fiabilite_reelle": [0.87], "ecart_fiabilite": [-0.10], "delai_annonce_j": [10],
        "delai_reel_moyen_j": [16.2], "tolerance_retard_j": [3.0]})))
    at = lancer().run()
    assert not at.exception
    assert "Planifier avec 16 j au lieu de 10 j" in texte(at)


def fiche_fournisseur(ident):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/fournisseur.py")
    at.query_params["id"] = ident
    return at.run()


def test_fiche_fournisseur_complete(donnees_factices):
    at = fiche_fournisseur("FRN002")
    assert not at.exception
    t = texte(at)
    assert "Torino Elettro" in t and "Partenaire depuis 2020" in t
    assert "Annonce <b>97 %</b> de ponctualité, en tient <b>54 %</b>" in t
    assert "Délai réel <b>16 j</b> pour 10 annoncés, en hausse de 3 j" in t
    assert "1 produit épuisé au T1 2026, dont <b>Smartphone Nexora Évasion 15</b>, n°2 de sa catégorie" in t
    assert "planifier avec 16 j au lieu de 10 j" in t
    # score = moyenne(54, 91, 0) = 48 : à risque, bandeau rouge (qualité : le plus de retours des 3)
    assert ">48</div>" in t and "à risque" in t and "ts-retenir rouge" in t
    assert "13/02/2026" in t and "Aucune au T1" in t
    assert "+3 j" in t and "-2,0 pt" in t                 # délai et réception face à 2024


def test_score_fournisseur():
    import pandas as pd
    from src.regles import score_fournisseurs, niveau_fournisseur
    t = score_fournisseurs(pd.DataFrame({"fiabilite_reelle": [0.9, 0.5], "taux_reception": [1.0, 0.9],
                                         "taux_retour": [0.01, 0.05]}))
    assert list(t["qualite"]) == [100.0, 0.0] and list(t["score"].round(1)) == [96.7, 46.7]
    assert niveau_fournisseur(96.7) == "fiable" and niveau_fournisseur(65) == "à surveiller"


def fiche_commande(ident):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/commande.py")
    at.query_params["id"] = ident
    return at.run()


def test_fiche_commande_en_retard(donnees_factices):
    at = fiche_commande("CMD0000033")
    assert not at.exception
    t = texte(at)
    assert "Commande CMD0000033" in t and "ts-retenir rouge" in t
    assert "Livrée avec <b>4 jours de retard</b>" in t
    assert "Le modèle l'avait <b>prédit</b> à l'expédition (41 %)" in t
    assert "1 article <b>retourné</b> (défectueux)" in t
    assert "Livrée</div><div class=\"d\">12/09/2025 · prévu 08/09/2025" in t       # étape du suivi en rouge
    assert "confirmé : retard mesuré 4 j" in t and "Retourné · défectueux" in t
    assert "Prédiction juste" in t
    assert "Transporteur SahelLog" in t and "Expédié un jeudi" in t and "37 %" in t   # 04/09/2025 = jeudi


def test_fiche_commande_annulee(donnees_factices):
    at = fiche_commande("CMD0000040")
    assert not at.exception
    t = texte(at)
    assert "Commande <b>annulée</b> le 03/10/2025" in t and "Annulée</div>" in t


def test_recherche_numero_de_commande(donnees_factices):
    at = lancer().run()
    at.main.text_input[0].set_value("cmd0000033").run()
    assert not at.exception
    assert "Commande CMD0000033" in texte(at)


def fiche_transporteur(ident):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/transporteur.py")
    at.query_params["id"] = ident
    return at.run()


def test_fiche_transporteur(donnees_factices):
    for ident in ["SahelLog", "TRP01"]:                          # nom (liens des fiches) ou identifiant
        at = fiche_transporteur(ident)
        assert not at.exception
        t = texte(at)
        assert "SahelLog" in t and "TRP01" in t and "ts-retenir rouge" in t
    assert "Le plus en retard : <b>37,0 %</b> contre 17,0 % en moyenne" in t
    assert "Dégradation continue depuis <b>S1 2024</b>" in t
    assert "Retards concentrés dans la région <b>Sud</b>" in t
    assert "prévenir le client du colis à risque" in t
    assert "le modèle sous-estime de 20,0 pt" in t and "+7,0 pt" in t
    assert "1 colis en alerte sur 2 en transit" in " ".join(c.value for c in at.caption)


def test_transporteur_inconnu(donnees_factices):
    at = fiche_transporteur("Inconnu Express")
    assert any("Inconnu Express" in e.value for e in at.error)


def test_transporteur_rupture(donnees_factices, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(donnees_factices, "retard_semestres", lambda: pd.DataFrame({
        "transporteur": ["SahelLog"] * 4 + ["ensemble"] * 4, "annee": [2024, 2024, 2025, 2025] * 2,
        "semestre": [1, 2, 1, 2] * 2, "taux": [0.086, 0.372, 0.382, 0.364, 0.11, 0.165, 0.18, 0.167]}))
    t = texte(fiche_transporteur("SahelLog"))
    assert "Rupture au <b>S2 2024</b> : retard passé de 9 % à 37 %" in t


def test_voix_du_client(donnees_factices):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/voix_client.py")
    at.run()
    assert not at.exception
    t = texte(at)
    assert "<b>21 %</b> des commentaires en derja" in t
    assert "Le thème « Satisfaction générale » domine (<b>2 541</b> mentions)" in t
    assert "Le texte suit la <b>note</b>, pas l'événement vécu" in t       # 31 % ≤ 30,8 % + 3 pt (moyenne pondérée des autres négatifs)
    assert "Behi barcha" in t and "Derja · 1 278" in t
    assert "31,0 % contre 30,8 %" in t
    at.selectbox[1].set_value("2025").run()                               # filtre d'année : pas d'erreur
    assert not at.exception


def test_page_modeles(donnees_factices):
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/modeles.py")
    at.run()
    assert not at.exception
    t = texte(at)
    assert "4 modèles en production" in t and "1 indicateur en alerte" in t
    assert "9,5 %" in t and "-37,5 % d'erreur" in t and "0,818" in t   # ventes : MAPE et gain ; churn : AUC
    assert "+3,0 %" in t                                               # churn : gain recalculé (0,818 / 0,794)
    assert "Retard de livraison" in t and "À surveiller" in t        # alerte du suivi sur le retard
    assert "churn_production" in t and "recence_j" in t
    assert "Suivi dans le temps" in t and "Alertes à chaque exécution" in t           # v0.14 : courbes de suivi
    assert "Dernière exécution (données au 31/12/2025) : 15 alertes sur 90 indicateurs" in t
    assert "Une seule exécution pour l'instant" in t
    assert "Modèle évalué, appris sur 2023-2024 · 1 alerte sur 1" in t               # pas de rejeu : repli sur « retard »


def test_modeles_historique_et_modele_de_production(donnees_factices, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(donnees_factices, "ml_suivi_historique", lambda: pd.DataFrame({
        "date_donnees": ["2025-12-31", "2025-12-31", "2026-01-31", "2026-01-31"], "cas": ["retard", "churn"] * 2,
        "indicateurs": [60, 30, 60, 30], "alertes": [14, 1, 9, 0]}))
    monkeypatch.setattr(donnees_factices, "ml_suivi", lambda: pd.DataFrame({
        "cas": ["retard_production"] * 4, "objet": ["SahelLog", "TunExpress"] * 2,
        "periode": ["2025-11", "2025-11", "2025-12", "2025-12"], "indicateur": ["écart taux prévu - réel"] * 4,
        "valeur": [-0.08, 0.01, -0.02, 0.0], "seuil": [0.05] * 4, "statut": ["ALERTE", "OK", "OK", "OK"]}))
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/modeles.py")
    at.run()
    assert not at.exception
    t = texte(at)
    assert "Dernière exécution (données au 31/01/2026) : 9 alertes sur 90 indicateurs" in t
    assert "2 exécutions depuis les données au 31/12/2025" in t
    assert "Modèle de production, réappris chaque mois sur 12 mois · 1 alerte sur 4" in t


def test_modeles_sans_historique(donnees_factices, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(donnees_factices, "ml_suivi_historique",
                        lambda: pd.DataFrame(columns=["date_donnees", "cas", "indicateurs", "alertes"]))
    at = AppTest.from_file(APP, default_timeout=DELAI)
    at.switch_page("pages/modeles.py")
    at.run()
    assert not at.exception
    assert "Historique non publié" in texte(at)


def test_remboursement_sans_retour(donnees_factices, monkeypatch):
    import pandas as pd
    lignes = donnees_factices.commande_lignes("CMD0000033").assign(quantite_retournee=0, montant_rembourse_ttc=0.0)
    monkeypatch.setattr(donnees_factices, "commande_lignes", lambda i: lignes)
    t = texte(fiche_commande("CMD0000033"))
    assert "Retour / remboursement" in t and "remboursés, sans article retourné" in t
