from sqlalchemy import (
    Column, Date, Numeric, Text, JSON, ForeignKey, BigInteger
)
from src import db

class TeachersLogin(db.Model):
    __tablename__ = 'TeachersLogin'
    
    id = Column(BigInteger, primary_key=True)  # 'serial' is represented as Integer with auto-increment
    Name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    Password = Column(Text, nullable=False)
    IP = Column(JSON, nullable=True)
    
    Sign = Column(Text, nullable=True)
    User = Column(Text, nullable=False)
    status = Column(db.Enum('active', 'deleted', name='Status',), nullable=False, default='active')
    status = Column(Text, nullable=False)
    image = Column(Text, nullable=True)
    qualification = Column(Text, nullable=True)
    dob = Column(Date, nullable=True)
    phone = Column(BigInteger, nullable=True)
    date_of_joining = Column(Date, nullable=True)
    address = Column(Text, nullable=True)
    permission_number = Column(Numeric, nullable=False, default=1)
    national_id = Column(Text, nullable=True)
    salary = Column(Numeric, nullable=True)
    gender = Column(db.Enum('Male', 'Female', name='GENDER'), nullable=True)

    school_id = Column(Text, ForeignKey('Schools.id', onupdate="CASCADE"), nullable=False)
    school = db.relationship("Schools", back_populates="staff_data")

    role_id = Column(BigInteger, ForeignKey('Roles.id', onupdate="CASCADE"), nullable=False)
    role_data = db.relationship("Roles", back_populates="staff_data")

    class_data = db.relationship("ClassData", back_populates="class_teacher_data")
    class_access = db.relationship("ClassAccess", back_populates="staff_data")
    subjects = db.relationship("Subjects", back_populates="staff_data")
    attendance = db.relationship("Attendance", back_populates="staff_data")
    papers = db.relationship("Papers", back_populates="staff_data")