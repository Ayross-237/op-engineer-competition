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

def get_programs(school_id: int) -> list[tuple[int, str, str, str]]:
    """
    returns the list of programs (weekly recurring tutoring slots) for a school.

    Returns: [
        (id: int, day: str, start: timestamp, end: timestamp)
    ]
    """
    response = (
        client.table("programs")
        .select("id", "day_of_week", "start_time", "end_time")
        .eq("school_id", school_id)
        .execute()
    )
    data: Any = response.data
    return [(p["id"], p["day_of_week"], p["start_time"], p["end_time"]) for p in data]

def get_students(program_id: int, wants_catering=True) -> list[tuple[int, list[str]]]:
    """
    returns the list of students enrolled in the given program.

    Returns: [
        (id: int, dietary: list[str])
    ]
    """
    response = (
        client.table("enrolments")
        .select("students(id, dietary, wants_catering)")
        .eq("program_id", program_id)
        .execute()
    )
    data: Any = response.data
    return [
        (e["students"]["id"], e["students"]["dietary"])
        for e in data
        if e.get("students") and e["students"]["wants_catering"] == wants_catering
    ]

def get_sessions(program_id: int, dates: list[str]) -> list[str]:
    """
    Returns the dates on which the given program has a scheduled session,
    restricted to the supplied list of candidate dates.
    """
    response = (
        client.table("sessions")
        .select("date")
        .eq("program_id", program_id)
        .in_("date", dates)
        .execute()
    )
    data: Any = response.data
    return [s["date"] for s in data]

def get_students_for_session(program_id: int, session_date: str, wants_catering=True) -> list[tuple[int, list[str]]]:
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

    return [(sid, diet) for sid, diet in enrolled if sid not in absent_ids]