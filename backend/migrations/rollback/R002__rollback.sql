-- Rollback for V002: Balbird Intelligence Business Cases
DROP TABLE IF EXISTS bi_case_links CASCADE;
DROP TABLE IF EXISTS bi_case_parties CASCADE;
DROP TABLE IF EXISTS bi_business_cases CASCADE;
DROP FUNCTION IF EXISTS bi_next_case_number();
