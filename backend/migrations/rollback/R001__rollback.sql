-- Rollback for V001: Balbird Intelligence Master Data
-- CAUTION: Drops newly created tables only. Never touches legacy tables.

DROP TABLE IF EXISTS bi_parts CASCADE;
DROP TABLE IF EXISTS bi_suppliers CASCADE;
DROP TABLE IF EXISTS bi_customers CASCADE;
DROP TABLE IF EXISTS bi_user_profiles CASCADE;
DROP TABLE IF EXISTS bi_departments CASCADE;
