from src import db
from sqlalchemy import Column, BigInteger, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func


class StudentSubjects(db.Model):
    __tablename__ = 'StudentSubjects'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    student_session_id = Column(
        BigInteger, ForeignKey(
            'StudentSessions.id', onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=False
    )

    class_subject_id = Column(
        BigInteger, ForeignKey(
            'ClassSubject.id', onupdate='CASCADE', ondelete='RESTRICT'
        ),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            'student_session_id', 'class_subject_id',
            name='uq_student_subject_session_class_subject'
        ),
    )

    # Relationships
    student_session = db.relationship(
        'StudentSessions', back_populates='student_subjects'
    )

    class_subject = db.relationship(
        'ClassSubject', back_populates='student_subjects'
    )