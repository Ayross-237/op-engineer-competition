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