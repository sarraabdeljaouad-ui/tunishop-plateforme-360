/* =============================================================================
   TuniShop - Plateforme vue 360
   Script 07 : diagnostic de la lenteur de la fiche Transporteur (aucune modification de la base)
   Auteure : Sarra Abdeljaouad · 17/11/2026
   Chronomètre chacune des 4 requêtes de la fiche, avec les paramètres de SahelLog et de 2025.
   Lecture : le dernier tableau des Résultats (requête, durée en ms, lignes).
   ============================================================================= */
USE TuniShop_ANALYTICS;
SET NOCOUNT ON;
IF OBJECT_ID('tempdb..#mesures') IS NOT NULL DROP TABLE #mesures;
CREATE TABLE #mesures (n int, requete nvarchar(80), duree_ms int, lignes int);
DECLARE @t0 datetime2, @n int;

-- 0a. lecture seule de la vue des livraisons (base des requêtes 1 à 3)
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r0a') IS NOT NULL DROP TABLE #r0a;
SELECT * INTO #r0a FROM app.v_livraison_detail;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (-2, N'0a. lecture de app.v_livraison_detail', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

-- 0b. lecture seule des prédictions de retard jointes par cette vue
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r0b') IS NOT NULL DROP TABLE #r0b;
SELECT * INTO #r0b FROM pbi.v_ml_retard;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (-1, N'0b. lecture de pbi.v_ml_retard', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

-- 1. chiffres par transporteur (2025)
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r1') IS NOT NULL DROP TABLE #r1;
WITH l AS (
            SELECT transporteur, est_livree, en_retard, retard_j, proba_retard
            FROM app.v_livraison_detail WHERE annee = 2025
        ), liv AS (
            SELECT transporteur, SUM(CASE WHEN est_livree = 1 THEN 1 ELSE 0 END) AS colis_livres,
                   AVG(CASE WHEN est_livree = 1 THEN CAST(en_retard AS float) END) AS taux_reel,
                   AVG(CASE WHEN est_livree = 1 THEN proba_retard END) AS taux_predit,
                   AVG(CAST(retard_j AS float)) AS retard_moyen_j
            FROM l GROUP BY transporteur
            UNION ALL
            SELECT 'ensemble', SUM(CASE WHEN est_livree = 1 THEN 1 ELSE 0 END),
                   AVG(CASE WHEN est_livree = 1 THEN CAST(en_retard AS float) END),
                   AVG(CASE WHEN est_livree = 1 THEN proba_retard END), AVG(CAST(retard_j AS float))
            FROM l
        ), neg AS (                       -- avis qui critiquent la livraison (un avis peut avoir plusieurs thèmes)
            SELECT DISTINCT avis_id FROM pbi.v_tm_avis_themes
            WHERE theme = N'Livraison' AND polarite = N'négatif'
        ), av AS (
            SELECT ISNULL(a.transporteur, 'inconnu') AS transporteur, COUNT(*) AS nb_avis,
                   SUM(CASE WHEN n.avis_id IS NOT NULL THEN 1 ELSE 0 END) AS nb_negatifs_livraison
            FROM pbi.v_tm_avis AS a
            LEFT JOIN neg AS n ON n.avis_id = a.avis_id
            WHERE YEAR(a.date_avis) = 2025
            GROUP BY ISNULL(a.transporteur, 'inconnu')
        ), av_tot AS (
            SELECT 'ensemble' AS transporteur, SUM(nb_avis) AS nb_avis, SUM(nb_negatifs_livraison) AS nb_negatifs_livraison
            FROM av
        )
        SELECT liv.*, x.nb_avis, CAST(x.nb_negatifs_livraison AS float) / NULLIF(x.nb_avis, 0) AS part_avis_negatifs
        INTO #r1
        FROM liv
        LEFT JOIN (SELECT * FROM av UNION ALL SELECT * FROM av_tot) AS x ON x.transporteur = liv.transporteur;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (1, N'1. chiffres par transporteur (2025)', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

-- 2. retard par semestre (toutes années)
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r2') IS NOT NULL DROP TABLE #r2;
SELECT * INTO #r2 FROM (
SELECT transporteur, annee, semestre, AVG(CAST(en_retard AS float)) AS taux
                    FROM app.v_livraison_detail WHERE est_livree = 1 GROUP BY transporteur, annee, semestre
                    UNION ALL
                    SELECT 'ensemble', annee, semestre, AVG(CAST(en_retard AS float))
                    FROM app.v_livraison_detail WHERE est_livree = 1 GROUP BY annee, semestre
) AS x;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (2, N'2. retard par semestre (toutes années)', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

-- 3. retard par région (SahelLog, 2025)
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r3') IS NOT NULL DROP TABLE #r3;
SELECT * INTO #r3 FROM (
SELECT region, COUNT(*) AS colis, AVG(CAST(en_retard AS float)) AS taux
                    FROM app.v_livraison_detail
                    WHERE transporteur = N'SahelLog' AND annee = 2025 AND est_livree = 1 AND region IS NOT NULL
                    GROUP BY region 
) AS x;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (3, N'3. retard par région (SahelLog, 2025)', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

-- 4. colis en cours (SahelLog)
SET @t0 = SYSDATETIME();
IF OBJECT_ID('tempdb..#r4') IS NOT NULL DROP TABLE #r4;
SELECT * INTO #r4 FROM (
SELECT s.commande_id AS id, c.client_id, g.gouvernorat, s.region, s.date_expedition,
                           dp.[date] AS date_prevue, s.proba_retard, s.alerte_retard
                    FROM pbi.v_ml_scores_retard AS s
                    LEFT JOIN TuniShop_DWH.bi.v_fact_livraisons AS l  ON l.livraison_id = s.livraison_id
                    LEFT JOIN TuniShop_DWH.bi.v_dim_client      AS c  ON c.client_sk = l.client_sk
                    LEFT JOIN TuniShop_DWH.bi.v_dim_geographie  AS g  ON g.geographie_sk = l.geographie_sk
                    LEFT JOIN TuniShop_DWH.bi.v_dim_date        AS dp ON dp.date_sk = l.date_prevue_sk
                    WHERE s.transporteur = N'SahelLog'
                      AND s.date_scoring = (SELECT MAX(date_scoring) FROM pbi.v_ml_scores_retard)
                    
) AS x;
SET @n = @@ROWCOUNT;
INSERT #mesures VALUES (4, N'4. colis en cours (SahelLog)', DATEDIFF(millisecond, @t0, SYSDATETIME()), @n);

SELECT requete, duree_ms, lignes FROM #mesures ORDER BY n;
GO
