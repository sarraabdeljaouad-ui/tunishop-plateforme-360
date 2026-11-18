/* =============================================================================
   TuniShop - Plateforme vue 360 (Streamlit)
   Script 04 : vue de la fiche Fournisseur (schéma app, base TuniShop_ANALYTICS)
   Auteure : Sarra Abdeljaouad
   Version : 1.0 (14/11/2026), d'après la maquette 04 v2.

   Une vue nouvelle : les chiffres de chaque fournisseur par année, base des comparaisons
   2025 face à 2024 et du score sur 100 (calculé dans Streamlit, voir src/regles.py).
     - achats : année de la commande fournisseur ; retard compté au-delà de la tolérance
       max(3 j, 25 % du délai annoncé), comme app.v_fournisseur_fiche (script 01 v1.2) ;
     - aval : ventes et retours des produits du fournisseur, année de la commande client
       et année de la demande de remboursement.
   Les autres blocs lisent des vues existantes : app.v_fournisseur_fiche, app.v_fournisseur_achats_mois,
   app.v_produit_annee (script 03), pbi.v_ml_scores_demande.

   Exécution : SSMS, instance ABDELJAOUAD, F5. Le script peut être relancé.
   Prérequis : scripts 01 à 03 exécutés.
   ============================================================================= */
USE TuniShop_ANALYTICS;
GO

CREATE OR ALTER VIEW app.v_fournisseur_annee AS
WITH ach AS (
    SELECT f.fournisseur_id, dt.annee,
           COUNT(DISTINCT a.commande_fournisseur_id)  AS nb_commandes,
           SUM(a.montant_ht)                          AS montant_achete_ht,
           SUM(a.quantite_commandee)                  AS quantite_commandee,
           SUM(a.quantite_recue)                      AS quantite_recue,
           AVG(CAST(a.delai_appro_reel_j AS float))   AS delai_reel_moyen_j,
           AVG(CASE WHEN a.retard_appro_j IS NULL THEN NULL
                    WHEN a.retard_appro_j > CASE WHEN 0.25 * f.delai_appro_moyen_j > 3
                                                 THEN 0.25 * f.delai_appro_moyen_j ELSE 3 END
                    THEN 1.0 ELSE 0.0 END)            AS taux_retard
    FROM TuniShop_DWH.bi.v_fact_achats_fournisseur AS a
    JOIN TuniShop_DWH.bi.v_dim_fournisseur         AS f  ON f.fournisseur_sk = a.fournisseur_sk
    JOIN TuniShop_DWH.bi.v_dim_date                AS dt ON dt.date_sk = a.date_commande_sk
    WHERE f.fournisseur_sk > 0
    GROUP BY f.fournisseur_id, dt.annee
), ven AS (
    SELECT p.fournisseur_id, dt.annee,
           SUM(v.montant_ttc) AS ca_aval_ttc,
           SUM(v.quantite)    AS quantite_vendue
    FROM TuniShop_DWH.bi.v_fact_ventes AS v
    JOIN TuniShop_DWH.bi.v_dim_produit AS p  ON p.produit_sk = v.produit_sk
    JOIN TuniShop_DWH.bi.v_dim_date    AS dt ON dt.date_sk   = v.date_commande_sk
    WHERE v.est_ca_reconnu = 1 AND p.produit_sk > 0 AND p.fournisseur_id IS NOT NULL
    GROUP BY p.fournisseur_id, dt.annee
), rmb AS (
    SELECT p.fournisseur_id, dt.annee, SUM(r.quantite) AS quantite_retournee
    FROM TuniShop_DWH.bi.v_fact_remboursements AS r
    JOIN TuniShop_DWH.bi.v_dim_produit         AS p  ON p.produit_sk = r.produit_sk
    JOIN TuniShop_DWH.bi.v_dim_date            AS dt ON dt.date_sk   = r.date_demande_sk
    WHERE p.produit_sk > 0 AND p.fournisseur_id IS NOT NULL
    GROUP BY p.fournisseur_id, dt.annee
), cles AS (
    SELECT fournisseur_id, annee FROM ach
    UNION SELECT fournisseur_id, annee FROM ven
)
SELECT k.fournisseur_id, k.annee,
       ISNULL(ac.nb_commandes, 0)                                          AS nb_commandes,
       ISNULL(ac.montant_achete_ht, 0)                                     AS montant_achete_ht,
       ac.delai_reel_moyen_j,
       CAST(ac.quantite_recue AS float) / NULLIF(ac.quantite_commandee, 0) AS taux_reception,
       1 - ac.taux_retard                                                  AS fiabilite_reelle,
       ISNULL(vn.ca_aval_ttc, 0)                                           AS ca_aval_ttc,
       ISNULL(vn.quantite_vendue, 0)                                       AS quantite_vendue,
       ISNULL(rb.quantite_retournee, 0)                                    AS quantite_retournee,
       CAST(rb.quantite_retournee AS float) / NULLIF(vn.quantite_vendue, 0) AS taux_retour
FROM cles AS k
LEFT JOIN ach AS ac ON ac.fournisseur_id = k.fournisseur_id AND ac.annee = k.annee
LEFT JOIN ven AS vn ON vn.fournisseur_id = k.fournisseur_id AND vn.annee = k.annee
LEFT JOIN rmb AS rb ON rb.fournisseur_id = k.fournisseur_id AND rb.annee = k.annee;
GO

/* =============================================================================
   CONTRÔLES (à lire dans l'onglet Résultats)
   ============================================================================= */

-- F1. La vue existe (attendu : 1 ligne)
SELECT name AS vue FROM sys.views WHERE schema_id = SCHEMA_ID('app') AND name = 'v_fournisseur_annee';

-- F2. Achats : total de la vue = total du DWH hors membres techniques (deux nombres égaux)
SELECT (SELECT SUM(montant_achete_ht) FROM app.v_fournisseur_annee) AS achats_fiches,
       (SELECT SUM(a.montant_ht)
        FROM TuniShop_DWH.bi.v_fact_achats_fournisseur AS a
        JOIN TuniShop_DWH.bi.v_dim_fournisseur AS f ON f.fournisseur_sk = a.fournisseur_sk
        WHERE f.fournisseur_sk > 0) AS achats_dwh;

-- F3. Une ligne par fournisseur et par année (attendu : 0 ligne)
SELECT fournisseur_id, annee, COUNT(*) AS n FROM app.v_fournisseur_annee GROUP BY fournisseur_id, annee HAVING COUNT(*) > 1;

-- F4. Cohérence avec la fiche à vie : fiabilité 2023-2025 pondérée proche de app.v_fournisseur_fiche (écart faible)
SELECT TOP (5) f.fournisseur_id, f.nom_fournisseur, f.fiabilite_annoncee, f.fiabilite_reelle AS fiabilite_a_vie,
       a.fiabilite_reelle AS fiabilite_2025, a.delai_reel_moyen_j AS delai_2025, a.taux_reception, a.taux_retour
FROM app.v_fournisseur_fiche AS f
JOIN app.v_fournisseur_annee AS a ON a.fournisseur_id = f.fournisseur_id AND a.annee = 2025
ORDER BY f.ecart_fiabilite;

PRINT N'Script 04 terminé : 1 vue (fiche Fournisseur).';
GO
