import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_that_is_long_and_random'
DATABASE = 'clinic.db'

# --- Database Connection Handling ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- Login Required Decorator ---
def login_required(role="any"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('กรุณาล็อกอินเพื่อเข้าถึงหน้านี้', 'warning')
                return redirect(url_for('login'))
            
            allowed_roles = role.split(',')
            if role != "any" and session.get('role') not in allowed_roles:
                flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
                return redirect(url_for('index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name, phone, password = request.form['name'], request.form['phone'], request.form['password']
        db = get_db()
        if db.execute('SELECT id FROM patients WHERE phone = ?', (phone,)).fetchone():
            flash('เบอร์โทรศัพท์นี้ถูกใช้งานแล้ว', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        db.execute('INSERT INTO patients (name, phone, password) VALUES (?, ?, ?)', (name, phone, hashed_password))
        db.commit()
        flash('ลงทะเบียนสำเร็จ! กรุณาล็อกอิน', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session and session.get('role') == 'patient': return redirect(url_for('index'))
    if request.method == 'POST':
        phone, password = request.form['phone'], request.form['password']
        db = get_db()
        patient = db.execute('SELECT * FROM patients WHERE phone = ?', (phone,)).fetchone()
        if patient and check_password_hash(patient['password'], password):
            session.clear()
            session['user_id'] = patient['id']
            session['user_name'] = patient['name']
            session['role'] = 'patient'
            return redirect(url_for('index'))
        else:
            flash('เบอร์โทรศัพท์หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if 'user_id' in session and session.get('role') != 'patient': return redirect(url_for('search_appointments'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db = get_db()
        staff = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if staff and check_password_hash(staff['password'], password):
            session.clear()
            session['user_id'] = staff['id']
            session['user_name'] = staff['username']
            session['role'] = staff['role']
            return redirect(url_for('search_appointments'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('staff_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('คุณได้ออกจากระบบแล้ว', 'info')
    return redirect(url_for('login'))

# --- Patient Routes ---
@app.route('/')
@login_required(role="patient")
def index():
    db = get_db()
    doctors = db.execute('SELECT * FROM doctors ORDER BY name').fetchall()
    subjects = db.execute('SELECT * FROM appointment_subjects ORDER BY title').fetchall()
    return render_template('index.html', doctors=doctors, subjects=subjects)

@app.route('/book', methods=['POST'])
@login_required(role="patient")
def book():
    db = get_db()
    doctor_id, subject_id, patient_id = request.form['doctor_id'], request.form['subject_id'], session['user_id']
    slot = request.form.get('appointment_slot')
    if not slot or '|' not in slot:
        flash('กรุณาเลือกวันและเวลาที่ถูกต้อง', 'danger')
        return redirect(url_for('index'))
    app_date, app_time = slot.split('|')
    existing_appt = db.execute("SELECT id FROM appointments WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? AND status = 'Confirmed'", (doctor_id, app_date, app_time)).fetchone()
    if existing_appt:
        flash('ขออภัย คิวเวลานี้เพิ่งถูกจองไป กรุณาเลือกเวลาอื่น', 'danger')
        return redirect(url_for('index'))
    self_booked_appt = db.execute("SELECT id FROM appointments WHERE patient_id = ? AND doctor_id = ? AND appointment_date = ? AND appointment_time = ? AND status = 'Confirmed'", (patient_id, doctor_id, app_date, app_time)).fetchone()
    if self_booked_appt:
        flash('คุณได้จองคิวนี้ไปแล้ว ไม่สามารถจองซ้ำได้', 'warning')
        return redirect(url_for('index'))
    db.execute('INSERT INTO appointments (patient_id, doctor_id, subject_id, appointment_date, appointment_time, status) VALUES (?, ?, ?, ?, ?, ?)', (patient_id, doctor_id, subject_id, app_date, app_time, 'Confirmed'))
    db.commit()
    flash('การนัดหมายของคุณได้รับการยืนยัน!', 'success')
    return redirect(url_for('my_appointments'))

@app.route('/my_appointments')
@login_required(role="patient")
def my_appointments():
    db = get_db()
    appointments = db.execute("""
        SELECT a.id, d.name AS doctor_name, s.title AS subject_title, a.appointment_date, a.appointment_time, a.status
        FROM appointments a JOIN doctors d ON a.doctor_id = d.id LEFT JOIN appointment_subjects s ON a.subject_id = s.id
        WHERE a.patient_id = ? ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (session['user_id'],)).fetchall()
    return render_template('my_appointments.html', appointments=appointments)

# --- Staff & Admin Routes ---
@app.route('/search_appointments', methods=['GET', 'POST'])
@login_required(role="staff,admin")
def search_appointments():
    db = get_db()
    appointments = None
    search_phone = ""
    if request.method == 'POST':
        search_phone = request.form.get('phone', '')
        appointments = db.execute("""
            SELECT a.id, p.name AS patient_name, d.name AS doctor_name, a.appointment_date, a.appointment_time, a.status
            FROM appointments a JOIN patients p ON a.patient_id = p.id JOIN doctors d ON a.doctor_id = d.id
            WHERE p.phone = ? ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """, (search_phone,)).fetchall()
        if not appointments and search_phone: flash(f'ไม่พบข้อมูลนัดหมายสำหรับเบอร์ {search_phone}', 'warning')
    return render_template('search_appointments.html', appointments=appointments, search_phone=search_phone)

@app.route('/checkout/<int:appointment_id>', methods=['POST'])
@login_required(role="staff,admin")
def checkout_appointment(appointment_id):
    db = get_db()
    db.execute("UPDATE appointments SET status = 'รับบริการเรียบร้อย' WHERE id = ?", (appointment_id,)); db.commit()
    flash(f'บันทึกการเข้ารับบริการของนัดหมาย ID {appointment_id} สำเร็จ', 'success')
    return redirect(request.referrer or url_for('search_appointments'))

@app.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required()
def cancel_appointment(appointment_id):
    db = get_db()
    appt = db.execute('SELECT patient_id FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
    if not appt:
        flash('ไม่พบข้อมูลการนัดหมายนี้', 'danger')
        return redirect(url_for('index'))
    if session['role'] == 'patient' and session['user_id'] == appt['patient_id']:
        db.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = ?", (appointment_id,)); db.commit()
        flash('ยกเลิกการนัดหมายสำเร็จ', 'success')
        return redirect(url_for('my_appointments'))
    elif session['role'] in ['staff', 'admin']:
        db.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = ?", (appointment_id,)); db.commit()
        flash(f'ยกเลิกการนัดหมาย ID {appointment_id} สำเร็จ', 'success')
        return redirect(request.referrer or url_for('search_appointments'))
    else:
        flash('คุณไม่มีสิทธิ์ยกเลิกนัดหมายนี้', 'danger')
        return redirect(url_for('index'))

@app.route('/calendar')
@login_required(role="staff,admin")
def calendar_view():
    return render_template('calendar.html')

# --- Admin Only Routes ---
@app.route('/doctors', methods=['GET', 'POST'])
@login_required(role="admin")
def manage_doctors():
    db = get_db()
    if request.method == 'POST':
        name, specialty = request.form['name'], request.form['specialty']
        days_selected, start_time, end_time = request.form.getlist('days'), request.form['start_time'], request.form['end_time']
        if days_selected and start_time and end_time:
            available_time = f"{', '.join(days_selected)} | {start_time} - {end_time}"
        else:
            available_time = "ไม่ได้ระบุ"
        db.execute('INSERT INTO doctors (name, specialty, available_time) VALUES (?, ?, ?)', (name, specialty, available_time)); db.commit()
        flash(f'เพิ่มข้อมูลแพทย์ "{name}" สำเร็จ', 'success')
        return redirect(url_for('manage_doctors'))
    doctors = db.execute('SELECT * FROM doctors ORDER BY id').fetchall()
    return render_template('doctors.html', doctors=doctors)

@app.route('/doctor/delete/<int:doctor_id>', methods=['POST'])
@login_required(role="admin")
def delete_doctor(doctor_id):
    db = get_db()
    appointments = db.execute("SELECT id FROM appointments WHERE doctor_id = ? AND status = 'Confirmed'", (doctor_id,)).fetchall()
    if appointments:
        flash('ไม่สามารถลบแพทย์ได้ เนื่องจากยังมีนัดหมายค้างอยู่', 'danger')
    else:
        db.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,)); db.commit()
        flash('ลบข้อมูลแพทย์สำเร็จ', 'success')
    return redirect(url_for('manage_doctors'))

@app.route('/subjects', methods=['GET', 'POST'])
@login_required(role="admin")
def manage_subjects():
    db = get_db()
    if request.method == 'POST':
        action, title, subject_id = request.form.get('action'), request.form.get('title'), request.form.get('subject_id')
        if action == 'add' and title:
            try:
                db.execute("INSERT INTO appointment_subjects (title) VALUES (?)", (title,)); db.commit()
                flash('เพิ่มหัวข้อสำเร็จ', 'success')
            except sqlite3.IntegrityError: flash('หัวข้อนี้มีอยู่แล้ว', 'danger')
        elif action == 'delete' and subject_id:
            db.execute("DELETE FROM appointment_subjects WHERE id = ?", (subject_id,)); db.commit()
            flash('ลบหัวข้อสำเร็จ', 'success')
        return redirect(url_for('manage_subjects'))
    subjects = db.execute("SELECT * FROM appointment_subjects ORDER BY title").fetchall()
    return render_template('subjects.html', subjects=subjects)

# --- API Routes ---
@app.route('/api/doctor/<int:doctor_id>/slots')
@login_required(role="patient")
def get_doctor_slots(doctor_id):
    db = get_db()
    doctor = db.execute('SELECT available_time FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    if not doctor or not doctor['available_time']: return jsonify({})
    try:
        days_part, time_part = doctor['available_time'].split('|')
        start_time_str, end_time_str = [t.strip() for t in time_part.split('-')]
        work_days_th = [d.strip() for d in days_part.split(',')]
        start_time, end_time = datetime.strptime(start_time_str, '%H:%M').time(), datetime.strptime(end_time_str, '%H:%M').time()
    except (ValueError, IndexError): return jsonify({})
    th_day_to_weekday = {'จันทร์': 0, 'อังคาร': 1, 'พุธ': 2, 'พฤหัสบดี': 3, 'ศุกร์': 4, 'เสาร์': 5, 'อาทิตย์': 6}
    work_day_indices = [th_day_to_weekday.get(day) for day in work_days_th]
    all_booked_slots = {f"{r['appointment_date']}|{r['appointment_time']}" for r in db.execute("SELECT appointment_date, appointment_time FROM appointments WHERE doctor_id = ? AND status = 'Confirmed'",(doctor_id,)).fetchall()}
    user_booked_slots = {f"{r['appointment_date']}|{r['appointment_time']}" for r in db.execute("SELECT appointment_date, appointment_time FROM appointments WHERE doctor_id = ? AND patient_id = ? AND status = 'Confirmed'",(doctor_id, session['user_id'])).fetchall()}
    available_slots_by_date, today, slot_interval = defaultdict(list), datetime.now(), timedelta(minutes=30)
    for i in range(30):
        current_date = today + timedelta(days=i)
        if current_date.weekday() in work_day_indices:
            slot_time = datetime.combine(current_date, start_time)
            end_of_day = datetime.combine(current_date, end_time)
            while slot_time < end_of_day:
                date_str, time_str = slot_time.strftime('%Y-%m-%d'), slot_time.strftime('%H:%M')
                slot_key = f"{date_str}|{time_str}"
                if slot_key not in all_booked_slots or slot_key in user_booked_slots:
                    available_slots_by_date[date_str].append({"time": time_str, "booked_by_user": slot_key in user_booked_slots})
                slot_time += slot_interval
    return jsonify(available_slots_by_date)

@app.route('/api/appointments')
@login_required(role="staff,admin")
def api_appointments():
    db = get_db()
    appts_query = db.execute("""
        SELECT p.name as patient_name, d.name as doctor_name, s.title as subject_title, a.appointment_date, a.appointment_time
        FROM appointments a JOIN patients p ON a.patient_id = p.id JOIN doctors d ON a.doctor_id = d.id LEFT JOIN appointment_subjects s ON a.subject_id = s.id
        WHERE a.status = 'Confirmed'
    """).fetchall()
    events = [{'title': f"นพ. {a['doctor_name']}", 'start': f"{a['appointment_date']}T{a['appointment_time']}", 'color': '#007bff',
               'extendedProps': {'patientName': f"คุณ {a['patient_name']}", 'doctorName': f"นพ. {a['doctor_name']}", 'subjectTitle': a['subject_title'] or 'ไม่ได้ระบุ',
                                 'appointmentDate': a['appointment_date'], 'appointmentTime': a['appointment_time']}} for a in appts_query]
    return jsonify(events)

if __name__ == '__main__':
    app.run(debug=True)