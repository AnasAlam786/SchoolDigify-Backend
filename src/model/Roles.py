from sqlalchemy import (
    Boolean, Column, BigInteger, Text
)
from src import db

class Roles(db.Model):
    __tablename__ = 'Roles'
    id = Column(BigInteger, primary_key=True)
    role_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    assignable = Column(Boolean, nullable=True)
    display_order = Column(BigInteger, nullable=True)
    is_deletable = Column(Boolean, nullable=False, default=True)

    role_permissions = db.relationship("RolePermissions", back_populates="role_data")
    staff_data = db.relationship("TeachersLogin", back_populates="role_data")