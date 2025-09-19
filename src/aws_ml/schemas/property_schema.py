from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
import re

class PropertySchema(BaseModel):
    id: str
    property_type: str
    price: Optional[float] = None
    price_condominium: Optional[float] = None
    iptu: Optional[float] = None
    area_m2: int
    rooms: int
    bathrooms: int
    vacancies: int
    state: Optional[str] = None
    neighborhood: Optional[str] = None
    collection_date: date = Field(default_factory=date.today)

    # Este validador será aplicado aos campos listados ANTES de qualquer outra validação
    @field_validator('price', 'price_condominium', 'iptu', 'area_m2', 'rooms', 'bathrooms', 'vacancies', mode='before')
    @classmethod
    def clean_and_extract_numbers(cls, v):
        # Se o valor for nulo ou não for uma string, retorna como está
        if v is None or not isinstance(v, str):
            return v
        
        # Usa regex para encontrar todos os dígitos na string
        # Ex: "R$ 1.500.000,00" -> ["1", "5", "0", "0", "0", "0", "0", "0", "0"]
        # Ex: "120 m²" -> ["1", "2", "0"]
        numeros = re.findall(r'\d+', v)
        
        if numeros:
            # Junta os números encontrados e converte
            # Nota: Para preços com centavos, pode ser necessário um tratamento adicional
            return "".join(numeros)
        
        # Se não encontrar números (ex: "Sob consulta"), retorna None
        return None
    