-- Drops everything created by db/schema.sql so the schema can be re-applied cleanly.

DROP TABLE IF EXISTS meal_orders, dish_ratings, feedback, pricing_structures, items, absences, sessions, enrolments, programs, students, schools, caterers CASCADE;
DROP TYPE IF EXISTS dietary_tag, day_of_week;
