from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum as PyEnum

db = SQLAlchemy()

class IdentityEnum(PyEnum):
    STUDENT = '재학생'
    GRADUATE = '졸업생'
    STAFF = '교직원'
    GENERAL = '일반인'

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.String(36), nullable=False)
    area = db.Column(db.Integer, nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    satisfaction = db.Column(db.Boolean, nullable=False)
    identity = db.Column(db.Enum(IdentityEnum), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.astimezone(datetime.now()))

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.astimezone(datetime.now()))

def create_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
