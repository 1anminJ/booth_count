from flask import Flask, request, render_template, send_file
from io import BytesIO
from models import create_db, Log
from log_service import LogService
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

create_db(app)

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

@app.route('/admin')
def admin():
    return render_template('admin.html')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))