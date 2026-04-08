# src/model/__init__.py

# Import all model classes
from .Schools import Schools
from .Sessions import  Sessions
from .SchoolSession import SchoolSession
from .ClassData import ClassData
from .ClassAccess import ClassAccess

from .StudentsDB import StudentsDB
from .StudentSessions import StudentSessions
from .RTEInfo import RTEInfo
from .TeachersLogin import TeachersLogin

from .Attendance import Attendance
from .AttendanceHolidays import AttendanceHolidays

from .StudentMarks import StudentMarks
from .Subjects import Subjects
from .Exams import Exams
from .ClassExams import ClassExams

from .Roles import Roles
from .Permissions import Permissions
from .RolePermissions import RolePermissions
from .StaffPermissions import StaffPermissions

from .FeeData import  FeeData
from .FeeStructure import FeeStructure
from .FeeHeads import FeeHeads
from .FeeSessionData import FeeSessionData
from .FeeTransaction import FeeTransaction

# Optional: control what `from src.model import *` brings in
__all__ = [
    "Schools",
    "Sessions",
    "SchoolSession",
    "ClassData",
    "ClassAccess",
    
    "StudentsDB",
    "StudentSessions",
    "RTEInfo",
    "TeachersLogin",

    "Attendance",
    "AttendanceHolidays",

    "StudentMarks",
    "Exams",
    "ClassExams",
    "Subjects",

    
    "Roles",
    "Permissions",
    "RolePermissions",
    "StaffPermissions",

    "FeeData",
    "FeeStructure",
    "FeeHeads",
    "FeeSessionData",
    "FeeTransaction",
]
