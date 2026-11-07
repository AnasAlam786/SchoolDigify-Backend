
from sqlalchemy import String, case, cast, exists, func, or_

from src.model.ClassAccess import ClassAccess
from src.model.ClassData import ClassData
from src.model.RTEInfo import RTEInfo
from src.model.StudentSessions import StudentSessions
from src.model.StudentsDB import StudentsDB


PAGE_SIZE = 10

SORT_COLUMNS = {"", "STUDENTS_NAME", "ADMISSION_DATE", "SR", "DOB"}

SEARCH_FIELDS = {
    "STUDENTS_NAME": StudentsDB.STUDENTS_NAME,
    "FATHERS_NAME": StudentsDB.FATHERS_NAME,
    "SR": StudentsDB.SR,
    "ROLL": StudentSessions.ROLL,
    "PHONE": StudentsDB.PHONE,
    "PEN": StudentsDB.PEN,
}


class StudentQueryError(ValueError):
    pass


def parse_params(args):
    search = args.get("search", "").strip()
    search_in = args.get("searchIn", "all")
    class_view = args.get("classView", "All")
    sort_by = args.get("sortBy", "")
    sort_dir = args.get("sortDir", "asc")

    filter_rte = args.get("filterRTE", "false")
    filter_pen = args.get("filterPEN", "any")
    filter_gender = args.get("filterGender", "any")
    filter_admission = args.get("filterAdmission", "any")

    try:
        page = int(args.get("page", 1))
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        raise StudentQueryError("Invalid page number.")

    if len(search) > 200:
        raise StudentQueryError("Search text is too long.")

    if search_in != "all" and search_in not in SEARCH_FIELDS:
        raise StudentQueryError("Invalid search field.")

    if class_view != "All" and not class_view.isdigit():
        raise StudentQueryError("Invalid class filter.")

    if sort_by not in SORT_COLUMNS or sort_dir not in {"asc", "desc"}:
        raise StudentQueryError("Invalid sorting option.")

    if filter_rte not in {"true", "false"}:
        raise StudentQueryError("Invalid RTE filter.")

    if filter_pen not in {"any", "present", "missing"}:
        raise StudentQueryError("Invalid PEN filter.")

    if filter_gender not in {"any", "male", "female", "other"}:
        raise StudentQueryError("Invalid gender filter.")

    if filter_admission not in {"any", "new", "old"}:
        raise StudentQueryError("Invalid admission filter.")

    return {
        "page": page,
        "search": search.lower(),
        "search_in": search_in,
        "class_view": class_view,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "filter_rte": filter_rte == "true",
        "filter_pen": filter_pen,
        "filter_gender": filter_gender,
        "filter_admission": filter_admission,
    }


def apply_filters(query, params, session_id, school_id, user_id):

    # Basic permissions and session filters
    query = query.filter(
        StudentsDB.school_id == school_id,
        StudentSessions.session_id == session_id,
        exists().where(
            ClassAccess.class_id == ClassData.id,
            ClassAccess.staff_id == user_id,
        )
    )

    # Class filter
    if params["class_view"] != "All":
        query = query.filter(
            ClassData.id == int(params["class_view"])
        )

    # RTE filter
    if params["filter_rte"]:
        query = query.filter(
            exists().where(
                RTEInfo.student_id == StudentsDB.id,
                RTEInfo.is_RTE.is_(True),
            )
        )

    # PEN filter
    if params["filter_pen"] == "present":
        query = query.filter(
            StudentsDB.PEN.isnot(None),
            func.trim(StudentsDB.PEN) != "",
        )

    elif params["filter_pen"] == "missing":
        query = query.filter(
            or_(
                StudentsDB.PEN.is_(None),
                func.trim(StudentsDB.PEN) == "",
            )
        )

    # Gender filter
    if params["filter_gender"] != "any":
        query = query.filter(
            func.lower(cast(StudentsDB.GENDER, String))
            == params["filter_gender"]
        )

    # Admission filter
    if params["filter_admission"] == "new":
        query = query.filter(
            StudentsDB.admission_session_id == session_id
        )

    elif params["filter_admission"] == "old":
        query = query.filter(
            StudentsDB.admission_session_id != session_id
        )

    # Search filter
    if params["search"]:

        fields = (
            SEARCH_FIELDS.values()
            if params["search_in"] == "all"
            else [SEARCH_FIELDS[params["search_in"]]]
        )

        for token in params["search"].split():

            conditions = []

            for column in fields:
                value = cast(column, String)
                conditions.append(
                    func.lower(value).like(f"%{token}%", escape="\\")
                )

            query = query.filter(or_(*conditions))

    return query


def apply_sorting(query, params):

    sort_by = params["sort_by"]
    sort_dir = params["sort_dir"]

    # Selected sorting
    if sort_by == "STUDENTS_NAME":
        column = func.lower(StudentsDB.STUDENTS_NAME)

    elif sort_by == "ADMISSION_DATE":
        column = StudentsDB.ADMISSION_DATE

    elif sort_by == "SR":
        column = StudentsDB.SR

    elif sort_by == "DOB":
        column = StudentsDB.DOB

    else:
        column = None

    if column is not None:

        # Keep NULL values at the end
        query = query.order_by(
            case((column.is_(None), 1), else_=0).asc()
        )

        if sort_dir == "asc":
            query = query.order_by(column.asc())
        else:
            query = query.order_by(column.desc())

    # Default sorting / secondary sorting
    if column is None:
        query = query.order_by(
            ClassData.display_order.asc(),
            StudentSessions.ROLL.asc(),
        )
    else:
        query = query.order_by(
            ClassData.display_order.asc(),
            StudentSessions.ROLL.asc(),
        )

    # Ensure stable ordering when other values are equal
    query = query.order_by(StudentSessions.id.asc())

    return query

