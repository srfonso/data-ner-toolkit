from settings import ALLOWED_LANG_MODELS, MAX_DATA_BY_REQUEST
from pydantic import BaseModel, Field, field_validator


# ======================================================
# =====            REQUEST SERIALIZER              =====
# ======================================================

# /ner and /annotate enpoint serializer request. 
class RequestNER(BaseModel):
    data: list[str] = Field(
        ..., 
        max_items=MAX_DATA_BY_REQUEST, 
        description=f"list of text items (text + id), max {MAX_DATA_BY_REQUEST}"
    )
    allowed_types: list[str] = Field(
        default=[],
        alias="types",
        description="Allowed types (from spacy). Default = [] (all)"
    )
    lang: str = Field(
        ...,
        description="Language code of the texts, ISO-639-1",
        enum=list(ALLOWED_LANG_MODELS.keys())
    )

    @field_validator("allowed_types", mode='before')
    def check_empty_strings(cls, allowed_types):
        if "" in allowed_types:
            raise ValueError("Empty strings `""` are not allowed in 'allowed_types'")
        return allowed_types


# ======================================================
# =====             MODEL SERIALIZERS              =====
# ======================================================

# Entity model structure
class Entity(BaseModel):
    name: str
    type: str
    start_offset: int
    end_offset: int

# Text result model without annotations
class TextEntities(BaseModel):
    entities: list[Entity]

# Text result model with annotations
class AnnotateTextEntities(BaseModel):
    entities: list[Entity]
    annotated_text: str



# ======================================================
# =====           RESPONSE SERIALIZER              =====
# ======================================================

# /ner enpoint response serializer. 
class ResponseNER(BaseModel):
    model: str
    version: str
    results: list[TextEntities]

# /annotate endpoint response serializer.
class ResponseAnnotate(BaseModel):
    model: str
    version: str
    results: list[AnnotateTextEntities]