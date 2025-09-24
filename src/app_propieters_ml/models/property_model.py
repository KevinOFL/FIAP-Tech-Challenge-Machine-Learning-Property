from sqlalchemy import Column, Integer, String, Date, Time, Numeric, DateTime
from sqlalchemy.sql import func
from src.app_propieters_ml.core.database import Base

class Property(Base):
    __tablename__ = "properties"
    
    id = Column(String, primary_key=True, index=True, autoincrement=False)
    property_type = Column(String, nullable=False)
    price = Column(Numeric(11, 2), nullable=False)
    price_condominium = Column(Numeric(10, 2), nullable=True)
    iptu = Column(Numeric(10, 2), nullable=True)
    area_m2 = Column(Integer, nullable=False)
    rooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer, nullable=False)
    vacancies = Column(Integer, nullable=False)
    city = Column(String, nullable=False)
    neighborhood = Column(String, nullable=False)
    
    collection_date = Column(Date, server_default=func.current_date())
    collection_time = Column(Time, server_default=func.current_time())
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())