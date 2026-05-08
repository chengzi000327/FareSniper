from pydantic import BaseModel


class OtpRequestDto(BaseModel):
    phone: str


class OtpVerifyDto(BaseModel):
    phone: str
    code: str
