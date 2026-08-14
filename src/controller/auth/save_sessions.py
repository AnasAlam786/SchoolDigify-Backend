import os
import requests

from flask import session, current_app, url_for
from sqlalchemy.exc import ProgrammingError

from src.model.Schools import Schools
from src.model.Sessions import Sessions
from src.model.TeachersLogin import TeachersLogin
from src.model.Roles import Roles
from ..permissions.get_permissions import get_permissions
from src import r

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
        return False

    if not user:
        try:
            user = (
                TeachersLogin.query
                .join(Roles, Roles.id == TeachersLogin.role_id)
                .filter(TeachersLogin.id == user_id)
                .first()
            )
        except ProgrammingError:
            return False

    if not user:
        return False

    school = Schools.query.filter_by(id=user.school_id).first()

    if not school:
        return False

    sessions = (
        Sessions.query
        .with_entities(
            Sessions.id,
            Sessions.session,
            Sessions.current_session
        )
        .filter(Sessions.id >= school.school_legacy_id)
        .order_by(Sessions.session.desc())
        .all()
    )

    session.permanent = True

    session["role"] = user.role_data.role_name
    session["all_sessions"] = [int(s.session) for s in sessions]
    session["school_name"] = school.School_Name
    session["user_id"] = user.id

    # Only change here
    session["logo"] = get_local_logo(school)

    session["email"] = user.email
    session["school_id"] = user.school_id
    session["permission_no"] = user.permission_number
    session["user_name"] = user.Name
    session["user_image"] = user.image

    session["permissions"] = get_permissions(
        user.id,
        user.role_id
    )

    current_running_session = None

    for s in sessions:
        if s.current_session:
            current_running_session = s.id
            break

    session["session_id"] = current_running_session
    session["current_running_session"] = current_running_session

    r.set(
        session["user_id"],
        user.permission_number
    )

    return True