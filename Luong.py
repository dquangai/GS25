from flask import Flask, request, render_template, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
DB_NAME = 'shifts.db'

shift_hours = {
    '6-10': 4, '10-14': 4, '14-18': 4, '18-22': 4,
    '6-14': 8, '14-22': 8,
    '22-6': 8,
    'OFF': 0
}

HOURLY_RATE = 23800
NIGHT_RATE = round(HOURLY_RATE * 1.3)
PARTTIME_PHU_CAP = 150000
FULLTIME_PHU_CAP = 300000

os.makedirs("templates", exist_ok=True)

form_template = '''
<!DOCTYPE html>
<html>
<head>
  <title>Nhập Ca Làm</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container mt-5">
  <h2 class="mb-4">📝 Nhập Ca Làm</h2>
  <form method="POST">
    <div class="mb-3">
      <label for="date" class="form-label">Ngày làm ({{start}} → {{end}})</label>
      <input type="date" name="date" id="date" class="form-control" required value="{{today}}">
    </div>
    <div class="mb-3">
      <label for="shift" class="form-label">Ca làm</label>
      <select name="shift" id="shift" class="form-select">
        <option>6-10</option>
        <option>10-14</option>
        <option>14-18</option>
        <option>18-22</option>
        <option>6-14</option>
        <option>14-22</option>
        <option>22-6</option>
        <option>OFF</option>
      </select>
    </div>
    <div class="mb-3">
      <label for="type" class="form-label">Loại nhân viên</label>
      <select name="type" id="type" class="form-select">
        <option value="part-time">Part-time</option>
        <option value="full-time">Full-time</option>
      </select>
    </div>
    <button type="submit" class="btn btn-success">Lưu Ca Làm</button>
    <a href="/report" class="btn btn-primary">Xem Bảng Lương</a>
    <a href="/reset" class="btn btn-danger float-end" onclick="return confirm('Bạn có chắc chắn muốn xóa toàn bộ dữ liệu?')">Reset Dữ Liệu</a>
  </form>
</body>
</html>
'''

report_template = '''
<!DOCTYPE html>
<html>
<head>
  <title>Bảng Công & Lương</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container mt-5">
  <h2>📋 Bảng Công từ {{start}} đến {{end}}</h2>
  <table class="table table-bordered mt-3">
    <thead>
      <tr>
        <th>Ngày</th>
        <th>Ca</th>
        <th>Loại</th>
        <th>Giờ</th>
        <th>Lương</th>
      </tr>
    </thead>
    <tbody>
      {% for r in data %}
      <tr>
        <td>{{ r.date }}</td>
        <td>{{ r.shift }}</td>
        <td>{{ r.type }}</td>
        <td>{{ r.hours }}</td>
        <td>{{ r.salary }} VND</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <h4 class="mt-4">🧲 Tổng kết</h4>
  <ul>
    <li>Tổng số giờ: <strong>{{ total_hours }}</strong></li>
    <li>Lương chính: <strong>{{ main_salary }}</strong> VND</li>
    <li>Trợ cấp gửi xe: <strong>{{ parking }}</strong> VND</li>
    <li><b>Tổng thu nhập:</b> <strong class="text-success">{{ total_salary }} VND</strong></li>
  </ul>
  <a href="/" class="btn btn-secondary">← Nhập tiếp</a>
</body>
</html>
'''

with open("templates/form.html", "w", encoding="utf-8") as f:
    f.write(form_template)

with open("templates/report.html", "w", encoding="utf-8") as f:
    f.write(report_template)

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            shift TEXT,
            hours INTEGER,
            salary INTEGER,
            user_type TEXT
        )''')
        conn.commit()

def get_current_range():
    today = datetime.today()
    start = today.replace(day=26)
    if today.day < 26:
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=26)
    end = (start + timedelta(days=32)).replace(day=25)
    return start.date(), end.date()

@app.route('/', methods=['GET', 'POST'])
def form():
    start, end = get_current_range()
    today = datetime.today().strftime('%Y-%m-%d')
    if request.method == 'POST':
        date = request.form['date']
        shift = request.form['shift']
        user_type = request.form['type']

        if not (str(start) <= date <= str(end)):
            return "<h3 style='color:red;'>Chỉ được nhập từ %s đến %s</h3><a href='/'>Quay lại</a>" % (start, end)

        hours = shift_hours.get(shift, 0)
        rate = NIGHT_RATE if shift == '22-6' else HOURLY_RATE
        salary = hours * rate

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO shifts (date, shift, hours, salary, user_type) VALUES (?, ?, ?, ?, ?)',
                      (date, shift, hours, salary, user_type))
            conn.commit()

        return redirect(url_for('form'))

    return render_template('form.html', start=start, end=end, today=today)

@app.route('/report')
def report():
    start, end = get_current_range()
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('SELECT date, shift, hours, salary, user_type FROM shifts WHERE date BETWEEN ? AND ? ORDER BY date',
                  (str(start), str(end)))
        rows = c.fetchall()

    data = [dict(date=r[0], shift=r[1], hours=r[2], salary="{:,}".format(r[3]), type=r[4]) for r in rows]
    total_hours = sum(r['hours'] for r in data)
    total_salary_raw = sum(int(r['salary'].replace(',', '')) for r in data)
    user_types = set(r['type'] for r in data)
    parking = FULLTIME_PHU_CAP if 'full-time' in user_types else PARTTIME_PHU_CAP if 'part-time' in user_types else 0
    total_salary = total_salary_raw + parking

    formatted_total_salary = "{:,}".format(total_salary)
    formatted_main_salary = "{:,}".format(total_salary - parking)
    formatted_parking = "{:,}".format(parking)

    return render_template('report.html', data=data, total_hours=total_hours,
                           total_salary=formatted_total_salary,
                           main_salary=formatted_main_salary,
                           parking=formatted_parking,
                           start=start, end=end)

@app.route('/reset')
def reset():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM shifts')
        conn.commit()
    return redirect(url_for('form'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
