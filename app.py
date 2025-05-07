from flask import Flask, request, render_template, send_file, session, redirect, jsonify
from io import BytesIO
from google.auth.transport import requests
from google.oauth2 import id_token
from models import create_db, Log, Admin
from log_service import LogService
import os
from dotenv import load_dotenv
import base64
import json
import firebase_admin
from firebase_admin import credentials, auth
import pandas as pd

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

def verify_firebase_token(token):
    try:
        decoded_token = id_token.verify_oauth2_token(
            token, requests.Request(), audience=FIREBASE_PROJECT_ID
        )
        return decoded_token
    except Exception as e:
        print(f"토큰 검증 오류: {e}")
        return None

@app.route('/', methods=['GET'])
def form():
    return render_template('form.html')

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
    satisfaction = request.form.get('satisfaction')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not LogService.validate_params(uuid, area, identity, satisfaction):
        return render_template('invalid_access.html')

    if LogService.is_duplicate_today(uuid, area):
        return render_template('duplicate.html')

    LogService.add_log(uuid, identity, area, ip, satisfaction)
    return render_template('thanks.html', identity=identity)

@app.route('/invalid_access', methods=['GET'])
def invalid_access():
    return render_template('invalid_access.html')

@app.route('/download')
def download_csv():
    logs = Log.query.all()

    # SQLAlchemy 객체를 dict 리스트로 변환
    data = [{
        '참여 시간': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        '부스 번호': log.area,
        '신분': log.identity.name,
    } for log in logs]

    df = pd.DataFrame(data)

    # Excel 파일 생성
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Logs')

    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True, # 바로 다운로드 되게끔 설정
        download_name='노들축제 우수부스.xlsx'
    )

@app.route('/admin_login', methods=['GET'])
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


@app.route('/verify_user', methods=['POST'])
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
def admin():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    logs = Log.query.all()
    return render_template('admin.html', logs=logs, admin_phone=session.get('admin_phone'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin_login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
