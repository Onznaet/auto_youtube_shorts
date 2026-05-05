from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import get_db

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str

@router.get("/projects")
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    return [{"id": p.id, "name": p.name} for p in projects]

@router.post("/projects")
def create_project(req: ProjectCreate, db: Session = Depends(get_db)):
    p = models.Project(name=req.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "name": p.name}

@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if p:
        db.delete(p)
        db.commit()
    return {"status": "ok"}
