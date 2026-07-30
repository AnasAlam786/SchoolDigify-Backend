from sqlalchemy import TIMESTAMP, Column, BigInteger, ForeignKey, text
from src import db
from enum import Enum as PyEnum
from sqlalchemy import Enum as SQLEnum


class FeePaymentStatus(PyEnum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"


class FeeData(db.Model):
    __tablename__ = "FeeData"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    
    fee_payment_status = Column(
        SQLEnum(FeePaymentStatus, name="fee_payment_status"),
        nullable=False
    )

    transaction_id = Column(BigInteger, ForeignKey("FeeTransaction.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True)
    fee_transactions = db.relationship("FeeTransaction", back_populates="fee_data")

    student_session_id = Column(BigInteger, ForeignKey("StudentSessions.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True)
    student_sessions = db.relationship("StudentSessions", back_populates="fee_data")

    fee_session_id = Column(BigInteger, ForeignKey("FeeSessionData.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True)
    fee_sessions = db.relationship("FeeSessionData", back_populates="fee_data")
    
