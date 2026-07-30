from sqlalchemy import (
    Column, Date, BigInteger, Text, DateTime, Numeric, Enum,
    ForeignKey, func
)
from src import db

TCStatusEnum = Enum(
    "issued",
    "cancelled",
    name="TCStatus",
    create_type=False,
    inherit_schema=True
)

class TCRecords(db.Model):
    __tablename__ = 'TCRecords'
    
    id = Column(BigInteger, primary_key=True)
    student_session_id = Column(BigInteger, ForeignKey('StudentSessions.id', onupdate="CASCADE"), nullable=False, unique=True)

    tc_no = Column(Numeric, nullable=True)
    tc_date = Column(Date, nullable=True)
    tc_reason = Column(Text, nullable=True)
    general_conduct = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(TCStatusEnum, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    student_sessions = db.relationship("StudentSessions", back_populates="tc_records")