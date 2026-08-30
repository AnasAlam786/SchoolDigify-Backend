from sqlalchemy import Column, BigInteger, Numeric, Date, ForeignKey, UniqueConstraint
from src import db

class FeeSessionData(db.Model):
    __tablename__ = "FeeSessionData"

    __table_args__ = (
        UniqueConstraint(
            "session_id", "class_id", "structure_id",
            name="fee_session_data_unique"
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    amount = Column(Numeric, nullable=False)
    custom_due_date = Column(Date, nullable=True)
    custom_start_date = Column(Date, nullable=True)
    
    # Optional relationships
    structure_id = Column(BigInteger, ForeignKey("FeeStructure.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    fee_structure = db.relationship("FeeStructure", back_populates="fee_sessions")

    class_id = Column(BigInteger, ForeignKey("ClassData.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    class_data = db.relationship("ClassData", back_populates="fee_sessions")

    session_id = Column(BigInteger, ForeignKey("Sessions.id"), nullable=False)
    session = db.relationship("Sessions", back_populates="fee_sessions")

    fee_data = db.relationship("FeeData", back_populates="fee_sessions", uselist=True)