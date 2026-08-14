import re
from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator, ValidationError



class StaffVerification(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the staff member")
    email: Optional[EmailStr] = Field(None, description="Official email ID (optional)")
    phone: Optional[str] = Field(None, description="10-digit Indian phone number")
    
    dob: Optional[date] = Field(None, description="Date of birth in YYYY-MM-DD format")
    gender: Literal["Male", "Female", "Other"] = Field(..., description="Gender of the staff member")
    address: Optional[str] = Field(None, min_length=5, description="Residential address (optional)")
    
    # status: Literal["Active", "Inactive", "On Leave"] = Field("Active", description="Current employment status")
    
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for login")
    password: str = Field(..., min_length=6, description="Password for login (hashed in DB)")
    
    date_of_joining: Optional[date] = Field(None, description="Joining date in YYYY-MM-DD format")
    qualification: Optional[str] = Field(None, description="Educational qualification")
    salary: Optional[int] = Field(None, gt=0, description="Salary in INR (must be positive)")

    role_id: int = Field(..., description="Foreign key ID of role in roles table")
    image: Optional[str] = Field(None, description="Profile image URL or base64")
    sign: Optional[str] = Field(None, description="Digital signature URL or base64")
    national_id: Optional[str] = Field(None, description="National ID (e.g., UDISE Teacher ID)")



    # Custom validators for error messages
    @field_validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Name must have at least 2 characters")
        return v

    @field_validator('phone')
    def validate_phone(cls, v):
        if v is None:  # allow optional
            return v
        if not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Phone number must be a valid 10-digit Indian number starting with 6-9")
        return v

    @field_validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return v

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

    @field_validator('address')
    def validate_address(cls, v):
        if v is not None and len(v.strip()) < 5:
            raise ValueError("Address must have at least 5 characters")
        return v
    
    @field_validator("national_id")
    def validate_udise_id(cls, v):
        if v and not re.match(r"^[A-Z]{2}\d{12,13}$", v):
            raise ValueError("Invalid UDISE Staff ID format")
        return v
