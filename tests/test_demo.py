"""Mode démonstration : les requêtes T-SQL de l'application, traduites pour DuckDB, sur des fichiers Parquet."""
import ast
import re
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[1]
duckdb = pytest.importorskip("duckdb")


def _sources() -> str:
    fichiers = [RACINE / "src" / "donnees.py", RACINE / "src" / "db.py", *sorted((RACINE / "pages").glob("*.py"))]
    return "".join(f.read_text(encoding="utf-8") for f in fichiers)


def test_la_liste_des_objets_exportes_suit_le_code():
    """Un objet lu par l'application mais absent de l'export ferait échouer la démo en ligne."""
    from src import demo
    lus = set(re.findall(r"\b(TuniShop_DWH\.bi\.\w+|(?:app|pbi|ana|ctl)\.\w+)\b", _sources()))
    assert lus == set(demo.OBJETS)


def test_toutes_les_requetes_se_traduisent():
    """Chaque requête complète de src/donnees.py passe la traduction T-SQL → DuckDB."""
    from src.demo import traduire
    arbre = ast.parse((RACINE / "src" / "donnees.py").read_text(encoding="utf-8"))
    morceaux_f = {id(v) for n in ast.walk(arbre) if isinstance(n, ast.JoinedStr) for v in n.values}  # pièces de f-strings
    requetes = [n.value for n in ast.walk(arbre) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in morceaux_f and re.search(r"\bSELECT\b", n.value) and "FROM" in n.value]
    assert len(requetes) > 30
    for q in requetes:
        sql = traduire(q)
        assert "N'" not in sql and "AS REAL)" not in sql.upper()


def test_traduction_des_tournures_sql_server():
    from src.demo import traduire
    sql = traduire("SELECT TOP (:n) ISNULL(x, 'a') AS y, CAST(z AS float) AS f, N'négatif' AS p, d.[date] "
                   "FROM TuniShop_DWH.bi.v_dim_date AS d WHERE d.annee = :a")
    assert "LIMIT $n" in sql and "COALESCE" in sql and "AS DOUBLE)" in sql and "'négatif'" in sql
    assert "TuniShop_DWH.bi.v_dim_date" in sql and "$a" in sql
    apply_ = traduire("SELECT a.x FROM t AS a OUTER APPLY (SELECT TOP (1) y FROM u WHERE u.k = a.k) AS p")
    assert "LEFT JOIN LATERAL" in apply_ and apply_.rstrip().endswith("ON TRUE")


@pytest.fixture
def demo_factice(tmp_path, monkeypatch):
    """Quelques fichiers Parquet et le mode démo forcé."""
    from src import demo, db
    ts = pd.Timestamp
    tables = {
        "pbi.v_ml_scores_churn": pd.DataFrame({
            "client_id": ["C1", "C2", "C3"], "alerte_churn": [1, 1, 0], "decile_risque": [1, 2, 7],
            "date_scoring": [ts("2025-12-31")] * 3, "segment_rfm": ["À risque", "Hibernants", "Fidèles"],
            "proba_churn": [0.97, 0.80, 0.10], "montant_reconnu_ttc": [1000.0, 5000.0, 300.0], "recence_j": [216, 300, 20]}),
        "app.v_client_identite": pd.DataFrame({
            "client_id": ["C1", "C2", "C3"], "nom_complet": ["Dorra Ellouze", "Omar Sfar", "Ali Ben Ali"],
            "type_client": ["particulier"] * 3, "ville": ["Béja", "Gafsa", "Tunis"],
            "action_recommandee": ["Reconquête prioritaire : offre", None, None]}),
        "app.v_client_kpi": pd.DataFrame({"client_id": ["C1", "C2"], "derniere_commande": [ts("2025-05-29"), ts("2025-03-01")]}),
        "app.v_client_rfm": pd.DataFrame({
            "client_id": ["C1", "C1", "C2"], "segment_rfm": ["Champions", "À risque", "Hibernants"],
            "date_observation": [ts("2024-06-30"), ts("2025-09-30"), ts("2025-09-30")]}),
    }
    for objet, df in tables.items():
        df.to_parquet(tmp_path / f"{objet}.parquet", index=False)
    monkeypatch.setattr(demo, "DOSSIER", tmp_path)
    monkeypatch.setattr(demo, "MANIFESTE", tmp_path / "manifeste.json")
    monkeypatch.setenv("TUNISHOP_MODE", "demo")
    demo.connexion.clear()
    db.lire.clear()
    yield demo
    demo.connexion.clear()
    db.lire.clear()


def test_requete_complete_de_l_application_en_mode_demo(demo_factice):
    """alertes_churn : TOP, OUTER APPLY avec OFFSET/FETCH, sous-requête, paramètre, tri sur une expression."""
    from src import donnees
    total, detail = donnees.alertes_churn(5)
    assert total == 2
    assert detail["id"].tolist() == ["C2", "C1"]                      # tri par risque x CA : 4 000 puis 970
    c1 = detail.set_index("id").loc["C1"]
    assert c1["segment_precedent"] == "Champions" and c1["client"] == "Dorra Ellouze"
    assert pd.Timestamp(c1["derniere_commande"]) == pd.Timestamp("2025-05-29")


def test_mode_demo_choisi_automatiquement(tmp_path, monkeypatch):
    from src import demo
    monkeypatch.delenv("TUNISHOP_MODE", raising=False)
    monkeypatch.setattr(demo, "DOSSIER", tmp_path)                   # dossier demo_data présent
    monkeypatch.setattr(demo, "_connexion_sql_configuree", lambda: False)   # Streamlit Cloud : pas de [sql]
    assert demo.actif() is True
    monkeypatch.setattr(demo, "_connexion_sql_configuree", lambda: True)    # poste avec SQL Server
    assert demo.actif() is False
    monkeypatch.setenv("TUNISHOP_MODE", "demo")                      # la variable l'emporte
    assert demo.actif() is True


def test_valeurs_vides_comme_sql_server():
    """DuckDB renvoie pd.NA pour un bit ou un entier vide ; SQL Server renvoie None ou NaN.
    Sans conversion, « if c['est_livree'] == 1 » plante (cas d'une commande annulée, recette du 17/11/2026)."""
    pytest.importorskip("duckdb")
    import duckdb
    from src import demo
    brut = duckdb.connect().execute(
        "SELECT * FROM (VALUES (TRUE, 1, 2), (NULL, NULL, 3)) AS t(est_livree, retard_j, n)").df()
    df = demo.comme_sql_server(brut)
    assert df.loc[1, "est_livree"] is None
    assert df.loc[0, "est_livree"] == True  # noqa: E712
    assert df["retard_j"].dtype == "float64" and pd.isna(df.loc[1, "retard_j"])
    assert df["n"].dtype.kind == "i"
    assert not (df.loc[1, "est_livree"] == 1)   # ne lève plus d'erreur
