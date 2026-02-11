
import sys
import os
sys.path.append('/app')
from database import SessionLocal
from model.casefile_model import CaseFileModel

db = SessionLocal()
case = db.query(CaseFileModel).filter(CaseFileModel.id == 1).first()
if case:
    print(f"Case 1 Owner: {case.owner_id}")
    print(f"Case 1 Title: {case.title}")
    print(f"Case 1 Frequency: {case.report_frequency}")
else:
    print("Case 1 not found")
db.close()
