"""Tests des règles de la fiche Client (niveau de risque, signaux). Lancer : pytest -v"""
import pandas as pd

from src.regles import niveau_risque, signaux


def test_niveau_par_decile():
    assert [niveau_risque(d) for d in (1, 2, 3, 5, 6, 10)] == ["élevé", "élevé", "moyen", "moyen", "faible", "faible"]
    assert niveau_risque(None) is None and niveau_risque(float("nan")) is None


def test_aucun_signal_pour_un_bon_client():
    exp = {"nb_livrees_en_retard": 1, "taux_retard": 0.1, "nb_echecs_livraison": 0,
           "nb_paiements_echoues": 0, "nb_remboursements": 0}
    annees = pd.DataFrame({"annee": [2024, 2025], "ca_reconnu_ttc": [1000.0, 1100.0]})
    assert signaux(20, exp, annees, None, "positif") == []


def test_signaux_dun_client_a_risque():
    exp = {"nb_livrees_en_retard": 3, "taux_retard": 0.375, "nb_echecs_livraison": 1,
           "nb_paiements_echoues": 2, "nb_remboursements": 1}
    annees = pd.DataFrame({"annee": [2024, 2025], "ca_reconnu_ttc": [1600.0, 600.0]})
    rfm = pd.DataFrame({"date_observation": pd.to_datetime(["2025-06-30", "2025-09-30"]),
                        "segment_rfm": ["Fidèles", "À risque"]})
    s = signaux(117, exp, annees, rfm, "négatif")
    assert s == ["117 jours sans commande", "CA 2025 en baisse de 62 % face à 2024",
                 "segment RFM passé de « Fidèles » à « À risque »",
                 "3 livraisons en retard (38 % de ses livraisons)", "1 livraison(s) en échec",
                 "2 paiement(s) échoué(s)", "1 demande(s) de remboursement", "dernier avis négatif"]


def test_seuils_exacts():
    assert signaux(89, None, None, None, None) == []
    assert signaux(90, None, None, None, None) == ["90 jours sans commande"]
    exp = {"nb_livrees_en_retard": 2, "taux_retard": 0.29}
    assert signaux(None, exp, None, None, None) == []            # 29 % < 30 %


def test_date_rupture_interpolee():
    import pandas as pd
    from src.regles import date_rupture, couverture_mois
    d = pd.DataFrame({"mois": pd.to_datetime(["2026-01-01", "2026-02-01"]), "quantite_prevue": [8.0, 9.0],
                      "stock_depart": [12.0, 12.0]})
    assert date_rupture(d) == pd.Timestamp("2026-02-13")       # 4 unités sur 9 : 0,44 x 28 j = 12 j
    assert date_rupture(d.assign(stock_depart=100.0)) is None
    assert date_rupture(d.assign(stock_depart=0.0)) == pd.Timestamp("2026-01-01")
    assert round(couverture_mois(42, 318), 2) == 0.40          # exemple de la maquette : 0,4 mois
