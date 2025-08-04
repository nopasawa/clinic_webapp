# database.py (Complete and Corrected Version)

import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    """
    ฟังก์ชันสำหรับสร้างไฟล์ฐานข้อมูล clinic.db และตารางทั้งหมด
    """
    try:
        with sqlite3.connect('clinic.db') as conn:
            cursor = conn.cursor()
            print("กำลังสร้าง/อัปเดตฐานข้อมูลและตาราง...")
            cursor.execute("PRAGMA foreign_keys = ON;")

            # 1. ตาราง doctors
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                available_time TEXT
            )
            """)

            # 2. ตาราง patients (มีคอลัมน์ password)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """)

            # 3. ตารางหัวข้อการนัดหมาย
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointment_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE
            )
            """)

            # 4. ตาราง appointments (มีคอลัมน์ subject_id)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                subject_id INTEGER,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES appointment_subjects (id) ON DELETE SET NULL
            )
            """)

            # 5. ตาราง users สำหรับเจ้าหน้าที่
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('staff', 'admin'))
            )
            """)

            # เพิ่มข้อมูลหัวข้อตัวอย่าง (ถ้ายังไม่มี)
            cursor.execute("SELECT id FROM appointment_subjects")
            if not cursor.fetchone():
                default_subjects = ['ตรวจสุขภาพทั่วไป', 'ปรึกษาปัญหาผิว', 'ติดตามผลการรักษา', 'ทำแผล']
                for subject in default_subjects:
                    cursor.execute("INSERT INTO appointment_subjects (title) VALUES (?)", (subject,))
                print("เพิ่มหัวข้อการนัดหมายตัวอย่างสำเร็จ")

            # เพิ่มข้อมูลเจ้าหน้าที่ admin เริ่มต้น (ถ้ายังไม่มี)
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                hashed_password = generate_password_hash('admin123')
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                               ('admin', hashed_password, 'admin'))
                print("สร้างผู้ใช้ 'admin' (รหัสผ่าน: admin123) สำเร็จ")

            conn.commit()
            print("ฐานข้อมูลพร้อมใช้งาน!")

    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาดกับฐานข้อมูล: {e}")

if __name__ == '__main__':
    init_db()