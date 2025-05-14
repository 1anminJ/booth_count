from datetime import datetime
from models import SystemSetting, db


class SettingsService:
    @staticmethod
    def is_service_activated():
        """서비스 활성화 상태를 확인"""
        return SystemSetting.get_value('service_activated', 'false') == 'true'

    @staticmethod
    def set_service_status(active):
        """서비스 활성화 상태를 설정"""
        setting = SystemSetting.query.filter_by(key='service_activated').first()
        if not setting:
            setting = SystemSetting(key='service_activated')
        setting.value = 'true' if active else 'false'
        setting.updated_at = datetime.now()
        db.session.add(setting)
        db.session.commit()
