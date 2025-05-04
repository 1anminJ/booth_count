from datetime import datetime, date
from models import db, Log

class LogService:
    @staticmethod
    def is_duplicate_today(uuid, area):
        today = date.today()
        record = Log.query.filter(
            Log.uuid == uuid,
            Log.area == area,
            db.func.date(Log.timestamp) == today
        ).first()
        return record is not None

    @staticmethod
    def add_log(uuid, identity, area, ip, satisfaction=None):
        if LogService.is_duplicate_today(uuid, area):
            return None

        if isinstance(satisfaction, str):
            satisfaction = satisfaction.lower() == 'true'
        new_log = Log(
            uuid=uuid,
            area=area,
            identity=identity,
            ip=ip,
            satisfaction=satisfaction,
            timestamp=datetime.now(),
        )
        db.session.add(new_log)
        db.session.commit()
        return new_log
