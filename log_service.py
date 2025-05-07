from datetime import datetime, date
from models import db, Log

class LogService:
    @staticmethod
    def validate_params(uuid, area, identity, rating):
        # 필수 파라미터 확인
        if not uuid or not area or not identity or rating is None:
            return False

        # area가 숫자인지 확인
        if not area.isdigit():
            return False

        return True

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
    def add_log(uuid, identity, area, ip, rating=None):
        if LogService.is_duplicate_today(uuid, area):
            return None

        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()

        rating_int = int(rating)

        new_log = Log(
            uuid=uuid,
            area=area,
            identity=identity,
            ip=ip,
            rating=rating_int,
            timestamp=datetime.now(),
        )
        db.session.add(new_log)
        db.session.commit()
        return new_log
