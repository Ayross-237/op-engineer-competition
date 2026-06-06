from typing import Any

from . import client

def get_schools() -> list[tuple[int, str]]:
    response = (
        client.table("schools")
        .select("id", "name")
        .execute()
    )

    data: Any = response.data
    schools: list[tuple[int, str]] = []
    for school in data:
        id = school.get("id")
        name = school.get("name")
        schools.append((id, name))

    return schools

def get_caterers() -> list[tuple[int, str]]:
    """Returns every caterer as (id, name). Drives the per-caterer order loop."""
    response = (
        client.table("caterers")
        .select("id", "name")
        .execute()
    )
    data: Any = response.data
    return [(c["id"], c["name"]) for c in data]

def get_caterer_contact(caterer_id: int) -> tuple[str, str | None, bool]:
    """Returns the dispatch contact details for a caterer.

    Returns: (contact_email, chef_email, cc_chef)
    """
    response = (
        client.table("caterers")
        .select("contact_email", "chef_email", "cc_chef")
        .eq("id", caterer_id)
        .single()
        .execute()
    )
    data: Any = response.data
    return data["contact_email"], data["chef_email"], data["cc_chef"]

def get_schools_for_caterer(caterer_id: int) -> list[tuple[int, str]]:
    """Returns the schools served by a caterer as (id, name). Inverse of get_caterer."""
    response = (
        client.table("schools")
        .select("id", "name")
        .eq("caterer_id", caterer_id)
        .execute()
    )
    data: Any = response.data
    return [(s["id"], s["name"]) for s in data]

def get_caterer(school_id: int) -> int:
    """"
    Returns the current caterer_id for the school
    """
    response = (
        client.table("schools")
        .select("caterer_id")
        .eq("id", school_id)
        .single()
        .execute()
    )
    data: Any = response.data
    return data["caterer_id"]

def get_caterer_name(caterer_id: int) -> str:
    """
    Returns the name of the caterer with the given id
    """
    response = (
        client.table("caterers")
        .select("name")
        .eq("id", caterer_id)
        .single()
        .execute()
    )
    data: Any = response.data
    return data["name"]

def get_pricing(caterer_id: int) -> tuple[float, float, float]:
    """
    Returns the per-meal and per-trip cost components for the caterer.

    Returns: (price_per_item, per_trip_fee)
    """
    response = (
        client.table("pricing_structures")
        .select("price_per_item, per_trip_fee", "per_school_per_trip_fee") 
        .eq("caterer_id", caterer_id)
        .single()
        .execute()
    )
    data: Any = response.data
    return float(data["price_per_item"]), float(data["per_trip_fee"]), float(data["per_school_per_trip_fee"])

def get_menu(caterer_id: int) -> list[tuple[str, list[str]]]:
    """
    Returns the list of available items with dietary tags from the given caterer

    Returns: [
        (name: str, dietary: list[str])
    ]
    """
    response = (
        client.table("items")
        .select("name", "dietary_tags")
        .eq("caterer_id", caterer_id)
        .execute()
    )
    data: Any = response.data
    return [(item["name"], item["dietary_tags"]) for item in data]

def get_programs(school_id: int) -> list[tuple[int, str, str, str, str, str, str, str]]:
    """
    returns the list of programs (weekly recurring tutoring slots) for a school.

    Returns: [
        (id: int, day: str, start: timestamp, end: timestamp, dinner: timestamp,
         building: str, manager_name: str, manager_mobile: str)
    ]
    """
    response = (
        client.table("programs")
        .select("id", "day_of_week", "start_time", "end_time", "dinner_time", "building", "manager_name", "manager_mobile")
        .eq("school_id", school_id)
        .execute()
    )
    data: Any = response.data
    return [
        (p["id"], p["day_of_week"], p["start_time"], p["end_time"], p["dinner_time"], p["building"], p["manager_name"], p["manager_mobile"])
        for p in data
    ]

def get_students(program_id: int, wants_catering=True) -> list[tuple[int, list[str], str | None]]:
    """
    returns the list of students enrolled in the given program.

    Returns: [
        (id: int, dietary: list[str], dietary_extra: str | None)
    ]
    """
    response = (
        client.table("enrolments")
        .select("students(id, dietary, dietary_extra, wants_catering)")
        .eq("program_id", program_id)
        .execute()
    )
    data: Any = response.data
    return [
        (e["students"]["id"], e["students"]["dietary"], e["students"]["dietary_extra"])
        for e in data
        if e.get("students") and e["students"]["wants_catering"] == wants_catering
    ]

def get_sessions(program_id: int, dates: list[str]) -> list[tuple[str, str | None, str | None]]:
    """
    Returns the scheduled sessions for a program whose date falls in the supplied list,
    including substitute-manager fields (which are None when the regular manager is running it).

    Returns: [
        (date: str, sub_manager_name: str | None, sub_manager_mobile: str | None)
    ]
    """
    response = (
        client.table("sessions")
        .select("date", "sub_manager_name", "sub_manager_mobile")
        .eq("program_id", program_id)
        .in_("date", dates)
        .execute()
    )
    data: Any = response.data
    return [
        (s["date"], s["sub_manager_name"], s["sub_manager_mobile"])
        for s in data
    ]

def get_students_for_session(program_id: int, session_date: str, wants_catering=True) -> list[tuple[int, list[str], str | None]]:
    """
    Returns the catering-eligible students for a specific dated session:
    students enrolled in the program, minus those marked absent on that date.
    """
    enrolled = get_students(program_id, wants_catering=wants_catering)

    absences = (
        client.table("absences")
        .select("student_id")
        .eq("program_id", program_id)
        .eq("date", session_date)
        .execute()
    )
    absences_data: Any = absences.data
    absent_ids = {a["student_id"] for a in absences_data}

    return [(sid, diet, extra) for sid, diet, extra in enrolled if sid not in absent_ids]

def get_feedback(caterer_id: int) -> list[tuple[str, str]]:
    """
    Returns the feedback entries left for the caterer, as (date, feedback) pairs.
    """
    response = (
        client.table("feedback")
        .select("submitted_at", "content")
        .eq("caterer_id", caterer_id)
        .execute()
    )
    data: Any = response.data
    return [(f["submitted_at"], f["content"]) for f in data]

def get_dish_ratings(caterer_id: int) -> list[tuple[str, str, int]]:
    """
    Returns the per-student dish ratings for the caterer as (item_name, date, rating)
    triples. Drives date-weighted dish scoring (menu.rank_meals).
    """
    response = (
        client.table("dish_ratings")
        .select("item_name", "date", "rating")
        .eq("caterer_id", caterer_id)
        .execute()
    )
    data: Any = response.data
    return [(r["item_name"], r["date"], r["rating"]) for r in data]

def get_meal_orders(program_id: int, date: str) -> dict[int, str]:
    """
    Returns the students who pre-ordered ("locked in") a meal for the given dated
    session, as {student_id: item_name}. A locked order overrides auto-assignment
    in build_session_report; students without a row are auto-assigned as before.
    """
    response = (
        client.table("meal_orders")
        .select("student_id", "item_name")
        .eq("program_id", program_id)
        .eq("date", date)
        .execute()
    )
    data: Any = response.data
    return {o["student_id"]: o["item_name"] for o in data}


# --- student pre-order web app ---

def get_student_by_email(email: str) -> tuple[int, str, list[str], str | None] | None:
    """Looks a student up by their school email for the (password-less) web login.

    Returns (id, name, dietary, dietary_extra) or None if no student has that email.
    """
    response = (
        client.table("students")
        .select("id", "name", "dietary", "dietary_extra")
        .eq("student_email", email)
        .limit(1)
        .execute()
    )
    data: Any = response.data
    if not data:
        return None
    s = data[0]
    return s["id"], s["name"], s["dietary"], s["dietary_extra"]

def get_student_name(student_id: int) -> str:
    """Returns a student's name by id (used to address pre-order confirmation emails)."""
    response = (
        client.table("students")
        .select("name")
        .eq("id", student_id)
        .single()
        .execute()
    )
    data: Any = response.data
    return data["name"]

def get_upcoming_sessions_for_student(student_id: int) -> list[dict[str, Any]]:
    """Returns the dated sessions a student can pre-order for: every session of every
    program they're enrolled in, minus the ones they're marked absent from.

    Each dict carries what the web UI needs to render the session and resolve its menu:
    program_id, date, school_name, caterer_id, day, start, end, dinner, building.
    """
    enrolments = (
        client.table("enrolments")
        .select("program_id")
        .eq("student_id", student_id)
        .execute()
    )
    program_ids = [e["program_id"] for e in enrolments.data]
    if not program_ids:
        return []

    programs = (
        client.table("programs")
        .select("id", "day_of_week", "start_time", "end_time", "dinner_time", "building", "schools(name, caterer_id)")
        .in_("id", program_ids)
        .execute()
    )
    program_by_id = {p["id"]: p for p in programs.data}

    sessions = (
        client.table("sessions")
        .select("program_id", "date")
        .in_("program_id", program_ids)
        .execute()
    )
    absences = (
        client.table("absences")
        .select("program_id", "date")
        .eq("student_id", student_id)
        .execute()
    )
    absent = {(a["program_id"], a["date"]) for a in absences.data}

    rows: list[dict[str, Any]] = []
    for s in sessions.data:
        pid, date = s["program_id"], s["date"]
        program = program_by_id.get(pid)
        if program is None or (pid, date) in absent:
            continue
        school = program.get("schools") or {}
        rows.append({
            "program_id": pid,
            "date": date,
            "school_name": school.get("name"),
            "caterer_id": school.get("caterer_id"),
            "day": program["day_of_week"],
            "start": program["start_time"],
            "end": program["end_time"],
            "dinner": program["dinner_time"],
            "building": program["building"],
        })
    rows.sort(key=lambda r: (r["date"], r["school_name"] or ""))
    return rows

def get_meal_order(student_id: int, program_id: int, date: str) -> str | None:
    """Returns the student's currently locked-in dish for a session, or None."""
    response = (
        client.table("meal_orders")
        .select("item_name")
        .eq("student_id", student_id)
        .eq("program_id", program_id)
        .eq("date", date)
        .limit(1)
        .execute()
    )
    data: Any = response.data
    return data[0]["item_name"] if data else None

def upsert_meal_order(student_id: int, program_id: int, date: str, caterer_id: int, item_name: str) -> None:
    """Locks in (or replaces) a student's pre-ordered dish for a session."""
    (
        client.table("meal_orders")
        .upsert(
            {
                "student_id": student_id,
                "program_id": program_id,
                "date": date,
                "caterer_id": caterer_id,
                "item_name": item_name,
            },
            on_conflict="student_id,program_id,date",
        )
        .execute()
    )

def delete_meal_order(student_id: int, program_id: int, date: str) -> None:
    """Clears a student's pre-order for a session (reverting to auto-assignment)."""
    (
        client.table("meal_orders")
        .delete()
        .eq("student_id", student_id)
        .eq("program_id", program_id)
        .eq("date", date)
        .execute()
    )

def get_dish_rating_for_session(student_id: int, caterer_id: int, date: str) -> tuple[str, int] | None:
    """Returns the student's existing rating for a session as (item_name, rating), or None.
    Used to pre-fill the rating form and show the current score in the session list."""
    response = (
        client.table("dish_ratings")
        .select("item_name", "rating")
        .eq("student_id", student_id)
        .eq("caterer_id", caterer_id)
        .eq("date", date)
        .limit(1)
        .execute()
    )
    data: Any = response.data
    if not data:
        return None
    return data[0]["item_name"], data[0]["rating"]

def record_dish_rating(student_id: int, caterer_id: int, date: str, item_name: str, rating: int) -> None:
    """Ingests a student's 1-10 rating of the dish they had at a session.

    One rating per student per session: any existing rating for that
    (student, caterer, date) is cleared first, so switching the rated dish replaces
    the old row cleanly rather than leaving two. The caller is responsible for
    validating that the dish is on the caterer's menu and rating is in 1..10.
    """
    (
        client.table("dish_ratings")
        .delete()
        .eq("student_id", student_id)
        .eq("caterer_id", caterer_id)
        .eq("date", date)
        .execute()
    )
    (
        client.table("dish_ratings")
        .insert(
            {
                "student_id": student_id,
                "caterer_id": caterer_id,
                "item_name": item_name,
                "date": date,
                "rating": rating,
            }
        )
        .execute()
    )