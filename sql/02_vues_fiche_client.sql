/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 02 : vues de la fiche Client (schéma app, base TuniShop_ANALYTICS)
   Auteure : Sarra Abdeljaouad
   Version : 1.1 (14/11/2026) : note des avis par année, transporteur dans les habitudes,
             vue app.v_commande_livraison (retard par commande), d'après les maquettes.

   Complète le script 01 (identité, KPI à vie, ventes par mois, commandes, produits).
   Mêmes principes : regroupement par client_id (toutes versions du client),
   chaque source agrégée à part avant jointure, aucun calcul dans Streamlit.

   Exécution : SSMS, instance ABDELJAOUAD, F5. Le script peut être relancé.
   Prérequis : script 01 exécuté.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

/* -----------------------------------------------------------------------------
   1. KPI par année : base des comparaisons 2025 face à 2024
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_annee AS
WITH cmd AS (
    SELECT d.client_id, dt.annee,
           COUNT(*)                                                             AS nb_commandes,
           SUM(CASE WHEN f.est_ca_reconnu = 1 THEN 1 ELSE 0 END)                AS nb_commandes_reconnues,
           SUM(CASE WHEN f.est_ca_reconnu = 1 THEN f.montant_total_ttc ELSE 0 END) AS ca_reconnu_ttc,
           SUM(CASE WHEN s.statut_commande = 'annulee' THEN 1 ELSE 0 END)       AS nb_annulees
    FROM TuniShop_DWH.bi.v_fact_commandes      AS f
    JOIN TuniShop_DWH.bi.v_dim_client          AS d  ON d.client_sk = f.client_sk
    JOIN TuniShop_DWH.bi.v_dim_date            AS dt ON dt.date_sk  = f.date_commande_sk
    JOIN TuniShop_DWH.bi.v_dim_statut_commande AS s  ON s.statut_commande_sk = f.statut_commande_sk
    GROUP BY d.client_id, dt.annee
), ven AS (
    SELECT d.client_id, dt.annee,
           SUM(v.quantite) AS quantite_vendue, SUM(v.marge_brute_ht) AS marge_brute_ht
    FROM TuniShop_DWH.bi.v_fact_ventes AS v
    JOIN TuniShop_DWH.bi.v_dim_client  AS d  ON d.client_sk = v.client_sk
    JOIN TuniShop_DWH.bi.v_dim_date    AS dt ON dt.date_sk  = v.date_commande_sk
    WHERE v.est_ca_reconnu = 1
    GROUP BY d.client_id, dt.annee
), rmb AS (
    SELECT d.client_id, dt.annee,
           SUM(r.quantite) AS quantite_retournee, SUM(r.montant_rembourse_ttc) AS montant_rembourse_ttc
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_client          AS d  ON d.client_sk = r.client_sk
    JOIN TuniShop_DWH.bi.v_dim_date            AS dt ON dt.date_sk  = r.date_demande_sk
    GROUP BY d.client_id, dt.annee
), avi AS (
    SELECT d.client_id, dt.annee, COUNT(*) AS nb_avis, AVG(CAST(a.note AS float)) AS note_moyenne
    FROM TuniShop_DWH.bi.v_fact_avis  AS a
    JOIN TuniShop_DWH.bi.v_dim_client AS d  ON d.client_sk = a.client_sk
    JOIN TuniShop_DWH.bi.v_dim_date   AS dt ON dt.date_sk  = a.date_avis_sk
    GROUP BY d.client_id, dt.annee
)
SELECT cm.client_id, cm.annee, cm.nb_commandes, cm.nb_commandes_reconnues, cm.ca_reconnu_ttc,
       cm.ca_reconnu_ttc / NULLIF(cm.nb_commandes_reconnues, 0)            AS panier_moyen_ttc,
       CAST(cm.nb_annulees AS float) / NULLIF(cm.nb_commandes, 0)          AS taux_annulation,
       ISNULL(vn.marge_brute_ht, 0)                                       AS marge_brute_ht,
       ISNULL(vn.quantite_vendue, 0)                                      AS quantite_vendue,
       ISNULL(rb.quantite_retournee, 0)                                   AS quantite_retournee,
       CAST(rb.quantite_retournee AS float) / NULLIF(vn.quantite_vendue, 0) AS taux_retour,
       ISNULL(rb.montant_rembourse_ttc, 0)                                AS montant_rembourse_ttc,
       ISNULL(av.nb_avis, 0)                                              AS nb_avis,
       av.note_moyenne
FROM cmd AS cm
LEFT JOIN ven AS vn ON vn.client_id = cm.client_id AND vn.annee = cm.annee
LEFT JOIN rmb AS rb ON rb.client_id = cm.client_id AND rb.annee = cm.annee
LEFT JOIN avi AS av ON av.client_id = cm.client_id AND av.annee = cm.annee;
GO

/* -----------------------------------------------------------------------------
   2. Expérience client à vie : livraisons, paiements, remboursements, coupons, avis
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_experience AS
WITH liv AS (
    SELECT d.client_id,
           SUM(CASE WHEN l.est_livree = 1 THEN 1 ELSE 0 END)                                   AS nb_livrees,
           SUM(CASE WHEN l.est_livree = 1 AND l.est_livree_a_temps = 0 THEN 1 ELSE 0 END)      AS nb_livrees_en_retard,
           SUM(CASE WHEN l.est_livree = 0 AND l.statut_livraison NOT IN ('en_transit', 'en_preparation')
                    THEN 1 ELSE 0 END)                                                          AS nb_echecs_livraison
    FROM TuniShop_DWH.bi.v_fact_livraisons AS l
    JOIN TuniShop_DWH.bi.v_dim_client      AS d ON d.client_sk = l.client_sk
    GROUP BY d.client_id
), pai AS (
    SELECT d.client_id, COUNT(*) AS nb_tentatives_paiement,
           SUM(CASE WHEN p.est_reussi = 0 THEN 1 ELSE 0 END) AS nb_paiements_echoues
    FROM TuniShop_DWH.bi.v_fact_paiements AS p
    JOIN TuniShop_DWH.bi.v_dim_client     AS d ON d.client_sk = p.client_sk
    GROUP BY d.client_id
), rmb AS (
    SELECT d.client_id, COUNT(*) AS nb_remboursements, SUM(r.montant_rembourse_ttc) AS montant_rembourse_ttc
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_client          AS d ON d.client_sk = r.client_sk
    GROUP BY d.client_id
), cou AS (
    SELECT d.client_id, COUNT(*) AS nb_commandes,
           SUM(CASE WHEN f.coupon_sk > 0 THEN 1 ELSE 0 END) AS nb_commandes_avec_coupon,
           SUM(ISNULL(f.remise_coupon_ttc, 0))              AS remise_coupon_ttc
    FROM TuniShop_DWH.bi.v_fact_commandes AS f
    JOIN TuniShop_DWH.bi.v_dim_client     AS d ON d.client_sk = f.client_sk
    GROUP BY d.client_id
), avi AS (
    SELECT d.client_id, COUNT(*) AS nb_avis, AVG(CAST(a.note AS float)) AS note_moyenne
    FROM TuniShop_DWH.bi.v_fact_avis  AS a
    JOIN TuniShop_DWH.bi.v_dim_client AS d ON d.client_sk = a.client_sk
    GROUP BY d.client_id
)
SELECT co.client_id,
       co.nb_commandes, co.nb_commandes_avec_coupon,
       CAST(co.nb_commandes_avec_coupon AS float) / NULLIF(co.nb_commandes, 0) AS part_commandes_coupon,
       co.remise_coupon_ttc,
       ISNULL(lv.nb_livrees, 0) AS nb_livrees, ISNULL(lv.nb_livrees_en_retard, 0) AS nb_livrees_en_retard,
       CAST(lv.nb_livrees_en_retard AS float) / NULLIF(lv.nb_livrees, 0) AS taux_retard,
       ISNULL(lv.nb_echecs_livraison, 0) AS nb_echecs_livraison,
       ISNULL(pa.nb_tentatives_paiement, 0) AS nb_tentatives_paiement,
       ISNULL(pa.nb_paiements_echoues, 0)   AS nb_paiements_echoues,
       ISNULL(rb.nb_remboursements, 0)      AS nb_remboursements,
       ISNULL(rb.montant_rembourse_ttc, 0)  AS montant_rembourse_ttc,
       ISNULL(av.nb_avis, 0) AS nb_avis, av.note_moyenne
FROM cou AS co
LEFT JOIN liv AS lv ON lv.client_id = co.client_id
LEFT JOIN pai AS pa ON pa.client_id = co.client_id
LEFT JOIN rmb AS rb ON rb.client_id = co.client_id
LEFT JOIN avi AS av ON av.client_id = co.client_id;
GO

/* -----------------------------------------------------------------------------
   3. Habitudes : une ligne par client, dimension et valeur
      (canal, appareil, mode de paiement, transporteur : en commandes ; catégorie : en CA TTC reconnu)
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_habitudes AS
SELECT d.client_id, N'canal' AS dimension, c.libelle_canal AS valeur,
       COUNT(*) AS nb_commandes, SUM(f.montant_total_ttc) AS montant_ttc
FROM TuniShop_DWH.bi.v_fact_commandes AS f
JOIN TuniShop_DWH.bi.v_dim_client     AS d ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_canal      AS c ON c.canal_sk  = f.canal_sk
GROUP BY d.client_id, c.libelle_canal
UNION ALL
SELECT d.client_id, N'appareil', c.appareil, COUNT(*), SUM(f.montant_total_ttc)
FROM TuniShop_DWH.bi.v_fact_commandes AS f
JOIN TuniShop_DWH.bi.v_dim_client     AS d ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_canal      AS c ON c.canal_sk  = f.canal_sk
GROUP BY d.client_id, c.appareil
UNION ALL
SELECT d.client_id, N'mode de paiement', m.libelle_mode_paiement, COUNT(*), SUM(f.montant_total_ttc)
FROM TuniShop_DWH.bi.v_fact_commandes    AS f
JOIN TuniShop_DWH.bi.v_dim_client        AS d ON d.client_sk = f.client_sk
JOIN TuniShop_DWH.bi.v_dim_mode_paiement AS m ON m.mode_paiement_sk = f.mode_paiement_sk
GROUP BY d.client_id, m.libelle_mode_paiement
UNION ALL
SELECT d.client_id, N'catégorie', p.categorie, COUNT(DISTINCT v.commande_id), SUM(v.montant_ttc)
FROM TuniShop_DWH.bi.v_fact_ventes AS v
JOIN TuniShop_DWH.bi.v_dim_client  AS d ON d.client_sk  = v.client_sk
JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = v.produit_sk
WHERE v.est_ca_reconnu = 1
GROUP BY d.client_id, p.categorie
UNION ALL
SELECT d.client_id, N'transporteur', t.nom_transporteur, COUNT(DISTINCT l.commande_id), NULL
FROM TuniShop_DWH.bi.v_fact_livraisons  AS l
JOIN TuniShop_DWH.bi.v_dim_client       AS d ON d.client_sk = l.client_sk
JOIN TuniShop_DWH.bi.v_dim_transporteur AS t ON t.transporteur_sk = l.transporteur_sk
GROUP BY d.client_id, t.nom_transporteur;
GO

/* -----------------------------------------------------------------------------
   4. Remboursements du client, avec le motif
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_remboursements AS
SELECT d.client_id, r.remboursement_id, r.commande_id, p.produit_id, p.nom_produit,
       dt.[date] AS date_demande, m.libelle_motif, m.responsabilite, r.statut,
       r.quantite, r.montant_demande_ttc, r.montant_rembourse_ttc
FROM TuniShop_DWH.bi.v_fact_remboursements AS r
JOIN TuniShop_DWH.bi.v_dim_client          AS d  ON d.client_sk  = r.client_sk
JOIN TuniShop_DWH.bi.v_dim_produit         AS p  ON p.produit_sk = r.produit_sk
JOIN TuniShop_DWH.bi.v_dim_date            AS dt ON dt.date_sk   = r.date_demande_sk
JOIN TuniShop_DWH.bi.v_dim_motif_retour    AS m  ON m.motif_retour_sk = r.motif_retour_sk;
GO

/* -----------------------------------------------------------------------------
   5. Historique des segments RFM et des groupes k-means (data mining)
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_rfm AS
SELECT d.client_id, r.date_observation, r.periode, r.segment_rfm, r.code_rfm, r.cluster,
       r.est_derniere_observation
FROM pbi.v_dm_clients AS r
JOIN TuniShop_DWH.bi.v_dim_client AS d ON d.client_sk = r.client_sk;
GO

/* -----------------------------------------------------------------------------
   6. Prédit face au réel : test 2025 du modèle de churn
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_client_churn_test AS
SELECT d.client_id, t.date_observation, t.proba_churn, t.prediction, t.churn AS churn_reel
FROM ana.ml_pred_churn_2025 AS t
JOIN TuniShop_DWH.bi.v_dim_client AS d ON d.client_sk = t.client_sk;
GO

/* -----------------------------------------------------------------------------
   7. Livraison de chaque commande : retard, statut, transporteur, dates
      (une commande peut avoir plusieurs livraisons : on garde la plus en retard)
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_commande_livraison AS
WITH l AS (
    SELECT f.commande_id, f.livraison_id, f.statut_livraison, f.retard_j, f.est_livree, f.est_livree_a_temps,
           f.delai_livraison_j, t.nom_transporteur, de.[date] AS date_expedition, dp.[date] AS date_prevue,
           dl.[date] AS date_livraison,
           ROW_NUMBER() OVER (PARTITION BY f.commande_id ORDER BY f.retard_j DESC, f.livraison_id) AS rang
    FROM TuniShop_DWH.bi.v_fact_livraisons       AS f
    JOIN TuniShop_DWH.bi.v_dim_transporteur      AS t  ON t.transporteur_sk = f.transporteur_sk
    LEFT JOIN TuniShop_DWH.bi.v_dim_date         AS de ON de.date_sk = f.date_expedition_sk
    LEFT JOIN TuniShop_DWH.bi.v_dim_date         AS dp ON dp.date_sk = f.date_prevue_sk
    LEFT JOIN TuniShop_DWH.bi.v_dim_date         AS dl ON dl.date_sk = f.date_livraison_sk
)
SELECT commande_id, livraison_id, statut_livraison, retard_j, est_livree, est_livree_a_temps, delai_livraison_j,
       nom_transporteur AS transporteur, date_expedition, date_prevue, date_livraison
FROM l WHERE rang = 1;
GO

/* =============================================================================
   CONTRÔLES
   ============================================================================= */
-- K1. Les 7 vues existent (attendu : 7 lignes)
SELECT name AS vue FROM sys.views
WHERE schema_id = SCHEMA_ID('app')
  AND name IN ('v_client_annee', 'v_client_experience', 'v_client_habitudes',
               'v_client_remboursements', 'v_client_rfm', 'v_client_churn_test', 'v_commande_livraison');

-- K2. Le CA par année des fiches = CA reconnu du DWH (les deux nombres égaux)
SELECT (SELECT SUM(ca_reconnu_ttc) FROM app.v_client_annee) AS ca_fiches,
       (SELECT SUM(montant_total_ttc) FROM TuniShop_DWH.bi.v_fact_commandes WHERE est_ca_reconnu = 1) AS ca_dwh;

-- K3. Une ligne par client et par année (attendu : 0 ligne)
SELECT client_id, annee, COUNT(*) AS n FROM app.v_client_annee GROUP BY client_id, annee HAVING COUNT(*) > 1;

-- K4. Expérience : une ligne par client, autant de commandes qu'à vie (attendu : 0 et 0)
SELECT (SELECT COUNT(*) FROM (SELECT client_id FROM app.v_client_experience GROUP BY client_id HAVING COUNT(*) > 1) AS x) AS doublons,
       (SELECT COUNT(*) FROM app.v_client_experience AS e JOIN app.v_client_kpi AS k ON k.client_id = e.client_id
         WHERE e.nb_commandes <> k.nb_commandes) AS ecarts_commandes;

-- K6. Une ligne par commande livrée ou expédiée (attendu : 0 ligne)
SELECT commande_id, COUNT(*) AS n FROM app.v_commande_livraison GROUP BY commande_id HAVING COUNT(*) > 1;

-- K5. Fiche exemple : CLI004074
SELECT * FROM app.v_client_annee      WHERE client_id = 'CLI004074' ORDER BY annee;
SELECT * FROM app.v_client_experience WHERE client_id = 'CLI004074';
SELECT * FROM app.v_client_habitudes  WHERE client_id = 'CLI004074' ORDER BY dimension, nb_commandes DESC;

PRINT N'Script 02 terminé : 7 vues (fiche Client et livraison par commande).';
GO
