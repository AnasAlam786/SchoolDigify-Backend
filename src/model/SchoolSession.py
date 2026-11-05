from src import db
from sqlalchemy import (
    Column, Date, Text, ForeignKey, BigInteger, Numeric
)

class SchoolSession(db.Model):
    __tablename__ = 'SchoolSession'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    school_id = Column(Text, ForeignKey('Schools.id', onupdate='CASCADE'), nullable=False)
    session_id = Column(BigInteger, ForeignKey('Sessions.id', onupdate='CASCADE'), nullable=False)
    working_days = Column(Numeric, nullable=True)
    session_start_date = Column(Date)
    session_end_date = Column(Date)

    school = db.relationship("Schools", back_populates="school_sessions")
    session = db.relationship("Sessions", back_populates="school_sessions")