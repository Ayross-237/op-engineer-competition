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

def get_sessions(school_id: int) -> list[tuple[int, str, str, str]]:
    """
    returns the list of sessions associated with a school.

    Returns: [
        (id: int, day: str, start: timestamp, end: timestamp)
    ]
    """
    response = (
        client.table("sessions")
        .select("id", "day_of_week", "start_time", "end_time")
        .eq("school_id", school_id)
        .execute()
    )
    data: Any = response.data
    return [(s["id"], s["day_of_week"], s["start_time"], s["end_time"]) for s in data]

def get_students(session_id: int, wants_catering=True) -> list[tuple[int, list[str]]]:
    """
    returns the list of students that are attending the given session

    Returns: [
        (id: int, dietary: list[str])
    ]
    """
    response = (
        client.table("enrolments")
        .select("students(id, dietary, wants_catering)")
        .eq("session_id", session_id)
        .execute()
    )
    data: Any = response.data
    return [
        (e["students"]["id"], e["students"]["dietary"]) 
        for e in data 
        if e.get("students") and e["students"]["wants_catering"] == wants_catering
    ]