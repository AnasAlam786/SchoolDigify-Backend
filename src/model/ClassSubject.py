from sqlalchemy import (
    Column, BigInteger, ForeignKey
)
from src import db


class ClassSubject(db.Model):
    __tablename__ = 'ClassSubject'

    id = Column(BigInteger, primary_key=True)

    created_at = Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    class_id = Column(
        BigInteger, ForeignKey(
            'ClassData.id', onupdate="CASCADE", ondelete="RESTRICT"
        ), nullable=True
    )

    subject_id = Column(
        BigInteger, ForeignKey(
            'Subjects.id', onupdate="CASCADE", ondelete="RESTRICT"
        ), nullable=True
    )

    is_optional = Column(db.Boolean, nullable=False, default=False)

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

    # ================================================================
    # Relationships
    # ================================================================

    class_data = db.relationship("ClassData",back_populates="class_subjects")
    subject = db.relationship("Subjects",back_populates="class_subjects")
    student_subjects = db.relationship("StudentSubjects",back_populates="class_subject")
    start_session_data = db.relationship("Sessions",foreign_keys=[start_session])
    end_session_data = db.relationship("Sessions",foreign_keys=[end_session])

    marks = db.relationship("StudentMarks", back_populates="class_subject")