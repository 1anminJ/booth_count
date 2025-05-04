from flask import Flask, request, render_template, send_file
import csv
import io
from models import create_db, Log
from log_service import LogService
import os
from dotenv import load_dotenv

load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

create_db(app)

@app.route('/', methods=['GET', 'POST'])
def form():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if request.method == 'POST':
        uuid = request.form.get('uuid')
        identity = request.form.get('identity')
        area = request.form.get('area')

        if not uuid or not identity or not area:
            return "<h3>잘못된 요청입니다. 정보가 누락되었습니다.</h3>"

        if LogService.is_duplicate_today(uuid, area):
            return render_template('duplicate.html')

        LogService.add_log(uuid, identity, area, ip)
        return render_template('thanks.html', identity=identity)

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

    if LogService.is_duplicate_today(uuid, area):
        return render_template('duplicate.html')

    LogService.add_log(uuid, identity, area, ip, satisfaction)
    return render_template('thanks.html', identity=identity)


@app.route('/admin')
def admin():
    return None

@app.route('/download')
def download_csv():
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
