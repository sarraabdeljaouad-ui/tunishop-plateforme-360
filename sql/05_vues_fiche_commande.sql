/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 05 : vues de la fiche Commande (schéma app, base TuniShop_ANALYTICS)
   Auteure : Sarra Abdeljaouad
   Version : 1.0 (14/11/2026), d'après la maquette 05 v2.

   Deux vues :
     - app.v_commande_fiche  : une ligne par commande (dates du suivi, client, paiement, montants,
                               livraison la plus en retard, via app.v_commande_livraison du script 02) ;
     - app.v_commande_lignes : une ligne par produit commandé, avec son retour éventuel.
   Le risque de retard prédit vient de pbi.v_ml_retard (livraisons 2025 du test) et
   pbi.v_ml_scores_retard (colis en transit au dernier scoring).

   Exécution : SSMS, instance ABDELJAOUAD, F5. Le script peut être relancé.
   Prérequis : scripts 01 à 04 exécutés.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

/* -----------------------------------------------------------------------------
   1. En-tête de la commande
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_commande_fiche AS
WITH paiement AS (                                 -- 1er paiement réussi
    SELECT p.commande_id, MIN(dp.[date]) AS date_paiement
    FROM TuniShop_DWH.bi.v_fact_paiements AS p
    JOIN TuniShop_DWH.bi.v_dim_date       AS dp ON dp.date_sk = p.date_paiement_sk
    WHERE p.est_reussi = 1
    GROUP BY p.commande_id
)
SELECT f.commande_id, dc.[date] AS date_commande, de.[date] AS date_expedition,
       dl.[date] AS date_livraison, da.[date] AS date_annulation, pa.date_paiement,
       c.client_id, c.nom_complet AS client, c.type_client,
       g.gouvernorat, g.region, g.zone_livraison,
       ca.libelle_canal, mp.libelle_mode_paiement, s.statut_commande, s.libelle_statut, s.famille_statut,
       f.nb_lignes, f.nb_articles, f.sous_total_ttc, f.remise_coupon_ttc, f.frais_livraison_ttc,
       f.montant_total_ttc, f.montant_rembourse_ttc, f.nb_tentatives_paiement,
       f.delai_livraison_j, f.est_livree_a_temps, f.est_ca_reconnu,
       l.livraison_id, l.transporteur, l.statut_livraison, l.est_livree, l.retard_j,
       l.date_prevue, l.date_livraison AS date_livraison_colis
FROM TuniShop_DWH.bi.v_fact_commandes AS f
JOIN TuniShop_DWH.bi.v_dim_date            AS dc ON dc.date_sk = f.date_commande_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_date       AS de ON de.date_sk = f.date_expedition_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_date       AS dl ON dl.date_sk = f.date_livraison_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_date       AS da ON da.date_sk = f.date_annulation_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_client     AS c  ON c.client_sk = f.client_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_geographie AS g  ON g.geographie_sk = f.geographie_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_canal      AS ca ON ca.canal_sk = f.canal_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_mode_paiement   AS mp ON mp.mode_paiement_sk = f.mode_paiement_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_statut_commande AS s  ON s.statut_commande_sk = f.statut_commande_sk
LEFT JOIN paiement AS pa ON pa.commande_id = f.commande_id
LEFT JOIN app.v_commande_livraison AS l ON l.commande_id = f.commande_id;
GO

/* -----------------------------------------------------------------------------
   2. Lignes de la commande, avec leur retour
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_commande_lignes AS
WITH lig AS (
    SELECT v.commande_id, p.produit_id, p.nom_produit,
           SUM(v.quantite)          AS quantite,
           MAX(v.prix_unitaire_ttc) AS prix_unitaire_ttc,
           SUM(v.montant_ttc)       AS montant_ttc
    FROM TuniShop_DWH.bi.v_fact_ventes AS v
    JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = v.produit_sk
    GROUP BY v.commande_id, p.produit_id, p.nom_produit
), ret AS (
    SELECT r.commande_id, p.produit_id,
           SUM(r.quantite)              AS quantite_retournee,
           SUM(r.montant_rembourse_ttc) AS montant_rembourse_ttc,
           MAX(m.libelle_motif)         AS motif_retour,
           MAX(r.statut)                AS statut_retour
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_produit         AS p ON p.produit_sk = r.produit_sk
    LEFT JOIN TuniShop_DWH.bi.v_dim_motif_retour AS m ON m.motif_retour_sk = r.motif_retour_sk
    GROUP BY r.commande_id, p.produit_id
)
SELECT l.commande_id, l.produit_id, l.nom_produit, l.quantite, l.prix_unitaire_ttc, l.montant_ttc,
       ISNULL(rt.quantite_retournee, 0) AS quantite_retournee,
       ISNULL(rt.montant_rembourse_ttc, 0) AS montant_rembourse_ttc,
       rt.motif_retour, rt.statut_retour
FROM lig AS l
LEFT JOIN ret AS rt ON rt.commande_id = l.commande_id AND rt.produit_id = l.produit_id;
GO

/* =============================================================================
   CONTRÔLES (à lire dans l'onglet Résultats)
   ============================================================================= */

-- C1. Les 2 vues existent (attendu : 2 lignes)
SELECT name AS vue FROM sys.views
WHERE schema_id = SCHEMA_ID('app') AND name IN ('v_commande_fiche', 'v_commande_lignes');

-- C2. Une ligne par commande, autant que dans le DWH (deux nombres égaux, puis 0)
SELECT (SELECT COUNT(*) FROM app.v_commande_fiche) AS lignes_fiche,
       (SELECT COUNT(*) FROM TuniShop_DWH.bi.v_fact_commandes) AS commandes_dwh,
       (SELECT COUNT(*) FROM (SELECT commande_id FROM app.v_commande_fiche GROUP BY commande_id HAVING COUNT(*) > 1) AS x) AS doublons;

-- C3. Les lignes retrouvent le montant des ventes (deux nombres égaux)
SELECT (SELECT SUM(montant_ttc) FROM app.v_commande_lignes) AS lignes_fiche,
       (SELECT SUM(montant_ttc) FROM TuniShop_DWH.bi.v_fact_ventes) AS ventes_dwh;

-- C4. Un exemple : une commande livrée en retard, avec un retour et un avis
SELECT TOP (3) f.commande_id, f.date_commande, f.transporteur, f.retard_j, f.montant_total_ttc, f.montant_rembourse_ttc
FROM app.v_commande_fiche AS f
WHERE f.retard_j > 0 AND f.montant_rembourse_ttc > 0
  AND EXISTS (SELECT 1 FROM pbi.v_tm_avis AS a WHERE a.commande_id = f.commande_id)
ORDER BY f.date_commande DESC;

PRINT N'Script 05 terminé : 2 vues (fiche Commande).';
GO
