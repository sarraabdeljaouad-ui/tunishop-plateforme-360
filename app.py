"""
TuniShop - Plateforme vue 360
app.py : point d'entrée. Thème, menu latéral commun, puis la page demandée.

Lancer : streamlit run app.py
Auteure : Sarra Abdeljaouad
"""
import streamlit as st

from src import donnees, ui

st.set_page_config(page_title="TuniShop · Vue 360", page_icon="assets/icone_tunishop.svg", layout="wide")
ui.appliquer_theme()

pages = {
    "Navigation": [
        st.Page("pages/accueil.py", title="Accueil", icon=":material/home:", default=True),
        st.Page("pages/recherche.py", title="Recherche", icon=":material/search:", url_path="recherche"),
    ],
    "Fiches": [
        st.Page("pages/client.py", title="Client", icon=":material/person:", url_path="client"),
        st.Page("pages/produit.py", title="Produit", icon=":material/inventory_2:", url_path="produit"),
        st.Page("pages/fournisseur.py", title="Fournisseur", icon=":material/local_shipping:", url_path="fournisseur"),
        st.Page("pages/commande.py", title="Commande", icon=":material/receipt_long:", url_path="commande"),
        st.Page("pages/transporteur.py", title="Transporteur", icon=":material/conveyor_belt:", url_path="transporteur"),
    ],
    "Analyses": [
        st.Page("pages/voix_client.py", title="Voix du client", icon=":material/forum:", url_path="voix-du-client"),
        st.Page("pages/modeles.py", title="Modèles", icon=":material/model_training:", url_path="modeles"),
    ],
    "Outils": [
        st.Page("pages/verification.py", title="Vérification", icon=":material/fact_check:", url_path="verification"),
    ],
}

page = st.navigation(pages)
ui.menu_lateral(donnees.fraicheur())
page.run()
