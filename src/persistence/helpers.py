from collections import Counter
from typing import Any

from . import client


def get_dietary_counts_for_school(school_id: int) -> dict[str, int]:
    response = (
        client.table("schools")
        .select("sessions(enrolments(students(dietary)))")
        .eq("id", school_id)
        .execute()
    )

    data: Any = response.data
    print(data)
    counts: dict = {} 
    for school in data:
        for session in school.get("sessions") or []:
            for enrolment in session.get("enrolments") or []:
                student = enrolment.get("students")
                if student:
                    counts[student["dietary"]] = counts.get(student.dietary, 0) + 1

    return counts

def get_menu_for_school(school_id: int) -> list[tuple[str, list[str]]]:
    """
    returns a list of name, dietary pairs for the available menu for each school
    """
    response = (
        client.table("schools")
        .select("caterers(items(name, dietary_tags))")
        .eq("id", school_id)
        .execute()
    )

    data: Any = response.data
    menu: list[tuple[str, list[str]]] = []
    for school in data:
        caterer = school.get("caterers")
        if not caterer:
            continue
        for item in caterer.get("items") or []:
            menu.append((item["name"], item["dietary_tags"]))
    return menu

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