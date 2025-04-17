from flask import Flask, request, render_template
import csv
import os
from datetime import datetime
from flask import send_file

app = Flask(__name__)
LOG_FILE = "log.csv"

def is_duplicate(ip, uuid):
    if not os.path.exists(LOG_FILE):
        return False

    with open(LOG_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row.get('ip') == ip and row.get('uuid') == uuid:
                return True
    return False

@app.route('/admin')
def admin():
    if not os.path.exists(LOG_FILE):
        return "<h3>아직 아무 데이터도 없습니다.</h3>"

    with open(LOG_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)

    html = "<h2>제출 내역</h2><table border='1' style='border-collapse: collapse;'>"
    for row in rows:
        html += "<tr>" + "".join([f"<td style='padding: 5px 10px;'>{cell}</td>" for cell in row]) + "</tr>"
    html += "</table><br>"

    html += "<form action='/download'><button type='submit'>CSV 다운로드</button></form>"

    return html

@app.route('/download')
def download_csv():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, as_attachment=True)
    return "<h3>다운로드할 데이터가 없습니다.</h3>"

@app.route('/', methods=['GET', 'POST'])
def form():
    # ip = request.remote_addr
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if request.method == 'POST':
        uuid = request.form.get('uuid')
        identity = request.form.get('identity')

        # 유효성 검사
        if not uuid or not identity:
            return "<h3>잘못된 요청입니다. UUID 또는 신분 정보가 누락되었습니다.</h3>"

        # 중복 확인
        if is_duplicate(ip, uuid):
            return "<h3>중복 참여는 불가능합니다.</h3>"

        # 제출 시간
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # CSV에 저장
        is_new_file = not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(['timestamp', 'ip', 'uuid', 'identity'])
            writer.writerow([timestamp, ip, uuid, identity])

        return f"<h3>{identity}으로 참여해주셔서 감사합니다!</h3>"

    return render_template("form.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
