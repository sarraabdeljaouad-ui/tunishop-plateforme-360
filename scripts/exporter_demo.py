"""
TuniShop - Plateforme vue 360
scripts/exporter_demo.py : exporte en Parquet les vues et tables lues par l'application (dossier demo_data/),
pour faire tourner la plateforme sans SQL Server (démonstration en ligne).

À lancer sur le poste qui a SQL Server, depuis le dossier de la plateforme, .venv activé :
    python scripts/exporter_demo.py

Auteure : Sarra Abdeljaouad
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if ".venv" not in sys.executable:
    sys.exit(f"Script lancé avec {sys.executable}, hors du .venv. Active-le (.venv\\Scripts\\activate), "
             "vérifie que « (.venv) » s'affiche devant l'invite, puis relance.")
os.environ["TUNISHOP_MODE"] = "direct"                    # lire la vraie base, même si demo_data/ existe déjà
RACINE = Path(__file__).resolve().parents[1]
os.chdir(RACINE)                                          # pour trouver .streamlit/secrets.toml
sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402

from src import demo  # noqa: E402
from src.db import _config, lire  # noqa: E402


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    """Rend chaque colonne écrivable en Parquet : une colonne « objet » qui mélange des types devient du texte."""
    for col in df.columns:
        if df[col].dtype == object:
            types = {type(v) for v in df[col].dropna().head(2000)}
            if len(types) > 1:
                df[col] = df[col].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    return df


def main() -> None:
    demo.DOSSIER.mkdir(exist_ok=True)
    lignes, total = {}, 0
    print(f"Export de {len(demo.OBJETS)} objets vers {demo.DOSSIER}")
    for objet in demo.OBJETS:
        t0 = time.perf_counter()
        df = preparer(lire(f"SELECT * FROM {objet}", base="analytics"))
        f = demo.fichier(objet)
        df.to_parquet(f, index=False, compression="zstd")
        lignes[objet] = len(df)
        total += f.stat().st_size
        print(f"  {objet:<45} {len(df):>8} lignes  {f.stat().st_size / 1e6:6.2f} Mo  {time.perf_counter() - t0:5.1f} s")
    demo.MANIFESTE.write_text(json.dumps({
        "date_export": datetime.now().strftime("%d/%m/%Y"),
        "serveur": _config().get("serveur", "—"),
        "objets": lignes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Terminé : {len(lignes)} fichiers, {total / 1e6:.1f} Mo au total, manifeste écrit.")
    gros = [o for o in lignes if demo.fichier(o).stat().st_size > 50e6]
    if gros:
        print("ATTENTION : fichiers de plus de 50 Mo (limite GitHub : 100 Mo par fichier) :", gros)


if __name__ == "__main__":
    main()
