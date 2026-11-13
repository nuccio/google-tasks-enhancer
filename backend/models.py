from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # NON salvare i token in chiaro in produzione! Usa una soluzione di crittografia.
    google_tokens = Column(JSON) 
    
    tasks = relationship("Task", back_populates="owner")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True) # ID di Google Tasks
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
    assignmentInfo = Column(JSON, nullable=True) # Oggetto complesso
    links = Column(JSON, nullable=True) # Array di oggetti
    tasklist_id = Column(String, nullable=True) # Aggiunto per poter aggiornare il task su Google
    
    # Campi personalizzati
    priority = Column(String, default="media")
    project_name = Column(String, nullable=True)
    hashtags = Column(JSON, nullable=True) # Dedotti dal titolo
    estimated_time_minutes = Column(Integer, nullable=True)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="tasks")