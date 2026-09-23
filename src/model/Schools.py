from sqlalchemy import (
    BigInteger, Column, Text, Date, JSON, Numeric
)
from src import db

class Schools(db.Model):
    __tablename__ = 'Schools'
    
    id = Column(Text, primary_key=True)  # Primary key, text type
    created_at = Column(Date, nullable=False)
    School_Name = Column(Text, nullable=True)         # In DB, School_Name is nullable
    Address = Column(Text, nullable=True)               # In DB, Address is nullable
    Logo = Column(Text, nullable=True)
    UDISE = Column(Text, unique=True, nullable=True)    # In DB, UDISE is nullable but unique
    Phone = Column(Text, nullable=True)
    WhatsApp = Column(Text, nullable=True, server_default='')  # Default empty string
    Email = Column(Text, unique=True, nullable=True)
    Password = Column(Text, nullable=True)
    Manager = Column(Text, nullable=False)
    IP = Column(JSON, nullable=True)
    students_image_folder_id = Column(Text, nullable=True)  # Added students_image_folder_id as per DB
    school_heading_image = Column(Text, nullable=True)  # Added school_heading_image as per DB
    session_id = Column(Text, nullable=False)
    login_no = Column(Numeric, nullable=False)

    school_legacy_id = Column(BigInteger, db.ForeignKey('Sessions.id', onupdate='CASCADE'), nullable=False)
    session = db.relationship('Sessions', back_populates='school_legacy')
    
    # Relationships
    students = db.relationship("StudentsDB", back_populates="school")
    class_data = db.relationship("ClassData", back_populates="school")

    exams = db.relationship("Exams", back_populates="school")
    subjects = db.relationship("Subjects", back_populates="school")

    staff_data = db.relationship("TeachersLogin", back_populates="school")
    fee_structure = db.relationship("FeeStructure", back_populates="school")
    fee_transactions = db.relationship("FeeTransaction", back_populates="school")
    holidays = db.relationship("AttendanceHolidays", back_populates="school")
    papers = db.relationship("Papers", back_populates="school")
    school_sessions = db.relationship("SchoolSession", back_populates="school")

