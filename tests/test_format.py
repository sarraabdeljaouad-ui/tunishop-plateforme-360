"""Tests de l'affichage à la française. Lancer : pytest -v"""
import math

import pandas as pd

from src.format import date_fr, ecart_points, mois_fr, nombre, pct, tnd, tnd_compact, variation


def test_nombres_et_montants():
    assert nombre(12450.5) == "12 450"   # arrondi au plus proche pair, comme Python
    assert nombre(12450.56, 2) == "12 450,56"
    assert tnd(15541665.655) == "15 541 666 TND"
    assert pct(0.185) == "18,5 %"


def test_vides():
    for f in (nombre, tnd, pct, date_fr, mois_fr):
        assert f(None) == "—" and f(math.nan) == "—"


def test_variations():
    assert variation(110, 100) == "+10,0 %"
    assert variation(90, 100) == "-10,0 %"     # tiret ASCII, lu comme négatif par st.metric
    assert variation(5, 0) is None
    assert ecart_points(0.173, 0.19) == "-1,7 pt"


def test_dates():
    assert date_fr(pd.Timestamp("2026-11-14")) == "14/11/2026"
    assert date_fr("2026-11-14 15:09:20") == "14/11/2026 15:09"
    assert mois_fr("2026-03-01") == "mars 2026"


def test_montant_compact():
    assert tnd_compact(7134750.4) == "7,13 M TND"
    assert tnd_compact(845300) == "845 k TND"
    assert tnd_compact(9500) == "9 500 TND"


def test_dates_techniques_du_dwh_deviennent_vides():
    import datetime as dt
    import pandas as pd
    from src.donnees import _sans_dates_techniques
    t = _sans_dates_techniques(pd.DataFrame({
        "date_annulation": [dt.date(1900, 1, 2), dt.date(2025, 10, 3), None],
        "date_expedition": pd.to_datetime(["1900-01-01", "2025-09-04", None]),
        "montant": [1.0, 2.0, 3.0]}))
    assert t["date_annulation"].isna().tolist() == [True, False, True]
    assert t["date_expedition"].isna().tolist() == [True, False, True]
    assert t.loc[1, "date_annulation"] == pd.Timestamp("2025-10-03") and t["montant"].tolist() == [1.0, 2.0, 3.0]


def test_avis_par_transporteur_calcul_en_python(monkeypatch):
    """Même résultat que l'ancienne requête unique : part d'avis négatifs sur la livraison, par transporteur et année."""
    import pandas as pd
    from src import donnees
    donnees._avis_transporteurs.clear()
    reponses = iter([
        pd.DataFrame({"avis_id": ["A1", "A2", "A3", "A4"], "transporteur": ["SahelLog", "SahelLog", "inconnu", "TunExpress"],
                      "annee": [2025, 2025, 2025, 2024]}),
        pd.DataFrame({"avis_id": ["A1", "A4"]}),
    ])
    monkeypatch.setattr(donnees, "_lire", lambda sql, **p: next(reponses))
    t = donnees._avis_transporteurs().set_index(["annee", "transporteur"])
    assert t.loc[(2025, "SahelLog"), "nb_avis"] == 2 and t.loc[(2025, "SahelLog"), "nb_negatifs_livraison"] == 1
    assert t.loc[(2025, "ensemble"), "nb_avis"] == 3 and t.loc[(2024, "ensemble"), "nb_negatifs_livraison"] == 1
