
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "PLEASE-CHANGE-THIS-SECRET-KEY")
DB = os.path.join(os.path.dirname(__file__), "site.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
    cur.execute("""CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT NOT NULL, category TEXT NOT NULL,
        location TEXT, message TEXT NOT NULL, status TEXT DEFAULT '待處理',
        created_at TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
        content TEXT NOT NULL, image_url TEXT, published_at TEXT NOT NULL
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    if not cur.execute("SELECT id FROM admin WHERE username='admin'").fetchone():
        cur.execute("INSERT INTO admin(username,password_hash) VALUES(?,?)",
                    ("admin", generate_password_hash("12345678")))
    defaults = {
        "phone":"待填入正式電話",
        "line":"待填入官方 LINE",
        "facebook":"待填入 Facebook 粉專",
        "address":"待填入服務處地址",
        "hero_title":"林捷夷",
        "hero_slogan":"青年參政・用心服務",
        "hero_text":"傾聽地方聲音，用行動服務中埔。讓每一件民眾關心的小事，都能被認真看見、積極處理。"
    }
    for k,v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    conn.commit()
    conn.close()

def settings_dict():
    conn = get_db()
    rows = conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    return {r["key"]:r["value"] for r in rows}

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    conn = get_db()
    news = conn.execute("SELECT * FROM news ORDER BY id DESC LIMIT 6").fetchall()
    conn.close()
    return render_template("index.html", news=news, settings=settings_dict())

@app.route("/submit-case", methods=["POST"])
def submit_case():
    data = {
        "name":request.form.get("name","").strip(),
        "phone":request.form.get("phone","").strip(),
        "category":request.form.get("category","").strip(),
        "location":request.form.get("location","").strip(),
        "message":request.form.get("message","").strip()
    }
    if not all([data["name"],data["phone"],data["category"],data["message"]]):
        flash("請填寫完整資料。","error")
        return redirect(url_for("index")+"#contact")
    conn=get_db()
    conn.execute("""INSERT INTO cases(name,phone,category,location,message,status,created_at)
                    VALUES(?,?,?,?,?,'待處理',?)""",
                 (data["name"],data["phone"],data["category"],data["location"],data["message"],
                  datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()
    flash("陳情資料已成功送出。","success")
    return redirect(url_for("index")+"#contact")

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        username=request.form.get("username","")
        password=request.form.get("password","")
        conn=get_db()
        admin=conn.execute("SELECT * FROM admin WHERE username=?",(username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"],password):
            session["admin_id"]=admin["id"]
            session["username"]=admin["username"]
            return redirect(url_for("admin_dashboard"))
        flash("帳號或密碼錯誤。","error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_dashboard():
    conn=get_db()
    total=conn.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
    pending=conn.execute("SELECT COUNT(*) c FROM cases WHERE status='待處理'").fetchone()["c"]
    processing=conn.execute("SELECT COUNT(*) c FROM cases WHERE status='處理中'").fetchone()["c"]
    done=conn.execute("SELECT COUNT(*) c FROM cases WHERE status='已完成'").fetchone()["c"]
    latest=conn.execute("SELECT * FROM cases ORDER BY id DESC LIMIT 8").fetchall()
    news_count=conn.execute("SELECT COUNT(*) c FROM news").fetchone()["c"]
    conn.close()
    return render_template("admin_dashboard.html",total=total,pending=pending,processing=processing,done=done,latest=latest,news_count=news_count)

@app.route("/admin/cases")
@login_required
def admin_cases():
    status=request.args.get("status","")
    conn=get_db()
    rows=conn.execute("SELECT * FROM cases WHERE status=? ORDER BY id DESC",(status,)).fetchall() if status else conn.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_cases.html",rows=rows,status=status)

@app.route("/admin/cases/<int:case_id>",methods=["GET","POST"])
@login_required
def admin_case_detail(case_id):
    conn=get_db()
    if request.method=="POST":
        status=request.form.get("status","待處理")
        conn.execute("UPDATE cases SET status=? WHERE id=?",(status,case_id))
        conn.commit()
        flash("案件狀態已更新。","success")
    case=conn.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    conn.close()
    if not case: return "Not found",404
    return render_template("admin_case_detail.html",case=case)

@app.route("/admin/news",methods=["GET","POST"])
@login_required
def admin_news():
    conn=get_db()
    if request.method=="POST":
        title=request.form.get("title","").strip()
        content=request.form.get("content","").strip()
        image_url=request.form.get("image_url","").strip()
        if title and content:
            conn.execute("INSERT INTO news(title,content,image_url,published_at) VALUES(?,?,?,?)",
                         (title,content,image_url,datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            flash("最新消息已發布。","success")
    rows=conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_news.html",rows=rows)

@app.route("/admin/news/<int:news_id>/delete",methods=["POST"])
@login_required
def delete_news(news_id):
    conn=get_db(); conn.execute("DELETE FROM news WHERE id=?",(news_id,)); conn.commit(); conn.close()
    flash("消息已刪除。","success")
    return redirect(url_for("admin_news"))

@app.route("/admin/settings",methods=["GET","POST"])
@login_required
def admin_settings():
    conn=get_db()
    if request.method=="POST":
        for k in ["phone","line","facebook","address","hero_title","hero_slogan","hero_text"]:
            v=request.form.get(k,"").strip()
            conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
        conn.commit()
        flash("網站內容已更新。","success")
    rows=conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    return render_template("admin_settings.html",settings={r["key"]:r["value"] for r in rows})

@app.route("/admin/password",methods=["GET","POST"])
@login_required
def admin_password():
    if request.method=="POST":
        old=request.form.get("old_password","")
        new=request.form.get("new_password","")
        conn=get_db()
        admin=conn.execute("SELECT * FROM admin WHERE id=?",(session["admin_id"],)).fetchone()
        if not admin or not check_password_hash(admin["password_hash"],old):
            conn.close(); flash("原密碼不正確。","error"); return redirect(url_for("admin_password"))
        if len(new)<8:
            conn.close(); flash("新密碼至少 8 碼。","error"); return redirect(url_for("admin_password"))
        conn.execute("UPDATE admin SET password_hash=? WHERE id=?",(generate_password_hash(new),session["admin_id"]))
        conn.commit(); conn.close()
        flash("密碼已更新。","success")
    return render_template("admin_password.html")

init_db()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
