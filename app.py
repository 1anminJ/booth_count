from flask import Flask, request, render_template, send_file, session, redirect, jsonify
from sqlalchemy import func
from io import BytesIO
from google.auth.transport import requests
from google.oauth2 import id_token
from models import create_db, Log, Admin, db
from log_service import LogService
import os
from dotenv import load_dotenv
from datetime import datetime
import base64
import json
import firebase_admin
from firebase_admin import credentials, auth
import pandas as pd
from settings_service import SettingsService

load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID')
FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')
FIREBASE_AUTH_DOMAIN = os.getenv('FIREBASE_AUTH_DOMAIN')
FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET')
FIREBASE_MESSAGING_SENDER_ID = os.getenv('FIREBASE_MESSAGING_SENDER_ID')
FIREBASE_APP_ID = os.getenv('FIREBASE_APP_ID')
FIREBASE_MEASUREMENT_ID = os.getenv('FIREBASE_MEASUREMENT_ID')
FIREBASE_SERVICE_ACCOUNT = os.getenv('FIREBASE_SERVICE_ACCOUNT')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.urandom(24)


def initialize_firebase_admin():
    if not firebase_admin._apps:  # 아직 초기화되지 않았는지 확인
        try:
            # base64 디코딩
            service_account_json = base64.b64decode(FIREBASE_SERVICE_ACCOUNT).decode('utf-8')
            service_account_dict = json.loads(service_account_json)

            # 메모리에서 직접 사용
            cred = credentials.Certificate(service_account_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Firebase Admin SDK 초기화 오류: {e}")


create_db(app)
initialize_firebase_admin()


def _generate_excel_response(logs, filename_base):
    data = [{
        '참여 시간': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        '부스 번호': log.area,
        '신분': log.identity.name,
    } for log in logs]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Logs')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{filename_base}.xlsx'
    )


def _get_statistics(filter_date=None):
    stats = {}
    # 부스별 통계 쿼리
    area_query = db.session.query(Log.area, func.count(Log.id))
    # 신분별 통계 쿼리
    identity_query = db.session.query(Log.identity, func.count(Log.id))

    if filter_date:
        area_query = area_query.filter(func.date(Log.timestamp) == filter_date)
        identity_query = identity_query.filter(func.date(Log.timestamp) == filter_date)

    area_counts = area_query.group_by(Log.area).all()
    stats['area_labels'] = [row[0] for row in area_counts]
    stats['area_data'] = [row[1] for row in area_counts]

    identity_counts = identity_query.group_by(Log.identity).all()
    stats['identity_labels'] = [row[0].value for row in identity_counts]
    stats['identity_data'] = [row[1] for row in identity_counts]

    return stats


def verify_firebase_token(token):
    try:
        decoded_token = id_token.verify_oauth2_token(
            token, requests.Request(), audience=FIREBASE_PROJECT_ID
        )
        return decoded_token
    except Exception as e:
        print(f"토큰 검증 오류: {e}")
        return None


@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ''
    return value.strftime(format)


@app.route('/', methods=['GET'])
def form():
    # 서비스 비활성화 상태 확인
    if not SettingsService.is_service_activated():
        return render_template('inactive.html')

    area = request.args.get('area')
    if not area:
        return redirect('/invalid_access')

    return render_template('form.html', area=area)


@app.route('/feedback', methods=['POST'])
def feedback():
    uuid = request.form.get('uuid')
    area = request.form.get('area')
    identity = request.form.get('identity')
    return render_template('feedback.html', uuid=uuid, area=area, identity=identity)


@app.route('/submit', methods=['POST'])
def submit():
    uuid = request.form.get('uuid')
    area = request.form.get('area')
    identity = request.form.get('identity')
    rating = request.form.get('rating')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not LogService.validate_params(uuid, area, identity, rating):
        return render_template('invalid_access.html')

    if LogService.is_duplicate_today(uuid, area):
        return render_template('duplicate.html')

    LogService.add_log(uuid, identity, area, ip, rating)
    return render_template('thanks.html', identity=identity)


@app.route('/invalid_access', methods=['GET'])
def invalid_access():
    return render_template('invalid_access.html')


@app.route('/admin/login', methods=['GET'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect('/admin')

    firebase_config = {
        'apiKey': FIREBASE_API_KEY,
        'authDomain': FIREBASE_AUTH_DOMAIN,
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
        'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
        'appId': FIREBASE_APP_ID,
        'measurementId': FIREBASE_MEASUREMENT_ID
    }

    return render_template('admin_login.html', firebase_config=firebase_config)


@app.route('/admin/verify', methods=['POST'])
def verify_user():
    data = request.json

    # ID 토큰 검증
    token = data.get('idToken')
    if not token:
        return jsonify({'success': False, 'message': 'ID 토큰이 필요합니다'}), 400

    try:
        # Firebase로 토큰 검증
        decoded_token = auth.verify_id_token(token)

        # 사용자 전화번호 가져오기
        user_phone = decoded_token.get('phone_number')
        if not user_phone:
            return jsonify({'success': False, 'message': '전화번호 정보를 찾을 수 없습니다'}), 400

        # 관리자 확인
        service_admin = Admin.query.filter_by(phone_number=user_phone).first()
        if not service_admin:
            return jsonify({'success': False, 'message': '등록된 관리자가 아닙니다.'}), 403

        # 세션 설정
        session['admin_logged_in'] = True
        session['admin_phone'] = user_phone
        return jsonify({'success': True})

    except auth.InvalidIdTokenError:
        return jsonify({'success': False, 'message': '유효하지 않은 토큰입니다'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'인증 오류: {str(e)}'}), 500

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    recent_logs = Log.query.order_by(Log.timestamp.desc()).limit(5).all()
    total_count = Log.query.count()

    # 전체 통계 데이터 가져오기
    stats = _get_statistics()

    # 서비스 활성화 상태 확인
    service_activated = SettingsService.is_service_activated()

    return render_template(
        'admin.html',
        admin_phone=session.get('admin_phone'),
        logs=recent_logs,
        total_count=total_count,
        area_labels=stats['area_labels'],
        area_data=stats['area_data'],
        identity_labels=stats['identity_labels'],
        identity_data=stats['identity_data'],
        service_activated=service_activated
    )


@app.route('/admin/<date_str>')
def admin_by_date(date_str):
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    try:
        selected_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return "잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용해주세요.", 400

    # 선택된 날짜의 로그 (최신순 정렬 추가)
    logs_for_date = Log.query.filter(func.date(Log.timestamp) == selected_date_obj).order_by(Log.timestamp.desc()).limit(5).all()

    # 전체 로그 수 (원본 코드와 동일하게 전체 카운트 유지)
    total_count = Log.query.count()

    # 선택된 날짜의 로그 수
    count_for_date = len(logs_for_date)

    # 선택된 날짜의 통계 데이터 가져오기
    stats_for_date = _get_statistics(filter_date=selected_date_obj)

    service_activated = SettingsService.is_service_activated()

    return render_template(
        'admin.html',
        admin_phone=session.get('admin_phone'),
        logs=logs_for_date,
        selected_date_str=selected_date_obj.strftime('%Y-%m-%d'),  # 템플릿에서 사용할 날짜 문자열
        total_count=total_count,  # 전체 로그 수
        count_for_date=count_for_date,  # 해당 날짜 로그 수
        area_labels=stats_for_date['area_labels'],
        area_data=stats_for_date['area_data'],
        identity_labels=stats_for_date['identity_labels'],
        identity_data=stats_for_date['identity_data'],
        service_activated=service_activated
    )


@app.route('/admin/download-excel')
def download_all_excel():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    logs = Log.query.order_by(Log.timestamp.asc()).all()
    return _generate_excel_response(logs, '노들축제 우수부스(전체)')


@app.route('/admin/<date_str>/download-excel')
def download_date_excel(date_str):
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return "잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용해주세요.", 400

    logs = Log.query.filter(func.date(Log.timestamp) == selected_date).order_by(Log.timestamp.asc()).all()  # 시간순 정렬 추가
    return _generate_excel_response(logs, f'노들축제 우수부스({selected_date.strftime("%Y-%m-%d")})')


@app.route('/admin/toggle-service', methods=['POST'])
def toggle_service():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다'}), 403

    data = request.json
    active = data.get('active', False)

    try:
        SettingsService.set_service_status(active)
        return jsonify({'success': True, 'active': active})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))