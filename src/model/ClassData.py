from sqlalchemy import (
    Column, BigInteger, SmallInteger, Text, JSON, ForeignKey, Boolean
)
from src import db

class ClassData(db.Model):
    __tablename__ = 'ClassData'
    
    id = Column(BigInteger, primary_key=True)
    CLASS = Column(Text, nullable=False)
    Section = Column(Text, nullable=True)   # Added Section column as per DB
    display_order = Column(SmallInteger, nullable=True)
    grade_level = Column(SmallInteger, nullable=False)
    is_terminal = Column(Boolean, nullable=False, default=False)  # Indicates if this is a terminal class (e.g., 10th, 12th)

    school_id = Column(Text, ForeignKey('Schools.id', onupdate="CASCADE"), nullable=False)
    school = db.relationship("Schools", back_populates="class_data")

    class_teacher_id = Column(BigInteger, ForeignKey('TeachersLogin.id', onupdate="CASCADE"), nullable=False)
    class_teacher_data = db.relationship("TeachersLogin", back_populates="class_data")
    
    
    # Relationships
    class_subjects = db.relationship("ClassSubject", back_populates="class_data")
    student_sessions =  db.relationship("StudentSessions", back_populates="class_data")
    class_access = db.relationship("ClassAccess", back_populates="class_data")
    class_exams = db.relationship("ClassExams", back_populates="class_data")
    fee_sessions = db.relationship("FeeSessionData", back_populates="class_data")
    holidays = db.relationship("AttendanceHolidays", back_populates="class_data")
