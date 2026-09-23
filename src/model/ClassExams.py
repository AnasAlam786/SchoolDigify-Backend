from sqlalchemy import (
    TIMESTAMP, Column, BigInteger, ForeignKey, func
)
from src import db

class ClassExams(db.Model):
    __tablename__ = "ClassExams"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    exam_id = Column(BigInteger, ForeignKey('Exams.id', onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    class_id = Column(BigInteger, ForeignKey('ClassData.id', onupdate="CASCADE", ondelete="CASCADE"), nullable=True)

    start_session = Column(
        BigInteger,ForeignKey(
            'Sessions.id',onupdate="CASCADE",ondelete="RESTRICT"
        ), nullable=True
    )

    end_session = Column(
        BigInteger, ForeignKey(
            'Sessions.id',onupdate="CASCADE",ondelete="RESTRICT"
        ),nullable=True
    )


    start_session_data = db.relationship("Sessions",foreign_keys=[start_session])
    end_session_data = db.relationship("Sessions",foreign_keys=[end_session])
    # Optional: define relationships if you want ORM-style access
    exams = db.relationship("Exams", back_populates="class_exams")
    class_data = db.relationship("ClassData", back_populates="class_exams")
    marks = db.relationship(
        "StudentMarks",
        back_populates="class_exams",
        foreign_keys='[StudentMarks.exm_id]'
    )