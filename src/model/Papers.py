from src import db
from sqlalchemy import (
    Column, Text, ForeignKey, BigInteger, DateTime, String, Integer
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

class Papers(db.Model):
    __tablename__ = 'Papers'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('TeachersLogin.id', onupdate='CASCADE'), nullable=False)
    staff_data = db.relationship("TeachersLogin", back_populates="papers")

    session_id = Column(BigInteger, ForeignKey('Sessions.id', onupdate="CASCADE"), nullable=False)
    session = db.relationship("Sessions", back_populates="papers")

    school_id = Column(Text, ForeignKey('Schools.id', onupdate='CASCADE'), nullable=False)
    school = db.relationship("Schools", back_populates="papers")

    # self-reffering column
    cloned_from = Column( BigInteger, ForeignKey("Papers.id", ondelete="SET NULL"),nullable=True)

    # Metadata columns
    event = Column(String(255), nullable=False)  # e.g., "Formative Assessment - I"
    subject = Column(String(255), nullable=True)  # e.g., "Math"
    class_name = Column(String(50), nullable=True)  # e.g., "10A"
    marks = Column(Integer, nullable=True)  # Max marks
    duration = Column(String(50), nullable=True)  # e.g., "2 Hrs"
    
    # Question data
    paper_data = Column(JSONB, nullable=False)  # Structured questions JSON
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(Text, default="active", nullable=False)  # active/inactive for soft delete
    
    def __repr__(self):
        return f"<Papers {self.id}: {self.event} - {self.subject} ({self.class_name})>"
