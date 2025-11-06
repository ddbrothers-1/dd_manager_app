
import os, sqlite3, datetime, io
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'dd_secret_key'

ADMIN_DEFAULT = "DD_Brothers"
ADMIN_PASSWORD = "Ash#1Laddi"
ACTION_PASSWORD = "1322420"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "dd_manager.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS trucks (id INTEGER PRIMARY KEY AUTOINCREMENT, truck_no TEXT UNIQUE, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT, etype TEXT, truck_id INTEGER, driver_id INTEGER,
        amount REAL, date TEXT, description TEXT, hst_included INTEGER DEFAULT 0, edited INTEGER DEFAULT 0, created_at TEXT,
        FOREIGN KEY(truck_id) REFERENCES trucks(id), FOREIGN KEY(driver_id) REFERENCES drivers(id))""")
    conn.commit(); conn.close()

@app.context_processor
def inject_now():
    return dict(now=datetime.datetime.now())

def require_login():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return None

@app.route('/', methods=['GET','POST'])
def login():
    init_db()
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_DEFAULT and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        return render_template('login.html', admin_default=ADMIN_DEFAULT, error='Wrong password')
    return render_template('login.html', admin_default=ADMIN_DEFAULT)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
def home():
    redir = require_login()
    if redir: return redir
    db = get_db(); c=db.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) FROM entries WHERE kind='Income'"); inc = c.fetchone()[0] or 0.0
    c.execute("SELECT COALESCE(SUM(amount),0) FROM entries WHERE kind='Expense'"); exp = c.fetchone()[0] or 0.0
    c.execute("SELECT COUNT(*) FROM trucks WHERE active=1"); at = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM drivers WHERE active=1"); ad = c.fetchone()[0]
    db.close()
    return render_template('home.html', active='home', total_income=inc, total_expense=exp, net=inc-exp, active_trucks=at, active_drivers=ad)

@app.route('/trucks')
def trucks():
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor(); c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); rows=[dict(r) for r in c.fetchall()]; db.close()
    return render_template('trucks.html', active='trucks', trucks=rows)

@app.route('/trucks/add', methods=['POST'])
def add_truck():
    redir = require_login()
    if redir: return redir
    truck_no = request.form.get('truck_no','').strip()
    active = int(request.form.get('active','1'))
    if not truck_no.isdigit():
        db=get_db(); c=db.cursor(); c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); rows=[dict(r) for r in c.fetchall()]; db.close()
        return render_template('trucks.html', active='trucks', trucks=rows, t_error='Only numbers allowed for truck')
    try:
        db=get_db(); c=db.cursor(); c.execute('INSERT INTO trucks(truck_no,active) VALUES (?,?)',(truck_no,active)); db.commit(); db.close()
    except sqlite3.IntegrityError:
        db=get_db(); c=db.cursor(); c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); rows=[dict(r) for r in c.fetchall()]; db.close()
        return render_template('trucks.html', active='trucks', trucks=rows, t_error='Truck already in the System')
    return redirect(url_for('trucks'))

@app.route('/trucks/delete/<int:truck_id>', methods=['POST'])
def delete_truck(truck_id):
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor(); c.execute('DELETE FROM trucks WHERE id=?',(truck_id,)); db.commit(); db.close()
    return redirect(url_for('trucks'))

@app.route('/drivers')
def drivers():
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor(); c.execute('SELECT * FROM drivers ORDER BY name ASC'); rows=[dict(r) for r in c.fetchall()]; db.close()
    return render_template('drivers.html', active='drivers', drivers=rows)

@app.route('/drivers/add', methods=['POST'])
def add_driver():
    redir = require_login()
    if redir: return redir
    name = request.form.get('driver_name','').strip()
    active = int(request.form.get('active','1'))
    try:
        db=get_db(); c=db.cursor(); c.execute('INSERT INTO drivers(name,active) VALUES (?,?)',(name,active)); db.commit(); db.close()
    except sqlite3.IntegrityError:
        db=get_db(); c=db.cursor(); c.execute('SELECT * FROM drivers ORDER BY name ASC'); rows=[dict(r) for r in c.fetchall()]; db.close()
        return render_template('drivers.html', active='drivers', drivers=rows, d_error='Driver already in the System')
    return redirect(url_for('drivers'))

@app.route('/drivers/delete/<int:driver_id>', methods=['POST'])
def delete_driver(driver_id):
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor(); c.execute('DELETE FROM drivers WHERE id=?',(driver_id,)); db.commit(); db.close()
    return redirect(url_for('drivers'))

@app.route('/entries')
def entries():
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor()
    c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); trucks=[dict(r) for r in c.fetchall()]
    c.execute('SELECT * FROM drivers ORDER BY name ASC'); drivers=[dict(r) for r in c.fetchall()]
    c.execute('SELECT e.*, t.truck_no, d.name as driver_name FROM entries e LEFT JOIN trucks t ON e.truck_id=t.id LEFT JOIN drivers d ON e.driver_id=d.id ORDER BY date DESC, e.id DESC')
    rows=[dict(r) for r in c.fetchall()]; db.close()
    return render_template('entries.html', active='entries', trucks=trucks, drivers=drivers, entries=rows)

@app.route('/entries/add', methods=['POST'])
def add_entry():
    redir = require_login()
    if redir: return redir
    kind=request.form.get('kind',''); etype=request.form.get('etype',''); truck_id=request.form.get('truck_id',''); driver_id=request.form.get('driver_id','')
    amount=request.form.get('amount',''); date=request.form.get('date',''); description=request.form.get('description','')
    hst_included = 1 if request.form.get('hst_included')=='on' else 0
    if not all([kind, etype, truck_id, driver_id, amount, date, description]): return redirect(url_for('entries'))
    if kind=='Expense' and not request.form.get('hst_included'): return redirect(url_for('entries'))
    db=get_db(); c=db.cursor()
    c.execute('INSERT INTO entries(kind,etype,truck_id,driver_id,amount,date,description,hst_included,edited,created_at) VALUES (?,?,?,?,?,?,?,?,0,?)',
        (kind, etype, int(truck_id), int(driver_id), float(amount), date, description, hst_included, datetime.datetime.now().isoformat()))
    db.commit(); db.close()
    return redirect(url_for('entries'))

@app.route('/entries/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor(); c.execute('DELETE FROM entries WHERE id=?',(entry_id,)); db.commit(); db.close()
    return redirect(url_for('entries'))

@app.route('/entries/edit/<int:entry_id>', methods=['GET','POST'])
def edit_entry(entry_id):
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor()
    if request.method=='POST':
        kind=request.form.get('kind',''); etype=request.form.get('etype',''); truck_id=int(request.form.get('truck_id','')); driver_id=int(request.form.get('driver_id',''))
        amount=float(request.form.get('amount','')); date=request.form.get('date',''); description=request.form.get('description',''); hst_included=1 if request.form.get('hst_included')=='on' else 0
        c.execute('UPDATE entries SET kind=?, etype=?, truck_id=?, driver_id=?, amount=?, date=?, description=?, hst_included=?, edited=1 WHERE id=?',
            (kind, etype, truck_id, driver_id, amount, date, description, hst_included, entry_id))
        db.commit(); db.close(); return redirect(url_for('entries'))
    c.execute('SELECT * FROM entries WHERE id=?',(entry_id,)); entry=dict(c.fetchone())
    c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); trucks=[dict(r) for r in c.fetchall()]
    c.execute('SELECT * FROM drivers ORDER BY name ASC'); drivers=[dict(r) for r in c.fetchall()]; db.close()
    return render_template('edit_entry.html', active='entries', entry=entry, trucks=trucks, drivers=drivers)

@app.route('/reports')
def reports():
    redir = require_login()
    if redir: return redir
    import datetime as dt
    db=get_db(); c=db.cursor()
    c.execute('SELECT * FROM trucks ORDER BY truck_no+0 ASC'); trucks=[dict(r) for r in c.fetchall()]
    months=[(i, dt.date(1900,i,1).strftime('%B')) for i in range(1,13)]
    years=list(range(dt.date.today().year-5, dt.date.today().year+2))
    month=request.args.get('month'); year=request.args.get('year'); truck_id=request.args.get('truck_id'); action=request.args.get('action','view')
    rows=[]; no_data=False
    if month and year:
        start=f"{year}-{int(month):02d}-01"
        if int(month)==12: end=f"{int(year)+1}-01-01"
        else: end=f"{year}-{int(month)+1:02d}-01"
        if truck_id:
            c.execute('SELECT e.*, t.truck_no, d.name as driver_name FROM entries e LEFT JOIN trucks t ON e.truck_id=t.id LEFT JOIN drivers d ON e.driver_id=d.id WHERE date>=? AND date<? AND truck_id=? ORDER BY date ASC, e.id ASC', (start,end,truck_id))
        else:
            c.execute('SELECT e.*, t.truck_no, d.name as driver_name FROM entries e LEFT JOIN trucks t ON e.truck_id=t.id LEFT JOIN drivers d ON e.driver_id=d.id WHERE date>=? AND date<? ORDER BY t.truck_no+0 ASC, date ASC', (start,end))
        rows=[dict(r) for r in c.fetchall()]
        if not rows: no_data=True
        if action=='pdf':
            buf=io.BytesIO(); cn=canvas.Canvas(buf, pagesize=letter); w,h=letter
            cn.setFillColorRGB(11/255,42/255,74/255); cn.rect(0,h-70,w,70, stroke=0, fill=1)
            try:
                logo_path=os.path.join(BASE_DIR,'static','dd_logo.png')
                cn.drawImage(logo_path, 18, h-60, width=44, height=44, mask='auto')
            except Exception: pass
            cn.setFillColorRGB(1,1,1); cn.setFont('Helvetica-Bold',14); cn.drawCentredString(w/2, h-32, 'DD Brothers Transport Inc.')
            cn.setFont('Helvetica',9); cn.drawCentredString(w/2, h-48, '190 whithorn Cres, Caledonia, ON, N3W 0C9 • ddbrotherstrans@gmail.com • 437-985-0738, 437-219-0083')
            y=h-90; cn.setFillColorRGB(0,0,0); cn.setFont('Helvetica-Bold',11); 
            label = f"Truck {rows[0]['truck_no']}" if truck_id else 'All Trucks'
            cn.drawString(36,y, f'Monthly Report {year}-{int(month):02d} • {label}'); y-=14
            cn.setFont('Helvetica',9)
            for r in rows:
                if y<60:
                    cn.showPage()
                    cn.setFillColorRGB(11/255,42/255,74/255); cn.rect(0,h-70,w,70, stroke=0, fill=1)
                    try: cn.drawImage(logo_path, 18, h-60, width=44, height=44, mask='auto')
                    except Exception: pass
                    cn.setFillColorRGB(1,1,1); cn.setFont('Helvetica-Bold',14); cn.drawCentredString(w/2, h-32, 'DD Brothers Transport Inc.')
                    cn.setFont('Helvetica',9); cn.drawCentredString(w/2, h-48, '190 whithorn Cres, Caledonia, ON, N3W 0C9 • ddbrotherstrans@gmail.com • 437-985-0738, 437-219-0083')
                    y=h-90; cn.setFillColorRGB(0,0,0); cn.setFont('Helvetica',9)
                cn.drawString(36,y,f"{r.get('date','')}  T{r.get('truck_no','')}  {r.get('driver_name','')}  {r.get('kind','')}/{r.get('etype','')}  ${r.get('amount',0):.2f}"); y-=12
            cn.showPage(); cn.save(); buf.seek(0)
            return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'Monthly_{year}_{month}.pdf')
    db.close()
    return render_template('reports.html', active='reports', trucks=trucks, months=months, years=years, rows=rows, no_data=no_data)

@app.route('/driver-pay')
def driver_pay():
    redir = require_login()
    if redir: return redir
    db=get_db(); c=db.cursor()
    c.execute('SELECT * FROM drivers ORDER BY name ASC'); drivers=[dict(r) for r in c.fetchall()]
    driver_id=request.args.get('driver_id'); start=request.args.get('start'); end=request.args.get('end')
    rows=None; total=0.0
    if driver_id and start and end:
        c.execute("SELECT e.*, t.truck_no FROM entries e LEFT JOIN trucks t ON e.truck_id=t.id WHERE e.kind='Expense' AND e.etype='Driver pay' AND e.driver_id=? AND e.date>=? AND e.date<=? ORDER BY e.date ASC", (driver_id,start,end))
        rows=[dict(r) for r in c.fetchall()]; total=sum([r.get('amount',0) for r in rows])
    db.close()
    return render_template('driver_pay.html', active='driver_pay', drivers=drivers, rows=rows, total=total)

@app.route('/hst')
def hst():
    redir = require_login()
    if redir: return redir
    start=request.args.get('start'); end=request.args.get('end'); rows=[]; summary=None
    if start and end:
        db=get_db(); c=db.cursor()
        c.execute('SELECT kind, etype, amount, date, hst_included, description FROM entries WHERE date>=? AND date<=? ORDER BY date ASC', (start,end))
        rows=[dict(r) for r in c.fetchall()]
        hst_paid=sum([(r['amount']-(r['amount']/1.13)) for r in rows if r['kind']=='Expense' and r['hst_included']])
        hst_return=sum([r['amount'] for r in rows if r['kind']=='Income' and r['etype']=='HST Return'])
        summary={'hst_paid':hst_paid,'hst_return':hst_return}
        db.close()
    return render_template('hst.html', active='hst', rows=rows, summary=summary)

@app.route('/health')
def health():
    return jsonify(status='ok'), 200

with app.app_context():
    init_db()

if __name__ == '__main__':
    init_db()
    port=int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)
