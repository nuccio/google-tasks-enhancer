from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from .database import Base

# Allowed values of Task.priority. A task without a priority stores NULL.
PRIORITY_VALUES = ("low", "medium", "high")
DEFAULT_PRIORITY = "medium"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Do NOT store the tokens in clear text in production! Use encryption.
    google_tokens = Column(JSON) 
    
    tasks = relationship("Task", back_populates="owner")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True) # Google Tasks ID
    kind = Column(String)
    etag = Column(String)
    title = Column(String, index=True)
    updated = Column(String) # RFC 3339 timestamp
    selfLink = Column(String)
    parent = Column(String, nullable=True)
    position = Column(String)
    notes = Column(String)
    status = Column(String)
    due_date = Column(String, nullable=True) # RFC 3339 timestamp, renamed from 'due'
    completed = Column(String, nullable=True) # RFC 3339 timestamp
    deleted = Column(Boolean, default=False)
    hidden = Column(Boolean, default=False)
    webViewLink = Column(String)
    assignmentInfo = Column(JSON, nullable=True) # Complex object
    links = Column(JSON, nullable=True) # Array of objects
    tasklist_id = Column(String, nullable=True) # Needed to update the task on Google
    
    # Custom fields
    priority = Column(String, default=DEFAULT_PRIORITY)
    project_name = Column(String, nullable=True)
    hashtags = Column(JSON, nullable=True) # Derived from the title
    estimated_time_minutes = Column(Integer, nullable=True)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="tasks")