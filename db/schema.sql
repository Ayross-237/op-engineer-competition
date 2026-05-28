-- Padea Catering — Core Schema
-- Mirrors diagrams/core-schema.drawio (conceptual) and diagrams/db-schema.drawio (physical).

CREATE TYPE day_of_week AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday');

-- V = vegetarian (students) / vegetarian option (caterer items)
-- H = halal
CREATE TYPE dietary_tag AS ENUM ('GF', 'DF', 'NF', 'V', 'H');

CREATE TABLE caterers (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           TEXT NOT NULL,
    region         TEXT,
    contact_email  TEXT NOT NULL,
    chef_email     TEXT,
    cc_chef        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
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
    dietary_extra   TEXT,
    wants_catering  BOOLEAN NOT NULL DEFAULT TRUE,
    student_email   TEXT NOT NULL,
    parent_name     TEXT NOT NULL,
    parent_email    TEXT NOT NULL,
    parent_mobile   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A program is the recurring weekly tutoring slot at a school (e.g. JPC Tuesday 4:30pm).
CREATE TABLE programs (
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
    program_id  BIGINT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, program_id)
);

-- A session is one specific occurrence of a program on a given date.
-- Weak entity of programs: composite PK (program_id, date), no surrogate id.
-- sub_manager_* are populated only when the regular manager is not running this session.
CREATE TABLE sessions (
    program_id          BIGINT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    sub_manager_name    TEXT,
    sub_manager_mobile  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (program_id, date)
);

-- M:N junction realising the absent_from relationship between students and sessions.
CREATE TABLE absences (
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    program_id  BIGINT NOT NULL,
    date        DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, program_id, date),
    FOREIGN KEY (program_id, date) REFERENCES sessions(program_id, date) ON DELETE CASCADE
);

CREATE TABLE items (
    caterer_id    BIGINT NOT NULL REFERENCES caterers(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    dietary_tags  dietary_tag[] NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (caterer_id, name)
);

-- Manager-submitted feedback about a caterer.
-- Weak entity of caterers: composite PK (caterer_id, submitted_at), no surrogate id.
-- A single caterer may accumulate many feedback entries over time.
CREATE TABLE feedback (
    caterer_id    BIGINT NOT NULL REFERENCES caterers(id) ON DELETE CASCADE,
    submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (caterer_id, submitted_at)
);

CREATE TABLE pricing_structures (
    caterer_id      BIGINT PRIMARY KEY REFERENCES caterers(id) ON DELETE CASCADE,
    price_per_item  NUMERIC(10,2) NOT NULL,
    per_trip_fee    NUMERIC(10,2) NOT NULL DEFAULT 0,
    per_school_per_trip_fee  NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
