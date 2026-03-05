from sqlalchemy import (
    Boolean, TIMESTAMP, Column, BigInteger, ForeignKey, Text, func, Numeric
)
from src import db

class RTEInfo(db.Model):
    __tablename__ = "RTEInfo"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    account_number = Column(Text, nullable=True)
    ifsc = Column(Text, nullable=True)
    bank_name = Column(Text, nullable=True)
    account_holder = Column(Text, nullable=True)  # keep the same spelling if intentional
    RTE_registered_year = Column(Text, nullable=True)
    bank_branch = Column(Text, nullable=True)
    is_RTE = Column(Boolean, nullable=False)
    registration_no = Column(Numeric, nullable=True)
    

    student_id = Column(BigInteger, ForeignKey("StudentsDB.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    students = db.relationship("StudentsDB", back_populates="RTE_info")