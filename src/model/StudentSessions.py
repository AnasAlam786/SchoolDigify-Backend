from sqlalchemy import (
    Column, Date, Integer, BigInteger, Text, DateTime, Numeric, Enum,
    ForeignKey, UniqueConstraint
)
from src import db

PromotionStatusEnum = Enum(
    "promoted",
    "active",
    "passed_out",
    "tc",
    name="Promotion_Status",
    create_type=False,          # Important: reuse existing type in DB
    inherit_schema=True,
)
class StudentSessions(db.Model):
    __tablename__ = 'StudentSessions'
    
    id = Column(BigInteger, primary_key=True)
    student_id = Column(BigInteger, ForeignKey('StudentsDB.id', onupdate="CASCADE"), nullable=False)
    class_id = Column(BigInteger, ForeignKey('ClassData.id', onupdate="CASCADE"), nullable=False)
    ROLL = Column(Integer, nullable=True)
    Height = Column(Integer, nullable=True)
    Weight = Column(Integer, nullable=True)
    session_id = Column(BigInteger, ForeignKey('Sessions.id', onupdate="CASCADE"), nullable=False)
    Attendance = Column(Text, nullable=True)  # JSON format for bulk attendance or integer for daily count
    created_at = Column(DateTime)
    Section = Column(Text, nullable=True)

    tc_number = Column(Numeric, nullable=True)
    tc_date = Column(Date, nullable=True)
    left_reason = Column(Text, nullable=True)
    status = Column(PromotionStatusEnum, nullable=False)

    class_data = db.relationship("ClassData", back_populates="student_sessions")
    students = db.relationship("StudentsDB", back_populates="student_sessions")
    session = db.relationship("Sessions", back_populates="student_sessions")
    fee_data = db.relationship("FeeData", back_populates="student_sessions")
    attendance = db.relationship("Attendance", back_populates="student_sessions")
    tc_records = db.relationship("TCRecords", back_populates="student_sessions")

    __table_args__ = (
        UniqueConstraint('session_id', 'tc_number', name='uix_tc_session'),
        UniqueConstraint('class_id', 'ROLL', 'session_id' , name='uix_school_SR'),
    )
