from flask import Flask, request, render_template, send_file
import csv
import os
from datetime import datetime

app = Flask(__name__)
LOG_FILE = "log.csv"
#  UUID + area + today 조합 중복 체크
def is_duplicate_today(uuid, area):
    if not os.path.exists(LOG_FILE):
        return False

    today = datetime.now().strftime('%Y-%m-%d')

    with open(LOG_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row.get('uuid') == uuid and row.get('area') == area:
                row_date = row.get('timestamp', '')[:10]
                if row_date == today:
                    return True
    return False

@app.route('/', methods=['GET', 'POST'])
def form():
    area = request.args.get('area')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if request.method == 'POST':
        uuid = request.form.get('uuid')
        identity = request.form.get('identity')
        area = request.form.get('area')

        if not uuid or not identity or not area:
            return "<h3>잘못된 요청입니다. 정보가 누락되었습니다.</h3>"

        if is_duplicate_today(uuid, area):
            return render_template("duplicate.html")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        is_new_file = not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(['timestamp', 'area', 'ip', 'uuid', 'identity'])
            writer.writerow([timestamp, area, ip, uuid, identity])

        return render_template("thanks.html", identity=identity)

    return render_template("form.html")

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
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 중복 체크
    if is_duplicate_today(uuid, area):
        return render_template('duplicate.html')

    is_new_file = not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(['timestamp', 'area', 'ip', 'uuid', 'identity', 'satisfaction'])
        writer.writerow([timestamp, area, ip, uuid, identity, satisfaction])

    return render_template('thanks.html', identity=identity)


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
