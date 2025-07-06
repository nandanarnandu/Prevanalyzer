# models.py

# Import SQLAlchemy tools for creating and managing databases
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

# Create a base class that all our database tables will inherit from
# Think of this as a template for creating database tables
Base = declarative_base()

# Define the structure of our employee data table
class EmployeeData(Base):
    # Set the actual table name in the database
    __tablename__ = 'employee_data'
    
    # Define each column (field) in the table with its data type
    id = Column(Integer, primary_key=True)  # Unique ID number for each employee (auto-generated)
    name = Column(String)                   # Employee's name (text)
    salary = Column(String)                 # Employee's salary stored as encrypted text
    position = Column(String)               # Employee's job title (text)
    email = Column(String)                  # Employee's email address (text)

# Create the SQLite database file and connection
# SQLite is a simple database that stores data in a single file
engine = create_engine('sqlite:///employees.db')

# Create all the tables we defined (in this case, just the employee_data table)
# This actually creates the database file and table structure
Base.metadata.create_all(engine)