from typing import List, Literal
from uuid import UUID
from math import radians, sin, cos, atan2, sqrt
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict

class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=2, max_length=80)
    zip: str = Field(pattern=r'^\d{5}$')
    address: str = Field(default='', max_length=240)
    occupation: str = Field(min_length=2, max_length=100)
    workplace: str = Field(default='', max_length=100)
    bio: str = Field(default='', max_length=800)
    languages: List[str] = Field(min_length=1, max_length=12)
    cultures: List[str] = Field(default_factory=list, max_length=12)
    countries: List[str] = Field(default_factory=list, max_length=12)
    expertise: List[str] = Field(min_length=1, max_length=12)
    interests: List[str] = Field(default_factory=list, max_length=12)
    needs: List[str] = Field(default_factory=list, max_length=12)

    @field_validator('languages','cultures','countries','expertise','interests','needs')
    @classmethod
    def normalize(cls, values):
        cleaned=[]
        for value in values:
            value=value.strip().lower()
            if not value or len(value)>60:
                raise ValueError('Each tag must contain 1–60 characters.')
            if value not in cleaned:
                cleaned.append(value)
        return cleaned

class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1]
    formId: str = Field(min_length=1,max_length=200)
    responseId: str = Field(min_length=1,max_length=200)
    email: EmailStr
    consent: Literal[True]
    adult: Literal[True]
    profile: ProfileInput

    @field_validator('consent','adult',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True:
            raise ValueError('An explicit confirmation is required.')
        return value

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        if len(value)>254:
            raise ValueError('Email is too long.')
        return value.lower()

class MessageInput(BaseModel):
    clientMessageId: UUID | None = None
    body: str = Field(min_length=1,max_length=2000)
    @field_validator('body')
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError('Message cannot be empty.')
        return value.strip()

def distance_miles(lat1, lon1, lat2, lon2):
    a=sin(radians(lat2-lat1)/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(radians(lon2-lon1)/2)**2
    return 3958.8*2*atan2(sqrt(a),sqrt(max(0,1-a)))
