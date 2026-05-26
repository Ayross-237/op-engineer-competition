-- Wipes all rows from every table without touching the schema.
-- RESTART IDENTITY resets auto-generated PKs so re-populating starts at 1.

TRUNCATE TABLE
    absences,
    sessions,
    enrolments,
    items,
    pricing_structures,
    programs,
    students,
    schools,
    caterers
RESTART IDENTITY CASCADE;
