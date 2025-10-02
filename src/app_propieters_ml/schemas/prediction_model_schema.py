from pydantic import BaseModel, Field
from typing import Optional
    

class PredictionPriceSchema(BaseModel):
    
    property_type: str
    area_m2: int = Field(..., gt=0)
    rooms: int = Field(..., ge=0)
    bathrooms: int = Field(..., ge=1)
    vacancies: Optional[int] = Field(0, ge=0)