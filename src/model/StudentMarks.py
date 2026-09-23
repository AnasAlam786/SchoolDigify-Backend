from datetime import datetime
from sqlalchemy import (
    Column, Text, ForeignKey,BigInteger, Date
)
from src import db

class StudentMarks(db.Model):
    __tablename__ = 'StudentMarks'

    id = db.Column(BigInteger, primary_key=True, autoincrement=True)

    student_session_id = Column(BigInteger, db.ForeignKey('StudentSessions.id', onupdate='CASCADE'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('ClassSubject.id', onupdate='CASCADE'), nullable=False)
    exm_id = Column(BigInteger, db.ForeignKey('ClassExams.id', onupdate='CASCADE'), nullable=True)
    score = Column(Text, nullable=True)
    created_at = Column(Date, default=datetime.utcnow)

    __table_args__ = (
    db.UniqueConstraint(
        'student_session_id', 'subject_id', 'exm_id',
        name='uq_student_marks_student_subject_exam'
    ),
)
    
    # Optional: relationships for easier access (recommended)
    student_sessions = db.relationship('StudentSessions', back_populates='marks')
    class_exams = db.relationship('ClassExams', back_populates='marks')
    class_subject = db.relationship("ClassSubject", back_populates="marks")
