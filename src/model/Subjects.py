from src import db
from sqlalchemy import (
    Column, Text, ForeignKey, BigInteger, Numeric,
    Integer, Boolean, TIMESTAMP, func
)

class Subjects(db.Model):
    __tablename__ = "Subjects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, server_default=func.now())
    school_id = Column(Text, ForeignKey("Schools.id", onupdate="CASCADE"), nullable=False)
    class_id = Column(BigInteger, ForeignKey("ClassData.id", onupdate="CASCADE"), nullable=False)
    subject = Column(Text, nullable=False)
    max_marks = Column(Numeric, nullable=True)
    pass_marks = Column(Numeric, nullable=True)
    display_order = Column(Numeric, nullable=True)
    evaluation_type = Column(Text, nullable=False, server_default="")
    abbreviation = Column(Text, nullable=False)
    staff_id = Column(Integer, ForeignKey("TeachersLogin.id", onupdate="CASCADE"), nullable=True)
    subject_type = Column(Text, nullable=False, server_default="core")
    is_active = Column(Boolean, nullable=False, server_default="true")

    school = db.relationship("Schools", back_populates="subjects")
    staff_data = db.relationship("TeachersLogin", back_populates="subjects")
    class_subjects = db.relationship("ClassSubject", back_populates="subject")
