/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 06 : vue de la fiche Transporteur (schéma app, base TuniShop_ANALYTICS)
   Auteure : Sarra Abdeljaouad
   Version : 1.0 (14/11/2026), d'après la maquette 06 v2.

   Une vue au grain de la livraison, avec le transporteur, la région, l'année et le semestre
   d'expédition, le retard et la probabilité prédite (test 2025). La fiche la regroupe par semestre,
   par région ou par transporteur. Retard = livrée, mais pas à temps (même définition que les fiches
   Client et Commande).
   Les colis en cours viennent de pbi.v_ml_scores_retard ; les avis de pbi.v_tm_avis_themes.

   Exécution : SSMS, instance ABDELJAOUAD, F5. Le script peut être relancé.
   Prérequis : scripts 01 à 05 exécutés.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

CREATE OR ALTER VIEW app.v_livraison_detail AS
SELECT f.livraison_id, f.commande_id, t.transporteur_id, t.nom_transporteur AS transporteur,
       g.region, g.gouvernorat, de.[date] AS date_expedition, de.annee,
       CASE WHEN de.mois <= 6 THEN 1 ELSE 2 END AS semestre,
       f.statut_livraison, f.est_livree,
       CASE WHEN f.est_livree = 1 AND f.est_livree_a_temps = 0 THEN 1 ELSE 0 END AS en_retard,
       CASE WHEN f.est_livree = 1 AND f.retard_j > 0 THEN f.retard_j END AS retard_j,
       p.proba_retard
FROM TuniShop_DWH.bi.v_fact_livraisons AS f
JOIN TuniShop_DWH.bi.v_dim_date             AS de ON de.date_sk = f.date_expedition_sk
JOIN TuniShop_DWH.bi.v_dim_transporteur     AS t  ON t.transporteur_sk = f.transporteur_sk
LEFT JOIN TuniShop_DWH.bi.v_dim_geographie  AS g  ON g.geographie_sk = f.geographie_sk
LEFT JOIN pbi.v_ml_retard                   AS p  ON p.livraison_id = f.livraison_id
WHERE f.date_expedition_sk > 0 AND t.transporteur_sk > 0;
GO

/* =============================================================================
   CONTRÔLES (à lire dans l'onglet Résultats)
   ============================================================================= */

-- T1. La vue existe (attendu : 1 ligne)
SELECT name AS vue FROM sys.views WHERE schema_id = SCHEMA_ID('app') AND name = 'v_livraison_detail';

-- T2. Une ligne par livraison expédiée (deux nombres égaux, puis 0)
SELECT (SELECT COUNT(*) FROM app.v_livraison_detail) AS lignes_vue,
       (SELECT COUNT(*) FROM TuniShop_DWH.bi.v_fact_livraisons AS f
        JOIN TuniShop_DWH.bi.v_dim_transporteur AS t ON t.transporteur_sk = f.transporteur_sk
        WHERE f.date_expedition_sk > 0 AND t.transporteur_sk > 0) AS livraisons_dwh,
       (SELECT COUNT(*) FROM (SELECT livraison_id FROM app.v_livraison_detail GROUP BY livraison_id HAVING COUNT(*) > 1) AS x) AS doublons;

-- T3. Taux de retard 2025 par transporteur, réel et prédit (le prédit vient du test 2025)
SELECT transporteur, COUNT(*) AS livrees, AVG(CAST(en_retard AS float)) AS taux_reel, AVG(proba_retard) AS taux_predit
FROM app.v_livraison_detail
WHERE annee = 2025 AND est_livree = 1
GROUP BY transporteur
ORDER BY taux_reel DESC;

PRINT N'Script 06 terminé : 1 vue (fiche Transporteur).';
GO
