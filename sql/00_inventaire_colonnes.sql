/* TuniShop - Plateforme vue 360
   Inventaire des colonnes à envoyer à Claude pour écrire les vues de la plateforme (étape 5).
   À lancer dans SSMS sur l'instance ABDELJAOUAD.
   Résultat : clic droit sur la grille > "Enregistrer les résultats sous..." > CSV.
   Fais-le pour chacune des 2 requêtes (2 fichiers CSV). */

-- Requête 1 : TuniShop_DWH, schéma bi
USE TuniShop_DWH;
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_SCHEMA = 'bi'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
GO

-- Requête 2 : TuniShop_ANALYTICS, tous les schémas (ana, pbi, ctl...)
USE TuniShop_ANALYTICS;
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS c
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION;
GO
