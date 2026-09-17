import os
import requests

from flask import session, current_app, url_for
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from src.model.Schools import Schools
from src.model.Sessions import Sessions
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles
from ..permissions.get_permissions import get_permissions
from src import r
from src import db

def get_local_logo(school):
    if not school.Logo:
        return ""

    folder = os.path.join(
        current_app.static_folder,
        "school_logos"
    )

    os.makedirs(folder, exist_ok=True)

    filename = f"{school.id}.png"
    filepath = os.path.join(folder, filename)

    if not os.path.exists(filepath):
        try:
            response = requests.get(school.Logo, timeout=10)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(response.content)

        except Exception as e:
            print("Logo download error:", e)
            return school.Logo

    return url_for(
        "static",
        filename=f"school_logos/{filename}",
        _external=True
    )

def save_sessions(user=None, user_id=None):
    if not user and not user_id:
        return False, "User information is required."

    user_obj = None
    role = None

    if user:
        user_obj, role = user

    else:
        try:
            result = (
                db.session.query(TeachersLogin, Roles)
                .join(Roles, Roles.id == TeachersLogin.role_id)
                .filter(TeachersLogin.id == user_id)
                .first()
            )

            if result:
                user_obj, role = result
            else:
                return False, "Staff member does not exist."

        except SQLAlchemyError as e:
            db.session.rollback()
            print(e)
            return False, "Something went wrong. Server error!"

    if not user_obj:
        return False, "Staff member does not exist."

    if user_obj.status == "deleted" and role and role.is_deletable:
        return False, "You have been inactive from this school."

    school = Schools.query.filter_by(id=user_obj.school_id).first()

    if not school:
        return False, "School doesn't exist."

    sessions = (
        Sessions.query
        .with_entities(
            Sessions.id, Sessions.session, Sessions.current_session
        )
        .filter(Sessions.id >= school.school_legacy_id)
        .order_by(Sessions.session.desc())
        .all()
    )

    current_running_session = next(
        (s.id for s in sessions if s.current_session),
        None
    )

    session.permanent = True

    session["role"] = role.role_name
    session["all_sessions"] = [int(s.session) for s in sessions]
    session["school_name"] = school.School_Name
    session["user_id"] = user_obj.id
    session["logo"] = get_local_logo(school)
    session["email"] = user_obj.email
    session["school_id"] = user_obj.school_id
    session["permission_no"] = user_obj.permission_number
    session["user_name"] = user_obj.Name
    session["user_image"] = user_obj.image

    session["permissions"] = get_permissions(
        user_obj.id,
        user_obj.role_id
    )

    session["session_id"] = current_running_session
    session["current_running_session"] = current_running_session

    r.set(
        user_obj.id,
        user_obj.permission_number
    )

    return True, "Success"