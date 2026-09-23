from src import db
from sqlalchemy import (
    Boolean, Column, Date, Text, ForeignKey,BigInteger, Numeric
)
class Exams(db.Model):
    __tablename__ = 'Exams'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    school_id = Column(Text, ForeignKey('Schools.id', onupdate='CASCADE'), nullable=False)
    exam_name = Column(Text, nullable=False)
    exam_code = Column(Text, nullable=False)
    weightage = Column(Numeric, nullable=False)
    term = Column(Numeric, nullable=False)
    display_order = Column(Numeric, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    permission_updated_at = Column(Date, nullable=False)

    # Optional relationship
    school = db.relationship('Schools', back_populates='exams')
    class_exams = db.relationship("ClassExams", back_populates="exams")
