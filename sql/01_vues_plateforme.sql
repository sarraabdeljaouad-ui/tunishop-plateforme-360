/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 01 : vues de lecture de la plateforme, schéma app, base TuniShop_ANALYTICS
   Auteure : Sarra Abdeljaouad
   Version : 1.1 (14/11/2026) : exclusion des membres techniques -1 Inconnu et
             -2 Non applicable dans l'index et les vues d'identité.
             1.2 (14/11/2026) : fiche fournisseur, retard compté au-delà d'une tolérance
             (3 jours ou 25 % du délai annoncé, la plus grande des deux).

   Principe
   - La plateforme ne lit QUE ces vues (et quelques vues pbi existantes).
     Aucun calcul métier dans Streamlit : tout est ici, vérifiable en SQL.
   - Les vues sont dans TuniShop_ANALYTICS et lisent le DWH par le nom en
     trois parties TuniShop_DWH.bi.<vue>, comme tes vues pbi.
   - Une vue = un bloc d'une fiche. L'application relie les blocs par
     l'identifiant métier (client_id, produit_id, fournisseur_id).
   - Dimensions à historique (client, produit) : on regroupe les faits par
     identifiant métier, toutes versions confondues, et on affiche
     l'identité de la version courante (est_courant = 1).
   - Membres techniques (clé -1 Inconnu, -2 Non applicable) : exclus de
     l'index et des fiches (sk > 0), mais gardés dans les vues de KPI,
     pour que les totaux restent égaux au DWH (contrôles C3 et C4).

   Exécution : SSMS, instance ABDELJAOUAD, F5 sur tout le script.
   Le script peut être relancé : CREATE OR ALTER remplace les vues.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

IF SCHEMA_ID('app') IS NULL EXEC('CREATE SCHEMA app');
GO

/* -----------------------------------------------------------------------------
   1. Index de recherche : une ligne par client, produit, fournisseur
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_index_recherche AS
SELECT 'Client' AS type_entite, c.client_id AS id, c.nom_complet AS libelle,
       c.ville AS detail, CAST(NULL AS varchar(30)) AS sku
FROM TuniShop_DWH.bi.v_dim_client AS c
WHERE c.est_courant = 1 AND c.est_supprime = 0 AND c.client_sk > 0
UNION ALL
SELECT 'Produit', p.produit_id, p.nom_produit,
       p.marque, p.sku
FROM TuniShop_DWH.bi.v_dim_produit AS p
WHERE p.est_courant = 1 AND p.est_supprime = 0 AND p.produit_sk > 0
UNION ALL
SELECT 'Fournisseur', f.fournisseur_id, f.nom_fournisseur,
       f.pays, CAST(NULL AS varchar(30))
FROM TuniShop_DWH.bi.v_dim_fournisseur AS f
WHERE f.est_supprime = 0 AND f.fournisseur_sk > 0;
GO

/* =============================================================================
   FICHE CLIENT
   ============================================================================= */

/* 2. Identité + score de churn le plus récent + action recommandée */
CREATE OR ALTER VIEW app.v_client_identite AS
WITH dernier_score AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY s.client_id ORDER BY s.date_scoring DESC) AS rang
    FROM pbi.v_ml_scores_churn AS s
)
SELECT c.client_id, c.nom_complet, c.type_client, c.genre, c.tranche_age,
       c.gouvernorat, c.region, c.ville, c.canal_inscription, c.date_inscription,
       c.cohorte_inscription, c.segment_fidelite, c.opt_in_email, c.opt_in_sms,
       ds.date_scoring, ds.proba_churn, ds.alerte_churn, ds.decile_risque,
       ds.segment_rfm, ds.cluster, ds.recence_j, ds.frequence, ds.montant_reconnu_ttc,
       ds.version_modele, a.action_recommandee
FROM TuniShop_DWH.bi.v_dim_client AS c
LEFT JOIN dernier_score AS ds
       ON ds.client_id = c.client_id AND ds.rang = 1
LEFT JOIN ana.dm01_actions_segments AS a
       ON a.segment_rfm = ds.segment_rfm
WHERE c.est_courant = 1 AND c.est_supprime = 0 AND c.client_sk > 0;
GO

/* 3. KPI du client sur toute sa vie */
CREATE OR ALTER VIEW app.v_client_kpi AS
SELECT d.client_id,
       COUNT(*)                                                            AS nb_commandes,
       SUM(CASE WHEN f.est_ca_reconnu = 1 THEN 1 ELSE 0 END)               AS nb_commandes_reconnues,
       SUM(CASE WHEN f.est_ca_reconnu = 1 THEN f.montant_total_ttc ELSE 0 END) AS ca_reconnu_ttc,
       SUM(CASE WHEN f.est_ca_reconnu = 1 THEN f.montant_total_ttc ELSE 0 END)
         / NULLIF(SUM(CASE WHEN f.est_ca_reconnu = 1 THEN 1 ELSE 0 END), 0) AS panier_moyen_ttc,
       SUM(ISNULL(f.montant_rembourse_ttc, 0))                             AS montant_rembourse_ttc,
       AVG(CASE WHEN f.est_livree_a_temps IS NULL THEN NULL
                WHEN f.est_livree_a_temps = 1 THEN 1.0 ELSE 0.0 END)       AS taux_livre_a_temps,
       MIN(dt.[date])                                                      AS premiere_commande,
       MAX(dt.[date])                                                      AS derniere_commande
FROM TuniShop_DWH.bi.v_fact_commandes AS f
JOIN TuniShop_DWH.bi.v_dim_client     AS d  ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_date       AS dt ON dt.date_sk  = f.date_commande_sk
GROUP BY d.client_id;
GO

/* 4. CA du client par mois (courbe) */
CREATE OR ALTER VIEW app.v_client_ventes_mois AS
SELECT d.client_id,
       DATEFROMPARTS(dt.annee, dt.mois, 1) AS mois,
       COUNT(*)                            AS nb_commandes,
       SUM(f.montant_total_ttc)            AS ca_reconnu_ttc
FROM TuniShop_DWH.bi.v_fact_commandes AS f
JOIN TuniShop_DWH.bi.v_dim_client     AS d  ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_date       AS dt ON dt.date_sk  = f.date_commande_sk
WHERE f.est_ca_reconnu = 1
GROUP BY d.client_id, DATEFROMPARTS(dt.annee, dt.mois, 1);
GO

/* 5. Détail des commandes du client (tableau des dernières commandes) */
CREATE OR ALTER VIEW app.v_client_commandes AS
SELECT d.client_id, f.commande_id, dt.[date] AS date_commande,
       s.libelle_statut, f.nb_articles, f.montant_total_ttc,
       f.remise_coupon_ttc, f.delai_livraison_j, f.est_livree_a_temps,
       f.montant_rembourse_ttc, f.est_ca_reconnu
FROM TuniShop_DWH.bi.v_fact_commandes     AS f
JOIN TuniShop_DWH.bi.v_dim_client         AS d  ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_date           AS dt ON dt.date_sk  = f.date_commande_sk
JOIN TuniShop_DWH.bi.v_dim_statut_commande AS s ON s.statut_commande_sk = f.statut_commande_sk;
GO

/* 6. Produits achetés par le client (liens client -> produit) */
CREATE OR ALTER VIEW app.v_client_produits AS
SELECT d.client_id, p.produit_id,
       MAX(p.nom_produit)     AS nom_produit,
       MAX(p.categorie)       AS categorie,
       SUM(v.quantite)        AS quantite,
       SUM(v.montant_ttc)     AS montant_ttc,
       MAX(dt.[date])         AS dernier_achat
FROM TuniShop_DWH.bi.v_fact_ventes  AS v
JOIN TuniShop_DWH.bi.v_dim_client   AS d  ON d.client_sk  = v.client_sk
JOIN TuniShop_DWH.bi.v_dim_produit  AS p  ON p.produit_sk = v.produit_sk
JOIN TuniShop_DWH.bi.v_dim_date     AS dt ON dt.date_sk   = v.date_commande_sk
WHERE v.est_ca_reconnu = 1
GROUP BY d.client_id, p.produit_id;
GO

/* =============================================================================
   FICHE PRODUIT
   ============================================================================= */

/* 7. Identité du produit + son fournisseur */
CREATE OR ALTER VIEW app.v_produit_identite AS
SELECT p.produit_id, p.sku, p.nom_produit, p.marque, p.categorie, p.sous_categorie,
       p.gamme_prix, p.statut_produit, p.prix_catalogue_ttc, p.cout_achat_unitaire_ht,
       p.taux_tva, p.marge_brute_cible, p.taux_retour_cible,
       p.fournisseur_id, f.nom_fournisseur, f.pays AS pays_fournisseur
FROM TuniShop_DWH.bi.v_dim_produit AS p
LEFT JOIN TuniShop_DWH.bi.v_dim_fournisseur AS f
       ON f.fournisseur_id = p.fournisseur_id AND f.est_supprime = 0
WHERE p.est_courant = 1 AND p.est_supprime = 0 AND p.produit_sk > 0;
GO

/* 8. KPI du produit : ventes, marge, avis, retours.
      Chaque source est agrégée à part puis jointe : pas de multiplication de lignes. */
CREATE OR ALTER VIEW app.v_produit_kpi AS
WITH ventes AS (
    SELECT p.produit_id,
           SUM(v.quantite)                AS quantite_vendue,
           COUNT(DISTINCT v.commande_id)  AS nb_commandes,
           COUNT(DISTINCT v.client_sk)    AS nb_clients,
           SUM(v.montant_ht)              AS ca_ht,
           SUM(v.marge_brute_ht)          AS marge_brute_ht
    FROM TuniShop_DWH.bi.v_fact_ventes AS v
    JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = v.produit_sk
    WHERE v.est_ca_reconnu = 1
    GROUP BY p.produit_id
), avis AS (
    SELECT p.produit_id,
           COUNT(*)                        AS nb_avis,
           AVG(CAST(a.note AS float))      AS note_moyenne
    FROM TuniShop_DWH.bi.v_fact_avis   AS a
    JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = a.produit_sk
    GROUP BY p.produit_id
), retours AS (
    SELECT p.produit_id,
           SUM(r.quantite)                 AS quantite_retournee,
           SUM(r.montant_rembourse_ttc)    AS montant_rembourse_ttc
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_produit         AS p ON p.produit_sk = r.produit_sk
    GROUP BY p.produit_id
)
SELECT i.produit_id,
       ISNULL(vt.quantite_vendue, 0)  AS quantite_vendue,
       ISNULL(vt.nb_commandes, 0)     AS nb_commandes,
       ISNULL(vt.nb_clients, 0)       AS nb_clients,
       ISNULL(vt.ca_ht, 0)            AS ca_ht,
       ISNULL(vt.marge_brute_ht, 0)   AS marge_brute_ht,
       vt.marge_brute_ht / NULLIF(vt.ca_ht, 0)                       AS taux_marge,
       ISNULL(av.nb_avis, 0)          AS nb_avis,
       av.note_moyenne,
       ISNULL(rt.quantite_retournee, 0) AS quantite_retournee,
       CAST(rt.quantite_retournee AS float) / NULLIF(vt.quantite_vendue, 0) AS taux_retour,
       ISNULL(rt.montant_rembourse_ttc, 0) AS montant_rembourse_ttc
FROM app.v_produit_identite AS i
LEFT JOIN ventes  AS vt ON vt.produit_id = i.produit_id
LEFT JOIN avis    AS av ON av.produit_id = i.produit_id
LEFT JOIN retours AS rt ON rt.produit_id = i.produit_id;
GO

/* 9. Ventes du produit par mois (courbe) */
CREATE OR ALTER VIEW app.v_produit_ventes_mois AS
SELECT p.produit_id,
       DATEFROMPARTS(dt.annee, dt.mois, 1) AS mois,
       SUM(v.quantite)       AS quantite,
       SUM(v.montant_ht)     AS ca_ht,
       SUM(v.marge_brute_ht) AS marge_brute_ht
FROM TuniShop_DWH.bi.v_fact_ventes AS v
JOIN TuniShop_DWH.bi.v_dim_produit AS p  ON p.produit_sk = v.produit_sk
JOIN TuniShop_DWH.bi.v_dim_date    AS dt ON dt.date_sk   = v.date_commande_sk
WHERE v.est_ca_reconnu = 1
GROUP BY p.produit_id, DATEFROMPARTS(dt.annee, dt.mois, 1);
GO

/* 10. Stock du produit par mois, tous entrepôts confondus */
CREATE OR ALTER VIEW app.v_produit_stock_mois AS
SELECT p.produit_id,
       DATEFROMPARTS(dt.annee, dt.mois, 1)       AS mois,
       SUM(s.stock_fin_mois)                      AS stock_fin_mois,
       SUM(s.quantite_en_commande)                AS quantite_en_commande,
       SUM(s.valeur_stock_ht)                     AS valeur_stock_ht,
       SUM(CASE WHEN s.est_rupture = 1 THEN 1 ELSE 0 END) AS nb_entrepots_en_rupture
FROM TuniShop_DWH.bi.v_fact_stock_mensuel AS s
JOIN TuniShop_DWH.bi.v_dim_produit        AS p  ON p.produit_sk = s.produit_sk
JOIN TuniShop_DWH.bi.v_dim_date           AS dt ON dt.date_sk   = s.date_sk
GROUP BY p.produit_id, DATEFROMPARTS(dt.annee, dt.mois, 1);
GO

/* La prévision de demande par produit existe déjà : pbi.v_ml_scores_demande
   (produit_id, mois, quantite_prevue, stock_depart, demande_cumulee, rupture_sans_reappro).
   L'application la lit directement : pas de nouvelle vue. */

/* =============================================================================
   FICHE FOURNISSEUR
   ============================================================================= */

/* 11. Identité + annoncé (dimension) face au réel (achats)

   Retard d'une ligne d'achat : on compare la réception à la date prévue (retard_appro_j).
   Le délai normal d'un fournisseur varie d'environ 15 % sans incident : un retard de 1 ou 2 jours
   est du bruit. La fiabilité annoncée (fiabilite_livraison) est la probabilité d'éviter un vrai
   incident. Pour comparer ce qui est comparable, un retard ne compte que s'il dépasse une
   tolérance : 3 jours ou 25 % du délai annoncé, la plus grande des deux.
   Mesuré sur le dataset : fiabilité réelle moyenne 88,5 % pour 89,5 % annoncée, corrélation 0,75
   (contre 53,3 % et 0,32 si on compte dès 1 jour). Le taux strict reste affiché pour transparence. */
CREATE OR ALTER VIEW app.v_fournisseur_fiche AS
WITH achats AS (
    SELECT a.fournisseur_sk,
           MAX(CASE WHEN 0.25 * f.delai_appro_moyen_j > 3 THEN 0.25 * f.delai_appro_moyen_j ELSE 3 END) AS tolerance_retard_j,
           COUNT(DISTINCT a.commande_fournisseur_id) AS nb_commandes,
           COUNT(*)                                  AS nb_lignes,
           SUM(a.montant_ht)                         AS montant_achete_ht,
           SUM(a.quantite_commandee)                 AS quantite_commandee,
           SUM(a.quantite_recue)                     AS quantite_recue,
           AVG(CAST(a.delai_appro_reel_j AS float))  AS delai_reel_moyen_j,
           AVG(CASE WHEN a.retard_appro_j IS NULL THEN NULL
                    WHEN a.retard_appro_j > 0 THEN 1.0 ELSE 0.0 END) AS taux_retard_strict,
           AVG(CASE WHEN a.retard_appro_j IS NULL THEN NULL
                    WHEN a.retard_appro_j > CASE WHEN 0.25 * f.delai_appro_moyen_j > 3
                                                 THEN 0.25 * f.delai_appro_moyen_j ELSE 3 END
                    THEN 1.0 ELSE 0.0 END) AS taux_retard,
           AVG(CASE WHEN a.retard_appro_j > 0 THEN CAST(a.retard_appro_j AS float) END) AS retard_moyen_j
    FROM TuniShop_DWH.bi.v_fact_achats_fournisseur AS a
    JOIN TuniShop_DWH.bi.v_dim_fournisseur AS f ON f.fournisseur_sk = a.fournisseur_sk
    GROUP BY a.fournisseur_sk
)
SELECT f.fournisseur_id, f.nom_fournisseur, f.pays, f.est_local, f.conditions_paiement,
       f.delai_appro_moyen_j                                  AS delai_annonce_j,
       f.fiabilite_livraison                                  AS fiabilite_annoncee,
       ISNULL(x.nb_commandes, 0)                              AS nb_commandes,
       ISNULL(x.montant_achete_ht, 0)                         AS montant_achete_ht,
       x.delai_reel_moyen_j,
       x.delai_reel_moyen_j - f.delai_appro_moyen_j           AS ecart_delai_j,
       x.tolerance_retard_j,
       1 - x.taux_retard                                      AS fiabilite_reelle,
       (1 - x.taux_retard) - f.fiabilite_livraison            AS ecart_fiabilite,
       x.taux_retard, x.taux_retard_strict, x.retard_moyen_j,
       CAST(x.quantite_recue AS float) / NULLIF(x.quantite_commandee, 0) AS taux_reception
FROM TuniShop_DWH.bi.v_dim_fournisseur AS f
LEFT JOIN achats AS x ON x.fournisseur_sk = f.fournisseur_sk
WHERE f.est_supprime = 0 AND f.fournisseur_sk > 0;
GO

/* 12. Achats du fournisseur par mois (courbe) */
CREATE OR ALTER VIEW app.v_fournisseur_achats_mois AS
SELECT f.fournisseur_id,
       DATEFROMPARTS(dt.annee, dt.mois, 1)        AS mois,
       COUNT(DISTINCT a.commande_fournisseur_id)  AS nb_commandes,
       SUM(a.montant_ht)                          AS montant_ht,
       AVG(CAST(a.delai_appro_reel_j AS float))   AS delai_reel_moyen_j
FROM TuniShop_DWH.bi.v_fact_achats_fournisseur AS a
JOIN TuniShop_DWH.bi.v_dim_fournisseur         AS f  ON f.fournisseur_sk = a.fournisseur_sk
JOIN TuniShop_DWH.bi.v_dim_date                AS dt ON dt.date_sk = a.date_commande_sk
GROUP BY f.fournisseur_id, DATEFROMPARTS(dt.annee, dt.mois, 1);
GO

/* 13. Portefeuille : produits du fournisseur avec leurs KPI (liens fournisseur -> produit) */
CREATE OR ALTER VIEW app.v_fournisseur_produits AS
SELECT i.fournisseur_id, i.produit_id, i.nom_produit, i.categorie, i.statut_produit,
       k.quantite_vendue, k.ca_ht, k.taux_marge, k.note_moyenne, k.taux_retour
FROM app.v_produit_identite AS i
JOIN app.v_produit_kpi      AS k ON k.produit_id = i.produit_id;
GO

/* =============================================================================
   CONTRÔLES (à lancer après création ; résultats à noter dans la recette)
   ============================================================================= */
-- C1. Les 13 vues existent
SELECT name AS vue FROM sys.views WHERE schema_id = SCHEMA_ID('app') ORDER BY name;

-- C2. Index : nombre d'entités par type (attendu v1.1 : 16 000 clients, 596 produits, 40 fournisseurs)
SELECT type_entite, COUNT(*) AS nb, COUNT(DISTINCT id) AS nb_id_distincts
FROM app.v_index_recherche GROUP BY type_entite;

-- C3. Le CA total des fiches clients = CA reconnu du DWH (les deux nombres doivent être égaux)
SELECT (SELECT SUM(ca_reconnu_ttc) FROM app.v_client_kpi) AS ca_fiches_clients,
       (SELECT SUM(montant_total_ttc) FROM TuniShop_DWH.bi.v_fact_commandes WHERE est_ca_reconnu = 1) AS ca_dwh;

-- C4. Le CA HT des fiches produits = CA HT reconnu du DWH
--     (égaux, sauf ventes rattachées au produit -1 Inconnu ou à un produit supprimé : voir C7)
SELECT (SELECT SUM(ca_ht) FROM app.v_produit_kpi) AS ca_fiches_produits,
       (SELECT SUM(montant_ht) FROM TuniShop_DWH.bi.v_fact_ventes WHERE est_ca_reconnu = 1) AS ca_dwh;

-- C5. Une seule ligne par identifiant dans les vues "fiche" (attendu : 0 ligne)
SELECT 'client' AS fiche, client_id AS id, COUNT(*) AS n FROM app.v_client_identite GROUP BY client_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'produit', produit_id, COUNT(*) FROM app.v_produit_identite GROUP BY produit_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'fournisseur', fournisseur_id, COUNT(*) FROM app.v_fournisseur_fiche GROUP BY fournisseur_id HAVING COUNT(*) > 1;

-- C6. Exemple de fiche complète pour un client (remplace l'identifiant si besoin)
SELECT * FROM app.v_client_identite WHERE client_id = 'CLI004074';
SELECT * FROM app.v_client_kpi      WHERE client_id = 'CLI004074';

-- C8. Fiabilité des fournisseurs (v1.2) : la réelle doit être proche de l'annoncée en moyenne
SELECT CAST(AVG(fiabilite_annoncee) AS DECIMAL(5,3)) AS fiabilite_annoncee_moy,
       CAST(AVG(fiabilite_reelle) AS DECIMAL(5,3))   AS fiabilite_reelle_moy,
       SUM(CASE WHEN ecart_fiabilite < -0.05 THEN 1 ELSE 0 END) AS fournisseurs_5pts_sous_annonce
FROM app.v_fournisseur_fiche;

-- C7. Aucun membre technique dans l'index ni dans les fiches (attendu : 0 ligne)
SELECT 'index' AS vue, id FROM app.v_index_recherche WHERE id IN ('-1', '-2')
UNION ALL SELECT 'client',      client_id      FROM app.v_client_identite   WHERE client_id IN ('-1', '-2')
UNION ALL SELECT 'produit',     produit_id     FROM app.v_produit_identite  WHERE produit_id IN ('-1', '-2')
UNION ALL SELECT 'fournisseur', fournisseur_id FROM app.v_fournisseur_fiche WHERE fournisseur_id IN ('-1', '-2');
