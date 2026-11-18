/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 03 : vue de la fiche Produit (schéma app, base TuniShop_ANALYTICS)
   Auteure : Sarra Abdeljaouad
   Version : 1.0 (14/11/2026), d'après la maquette 03.

   Complète le script 01 (identité, KPI à vie, ventes et stock par mois).
   Une seule vue nouvelle : les KPI par produit et par année, base des comparaisons
   2025 face à 2024. Les autres blocs de la fiche lisent des vues existantes :
     - prévision de demande 2026 : pbi.v_ml_scores_demande ;
     - catégories achetées ensemble : pbi.v_dm_regles (règles stables uniquement) ;
     - thèmes et exemples d'avis : pbi.v_tm_avis, pbi.v_tm_avis_themes, pbi.v_tm_produits ;
     - délai réel du fournisseur : app.v_fournisseur_fiche.

   Mêmes principes que les scripts 01 et 02 : regroupement par produit_id (toutes versions),
   chaque source agrégée à part avant jointure, membres techniques (-1, -2) exclus.

   Exécution : SSMS, instance ABDELJAOUAD, F5. Le script peut être relancé.
   Prérequis : scripts 01 et 02 exécutés.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

/* -----------------------------------------------------------------------------
   1. KPI par produit et par année
      - ventes : lignes au CA reconnu, année de la commande ;
      - retours : année de la demande de remboursement ;
      - avis : année de l'avis, tous les avis (commentés ou non).
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW app.v_produit_annee AS
WITH ven AS (
    SELECT p.produit_id, dt.annee,
           SUM(v.montant_ttc)            AS ca_ttc,
           SUM(v.montant_ht)             AS ca_ht,
           SUM(v.quantite)               AS quantite_vendue,
           SUM(v.marge_brute_ht)         AS marge_brute_ht,
           COUNT(DISTINCT v.commande_id) AS nb_commandes
    FROM TuniShop_DWH.bi.v_fact_ventes AS v
    JOIN TuniShop_DWH.bi.v_dim_produit AS p  ON p.produit_sk = v.produit_sk
    JOIN TuniShop_DWH.bi.v_dim_date    AS dt ON dt.date_sk   = v.date_commande_sk
    WHERE v.est_ca_reconnu = 1 AND p.produit_sk > 0
    GROUP BY p.produit_id, dt.annee
), rmb AS (
    SELECT p.produit_id, dt.annee,
           SUM(r.quantite)              AS quantite_retournee,
           SUM(r.montant_rembourse_ttc) AS montant_rembourse_ttc
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_produit         AS p  ON p.produit_sk = r.produit_sk
    JOIN TuniShop_DWH.bi.v_dim_date            AS dt ON dt.date_sk   = r.date_demande_sk
    WHERE p.produit_sk > 0
    GROUP BY p.produit_id, dt.annee
), avi AS (
    SELECT p.produit_id, dt.annee,
           COUNT(*)                   AS nb_avis,
           AVG(CAST(a.note AS float)) AS note_moyenne
    FROM TuniShop_DWH.bi.v_fact_avis   AS a
    JOIN TuniShop_DWH.bi.v_dim_produit AS p  ON p.produit_sk = a.produit_sk
    JOIN TuniShop_DWH.bi.v_dim_date    AS dt ON dt.date_sk   = a.date_avis_sk
    WHERE p.produit_sk > 0
    GROUP BY p.produit_id, dt.annee
), cles AS (
    SELECT produit_id, annee FROM ven
    UNION SELECT produit_id, annee FROM rmb
    UNION SELECT produit_id, annee FROM avi
)
SELECT k.produit_id, k.annee,
       ISNULL(vn.ca_ttc, 0)                                             AS ca_ttc,
       ISNULL(vn.ca_ht, 0)                                              AS ca_ht,
       ISNULL(vn.quantite_vendue, 0)                                    AS quantite_vendue,
       ISNULL(vn.marge_brute_ht, 0)                                     AS marge_brute_ht,
       vn.marge_brute_ht / NULLIF(vn.ca_ht, 0)                          AS taux_marge,
       ISNULL(vn.nb_commandes, 0)                                       AS nb_commandes,
       ISNULL(rb.quantite_retournee, 0)                                 AS quantite_retournee,
       CAST(rb.quantite_retournee AS float) / NULLIF(vn.quantite_vendue, 0) AS taux_retour,
       ISNULL(rb.montant_rembourse_ttc, 0)                              AS montant_rembourse_ttc,
       ISNULL(av.nb_avis, 0)                                            AS nb_avis,
       av.note_moyenne
FROM cles AS k
LEFT JOIN ven AS vn ON vn.produit_id = k.produit_id AND vn.annee = k.annee
LEFT JOIN rmb AS rb ON rb.produit_id = k.produit_id AND rb.annee = k.annee
LEFT JOIN avi AS av ON av.produit_id = k.produit_id AND av.annee = k.annee;
GO

/* =============================================================================
   CONTRÔLES (à lire dans l'onglet Résultats)
   ============================================================================= */

-- P1. La vue existe (attendu : 1 ligne)
SELECT name AS vue FROM sys.views
WHERE schema_id = SCHEMA_ID('app') AND name = 'v_produit_annee';

-- P2. Le CA TTC des fiches produit = CA TTC des lignes reconnues du DWH, hors produit inconnu (deux nombres égaux)
SELECT (SELECT SUM(ca_ttc) FROM app.v_produit_annee) AS ca_fiches,
       (SELECT SUM(v.montant_ttc)
        FROM TuniShop_DWH.bi.v_fact_ventes AS v
        JOIN TuniShop_DWH.bi.v_dim_produit AS p ON p.produit_sk = v.produit_sk
        WHERE v.est_ca_reconnu = 1 AND p.produit_sk > 0) AS ca_dwh;

-- P3. Une ligne par produit et par année (attendu : 0 ligne)
SELECT produit_id, annee, COUNT(*) AS n FROM app.v_produit_annee GROUP BY produit_id, annee HAVING COUNT(*) > 1;

-- P4. Les sources des autres blocs répondent (attendu : 4 nombres > 0)
SELECT (SELECT COUNT(*) FROM pbi.v_ml_scores_demande)              AS lignes_demande,
       (SELECT COUNT(*) FROM pbi.v_dm_regles WHERE stable = 1)     AS regles_stables,
       (SELECT COUNT(*) FROM pbi.v_tm_avis_themes)                 AS themes_avis,
       (SELECT COUNT(*) FROM pbi.v_tm_produits)                    AS produits_text_mining;

-- P5. Les 5 meilleurs produits 2025 (pour choisir un exemple à ouvrir dans la plateforme)
SELECT TOP (5) a.produit_id, i.nom_produit, a.ca_ttc, a.quantite_vendue, a.taux_marge, a.taux_retour, a.note_moyenne
FROM app.v_produit_annee AS a
JOIN app.v_produit_identite AS i ON i.produit_id = a.produit_id
WHERE a.annee = 2025
ORDER BY a.ca_ttc DESC;

PRINT N'Script 03 terminé : 1 vue (fiche Produit).';
GO
