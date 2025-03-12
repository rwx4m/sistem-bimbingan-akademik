# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# Gunakan path absolut untuk database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'database.db')}")
app.config['SQLALCHEMY_DATABASE_URI'] = DB_PATH
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())

db = SQLAlchemy(app)

# Model User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hash password
    role = db.Column(db.String(10), nullable=False)  # 'admin', 'dosen', 'mahasiswa'

# Model Jadwal Bimbingan
class Bimbingan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mahasiswa_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dosen_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    waktu = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='menunggu')  # Status: menunggu, diterima, selesai
    catatan = db.Column(db.Text, nullable=True)  # Catatan dosen

@app.route('/')
def index():
    return render_template('index.html')

# Rute Histori Bimbingan (Dosen & Mahasiswa)
@app.route('/histori_bimbingan')
def histori_bimbingan():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    role = session['role']

    if role == 'mahasiswa':
        histori = Bimbingan.query.filter_by(mahasiswa_id=user_id, status='selesai').all()
    elif role == 'dosen':
        histori = Bimbingan.query.filter_by(dosen_id=user_id, status='selesai').all()
    else:
        return redirect(url_for('dashboard_admin'))

    return render_template('histori_bimbingan.html', histori=histori, role=role)

# Rute Konfirmasi Kehadiran Dosen
@app.route('/konfirmasi_kehadiran/<int:bimbingan_id>', methods=['GET'])
def konfirmasi_kehadiran(bimbingan_id):
    if 'user_id' not in session or session['role'] != 'dosen':
        return redirect(url_for('login'))

    bimbingan = Bimbingan.query.get_or_404(bimbingan_id)

    # Pastikan hanya dosen yang terkait yang bisa mengonfirmasi
    if bimbingan.dosen_id != session['user_id']:
        flash("Anda tidak memiliki akses ke bimbingan ini!", "danger")
        return redirect(url_for('dashboard'))

    bimbingan.status = 'selesai'
    db.session.commit()  # <-- Perubahan disimpan di database
    flash("Kehadiran berhasil dikonfirmasi!", "success")

    return redirect(url_for('dashboard'))


# Rute Tambah Catatan (Hanya Dosen)
@app.route('/tambah_catatan/<int:bimbingan_id>', methods=['GET', 'POST'])
def tambah_catatan(bimbingan_id):
    if 'user_id' not in session or session['role'] != 'dosen':
        return redirect(url_for('login'))

    bimbingan = Bimbingan.query.get_or_404(bimbingan_id)

    # Pastikan hanya dosen yang terkait bisa memberikan catatan
    if bimbingan.dosen_id != session['user_id']:
        flash("Anda tidak memiliki akses ke bimbingan ini!", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        catatan = request.form['catatan']
        bimbingan.catatan = catatan
        db.session.commit()
        flash("Catatan berhasil ditambahkan!", "success")
        return redirect(url_for('dashboard'))

    return render_template('tambah_catatan.html', bimbingan=bimbingan)

# Rute Tambah Bimbingan (Mahasiswa)
@app.route('/tambah_bimbingan', methods=['GET', 'POST'])
def tambah_bimbingan():
    if 'user_id' not in session or session['role'] != 'mahasiswa':
        return redirect(url_for('login'))

    if request.method == 'POST':
        dosen_id = request.form['dosen_id']
        waktu_str = request.form['waktu']
        waktu = datetime.strptime(waktu_str, '%Y-%m-%dT%H:%M')
        bimbingan = Bimbingan(mahasiswa_id=session['user_id'], dosen_id=dosen_id, waktu=waktu)
        db.session.add(bimbingan)
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    dosen_list = User.query.filter_by(role='dosen').all()
    return render_template('tambah_bimbingan.html', dosen_list=dosen_list)

# Rute Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Username tidak ditemukan!", "danger")
            return redirect(url_for('login'))

        if not check_password_hash(user.password, password):
            flash("Password salah!", "danger")
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['role'] = user.role

        if user.role == 'admin':
            return redirect(url_for('dashboard_admin'))
        return redirect(url_for('dashboard'))  # Arahkan ke dashboard mahasiswa/dosen

    return render_template('login.html')

# Rute Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Rute Dashboard (Dosen & Mahasiswa)
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session['role']

    if role == 'mahasiswa':
        bimbingan_list = Bimbingan.query.filter_by(mahasiswa_id=user_id).all()
    elif role == 'dosen':
        bimbingan_list = Bimbingan.query.filter_by(dosen_id=user_id).all()
    else:
        return redirect(url_for('dashboard_admin'))

    return render_template('dashboard.html', role=role, bimbingan_list=bimbingan_list)

# Rute Dashboard Admin
@app.route('/dashboard_admin')
def dashboard_admin():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    total_mahasiswa = User.query.filter_by(role='mahasiswa').count()
    total_dosen = User.query.filter_by(role='dosen').count()
    total_bimbingan = Bimbingan.query.count()
    bimbingan_selesai = Bimbingan.query.filter_by(status='selesai').count()
    bimbingan_menunggu = Bimbingan.query.filter_by(status='menunggu').count()
    bimbingan_diterima = Bimbingan.query.filter_by(status='diterima').count()
    
    return render_template('dashboard_admin.html', 
                           total_mahasiswa=total_mahasiswa,
                           total_dosen=total_dosen,
                           total_bimbingan=total_bimbingan,
                           bimbingan_selesai=bimbingan_selesai,
                           bimbingan_menunggu=bimbingan_menunggu,
                           bimbingan_diterima=bimbingan_diterima)

# Rute Kelola Pengguna (Admin)
@app.route('/kelola_pengguna', methods=['GET', 'POST'])
def kelola_pengguna():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Pengguna berhasil ditambahkan!", "success")
        return redirect(url_for('kelola_pengguna'))
    
    users = User.query.all()
    return render_template('kelola_pengguna.html', users=users)

@app.route('/hapus_pengguna/<int:user_id>')
def hapus_pengguna(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Pengguna berhasil dihapus!", "success")
    return redirect(url_for('kelola_pengguna'))

# Membuat database dan dummy user jika belum ada
def create_dummy_data():
    with app.app_context():
        if not os.path.exists(os.path.join(BASE_DIR, 'instance')):
            os.makedirs(os.path.join(BASE_DIR, 'instance'))
        db.create_all()
        if not User.query.first():
            admin = User(username="admin", password=generate_password_hash("admin123"), role="admin")
            dosen = User(username="dosen1", password=generate_password_hash("dosen123"), role="dosen")
            mahasiswa = User(username="student1", password=generate_password_hash("student123"), role="mahasiswa")
            db.session.add(admin)
            db.session.add(dosen)
            db.session.add(mahasiswa)
            db.session.commit()
            print("Dummy user berhasil ditambahkan!")

if __name__ == '__main__':
    create_dummy_data()
    app.run(debug=True)
