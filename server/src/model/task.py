from sqlalchemy import Column, Integer, String, Boolean, Date, Text
from .base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_name = Column(String(255), nullable=False)
    event_description = Column(Text, nullable=True)
    date = Column(Date, nullable=False)
    priority = Column(String(20), nullable=False, default="Medium")
    is_active = Column(Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        """Helper to convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "event_name": self.event_name,
            "event_description": self.event_description,
            "date": self.date.isoformat() if self.date else None,
            "priority": self.priority,
            "is_active": self.is_active,
        }

