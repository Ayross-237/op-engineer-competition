-- Padea Catering — Core Schema
-- Mirrors diagrams/core-schema.drawio (conceptual) and diagrams/db-schema.drawio (physical).

CREATE TYPE day_of_week AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday');

-- V = vegetarian (students) / vegetarian option (caterer items)
-- H = halal
CREATE TYPE dietary_tag AS ENUM ('GF', 'DF', 'NF', 'V', 'H');

CREATE TABLE caterers (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    region      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE schools (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    region      TEXT,
    caterer_id  BIGINT NOT NULL REFERENCES caterers(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE students (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL,
    year_level      INTEGER NOT NULL,
    dietary         dietary_tag[] NOT NULL DEFAULT '{}',
    student_email   TEXT NOT NULL,
    parent_name     TEXT NOT NULL,
    parent_email    TEXT NOT NULL,
    parent_mobile   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    school_id       BIGINT NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
    day_of_week     day_of_week NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    dinner_time     TIME NOT NULL,
    building        TEXT NOT NULL,
    year_levels     INTEGER[] NOT NULL,
    manager_name    TEXT NOT NULL,
    manager_mobile  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE enrolments (
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    session_id  BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, session_id)
);

CREATE TABLE items (
    caterer_id    BIGINT NOT NULL REFERENCES caterers(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    dietary_tags  dietary_tag[] NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (caterer_id, name)
);

CREATE TABLE pricing_structures (
    caterer_id         BIGINT PRIMARY KEY REFERENCES caterers(id) ON DELETE CASCADE,
    price_per_item     NUMERIC(10,2) NOT NULL,
    flat_delivery_fee  NUMERIC(10,2) NOT NULL DEFAULT 0,
    per_trip_fee       NUMERIC(10,2) NOT NULL DEFAULT 0,
    per_school_fee     NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
