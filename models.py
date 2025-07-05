# models.py
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class EmployeeData(Base):
    __tablename__ = 'employee_data'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    salary = Column(String)  # Encrypted string
    position = Column(String)
    email = Column(String)

# Create the SQLite database
engine = create_engine('sqlite:///employees.db')
Base.metadata.create_all(engine)
