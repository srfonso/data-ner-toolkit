import uuid
import json
import datetime
from typing import Optional
from pydantic import BaseModel, Field


class GeneralEncoder(json.JSONEncoder):
    """ An optional json.JSONEncoder subclass to serialize data types not supported 
    by the standard JSON serializer (e.g. datetime.datetime or UUID). 

    It will encode datetimes in ISO Format and UUIDs in hexadecimal string.
    """

    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return obj.hex 
        elif isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return (datetime.datetime.min + obj).time().isoformat()
        return super().default(obj)


# ======================================================
# =====            INPUT DATA MODELS               =====
# ======================================================

class TextItem(BaseModel):
    ID: uuid.UUID
    sub_ID: Optional[int] = None  # Ahora es opcional
    text: str

class InputData(BaseModel):
    data: list[TextItem] = Field(default_factory=list)

    class Config:
        validate_assignment = True


# ======================================================
# =====            RESULT DATA MODELS              =====
# ======================================================

class Entity(BaseModel):
    name: str
    type: str
    start_offset: int
    end_offset: int
    
    
class TextEntities(BaseModel):
    ID: uuid.UUID
    subID: int
    entities: list[Entity] = Field(default_factory=list)

    class Config:
        validate_assignment = True

class ResultData(BaseModel):
    data: list[TextEntities] = Field(default_factory=list)

    class Config:
        validate_assignment = True


