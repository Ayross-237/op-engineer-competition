-- Drops everything created by db/schema.sql so the schema can be re-applied cleanly.

DROP TABLE IF EXISTS pricing_structures, items, enrolments, sessions, students, schools, caterers CASCADE;
DROP TYPE IF EXISTS dietary_tag, day_of_week;