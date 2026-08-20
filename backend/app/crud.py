from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Category, Customer, Product, Quote, User


def list_items(db: Session, model): return db.scalars(select(model)).all()
def get_item(db: Session, model, item_id: int): return db.get(model, item_id)
def create_item(db: Session, obj):
    db.add(obj); db.commit(); db.refresh(obj); return obj
def delete_item(db: Session, obj):
    db.delete(obj); db.commit()

def update_item(db: Session, obj, data: dict):
    for key, value in data.items(): setattr(obj, key, value)
    db.commit(); db.refresh(obj); return obj
