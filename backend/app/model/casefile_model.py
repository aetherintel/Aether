from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base, PortableArray

class CaseFileModel(Base):
    __tablename__ = "casefiles"
    id         = Column(Integer, primary_key=True, index=True)
    owner_id   = Column(String,  nullable=False, index=True)
    title      = Column(String,  index=True)
    description = Column(Text)  
    category   = Column(String)
    postCount  = Column(Integer)
    tgchannels = Column(PortableArray(String))
    topics     = Column(PortableArray(String))
    terms      = Column(PortableArray(String))
    thumbnails = Column(PortableArray(String))
    duration   = Column(Integer)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    archived   = Column(Boolean, default=False)
    
    # Report Configuration
    report_frequency = Column(String, default="daily") # daily, weekly, monthly, none
    report_sections = Column(PortableArray(String), default=["stats", "charts", "messages"])

class ReportModel(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, index=True)
    path = Column(String)
    filename = Column(String)
    period = Column(String) # daily, weekly, monthly
    created_at = Column(DateTime(timezone=True), server_default=func.now())
