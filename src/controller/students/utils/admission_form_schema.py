from pydantic import BaseModel, Field, EmailStr, constr, conint, field_validator
from typing import Optional, Literal
from enum import Enum as PyEnum
from .validate_aadhaar import verify_aadhaar
from .str_to_date import str_to_date
from src.model.enums import StudentsDBEnums


# Build Python Enums from SQLAlchemy Enum values
def _sanitize_enum_member_name(raw: str) -> str:
    name = ''.join(ch if ch.isalnum() else '_' for ch in str(raw)).upper()
    if name and name[0].isdigit():
        name = f'N_{name}'
    return name or 'EMPTY'

def _build_python_enum(enum_name: str, sa_enum) -> type[PyEnum]:
    members = {}
    seen = set()
    for value in sa_enum.enums:
        base_name = _sanitize_enum_member_name(value)
        name = base_name
        counter = 1
        while name in seen:
            counter += 1
            name = f"{base_name}_{counter}"
        seen.add(name)
        members[name] = value
    return PyEnum(enum_name, members)

GenderEnum = _build_python_enum("GENDER", StudentsDBEnums.GENDER)
CasteTypeEnum = _build_python_enum("Caste_Type", StudentsDBEnums.CASTE_TYPE)
ReligionEnum = _build_python_enum("RELIGION", StudentsDBEnums.RELIGION)
BloodGroupEnum = _build_python_enum("BLOOD_GROUP", StudentsDBEnums.BLOOD_GROUP)
EducationTypeEnum = _build_python_enum("EDUCATION_TYPE", StudentsDBEnums.EDUCATION_TYPE)
FatherOccupationEnum = _build_python_enum("FATHERS_OCCUPATION", StudentsDBEnums.FATHERS_OCCUPATION)
MotherOccupationEnum = _build_python_enum("MOTHERS_OCCUPATION", StudentsDBEnums.MOTHERS_OCCUPATION)
HomeDistanceEnum = _build_python_enum("Home_Distance", StudentsDBEnums.HOME_DISTANCE)

# ------------------------- Personal Info -------------------------
class AdmissionFormModel(BaseModel):
    
    STUDENTS_NAME: constr(pattern=r'^[^\W\d_]+(?: [^\W\d_]+)*$') = Field(...) # type: ignore
    DOB: str = Field(...)
    GENDER: GenderEnum = Field(...)
    AADHAAR: Optional[constr(min_length=12, max_length=12)] = Field(default=None) # type: ignore
    Caste: Optional[str] = Field(None)
    Caste_Type: CasteTypeEnum = Field(...)

    RELIGION: ReligionEnum = Field(...)

    Height: Optional[conint(gt=0, lt=300)] = Field(None) # type: ignore
    Weight: Optional[conint(gt=0, lt=300)] = Field(None) # type: ignore

    BLOOD_GROUP: Optional[BloodGroupEnum] = Field(None)
        
    # ------------------------- Academic Info -------------------------
    admitted_as_new: bool = Field(..., description="Indicates if admitted as new")
    admission_session_id: int = Field(ge=2000, le=2100)
    admission_class_id: Optional[int] = Field(None, gt=0)
    class_id: int = Field(gt=0)
    ROLL: conint(gt=0) = Field(...) # type: ignore
    SR: conint(gt=0) = Field(...) # type: ignore
    ADMISSION_NO: conint(gt=0) = Field(...) # type: ignore
    ADMISSION_DATE: str = Field(...)
    PEN: Optional[constr(max_length=11, min_length=11)] = Field(None) # type: ignore
    APAAR: Optional[constr(max_length=12, min_length=12)] = Field(None) # type: ignore


    
    # ------------------------- Guardian Info -------------------------
    FATHERS_NAME: constr(pattern=r'^[^\W\d_]+(?: [^\W\d_]+)*$') = Field(...) # type: ignore
    FATHERS_AADHAR: Optional[constr(max_length=12, min_length=12)] = Field(None) # type: ignore
    MOTHERS_NAME: constr(pattern=r'^[^\W\d_]+(?: [^\W\d_]+)*$') = Field(...) # type: ignore
    MOTHERS_AADHAR: Optional[constr(max_length=12, min_length=12)] = Field(None) # type: ignore
    
    FATHERS_EDUCATION: Optional[EducationTypeEnum] = Field(None)
    FATHERS_OCCUPATION: Optional[FatherOccupationEnum] = Field(None)
    MOTHERS_EDUCATION: Optional[EducationTypeEnum] = Field(None)
    MOTHERS_OCCUPATION: Optional[MotherOccupationEnum] = Field(None)


    ADDRESS: str = Field(...) # type: ignore
    PHONE: constr(pattern=r"^\d{10}$") # type: ignore
    ALT_MOBILE: Optional[constr(pattern=r"^\d{10}$")] = Field(None)# type: ignore
    PIN: constr(pattern=r"^\d{6}$") = Field(...) # type: ignore
    Home_Distance: Optional[HomeDistanceEnum] = Field(default=None)
    EMAIL: Optional[EmailStr] = Field(None)


    Previous_School_Marks: Optional[constr(max_length=3)] = Field(None) # type: ignore
    Previous_School_Attendance: Optional[constr(max_length=3)] = Field(None) # type: ignore
    Previous_School_Name: Optional[constr(min_length=2)] = Field(None) # type: ignore

    # --- RTE fields ---
    is_RTE: bool = Field(default=False)
    account_number: Optional[constr(min_length=9, max_length=18)] = Field(None)
    RTE_registered_year: Optional[conint(gt=2000, lt=2100)] = Field(None)
    ifsc: Optional[constr(min_length=11, max_length=11)] = Field(None)
    bank_name: Optional[str] = Field(None)
    bank_branch: Optional[str] = Field(None)
    account_holder: Optional[str] = Field(None)
    registration_no: Optional[constr(min_length=3, max_length=8)] = Field(None) #exact 6 characters

    @field_validator("ifsc", mode="after")
    def normalize_ifsc(cls, v):
        if v:
            return v.upper()
        return v

    
    
    @field_validator("*", mode="before")
    @classmethod
    def empty_string_to_none(cls, v, info):
        if not isinstance(v, str):
            return v
        
        v = v.strip()
    
        if v == "":
            if not cls.model_fields[info.field_name].is_required():
                return None
        return v

    @field_validator('DOB', 'ADMISSION_DATE', mode='before')
    @classmethod
    def date_normalization(cls, v):
        if not v:
            return None
        
        parsed_date = str_to_date(v)
        return parsed_date
    
    @field_validator('AADHAAR', 'FATHERS_AADHAR', 'MOTHERS_AADHAR', mode='before')
    @classmethod
    def clean_aadhaar(cls, v):
        if not v:
            return None
        
        validated_clean_aaadhar = verify_aadhaar(v)
        return validated_clean_aaadhar
