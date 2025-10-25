# app.py
import streamlit as st
import sqlite3
import os
from datetime import datetime
from uuid import uuid4
from werkzeug.utils import secure_filename
import hashlib

# ---------- Konfiguratsiya ----------
APP_TITLE = "📁 File Manager — Qidiruvchi"
UPLOAD_DIR = "uploads"
DB_PATH = "files.db"

# default admin paroli (SHA256 bilan saqlangan)
# agar xohlasangiz, quyidagi admin parolini o'zgartiring (plain text) va sha256 ga aylantiring:
DEFAULT_USERNAME = "shohjahon"
DEFAULT_PASSWORD_PLAIN = "AD0352360s."  # ilovani o'rnatgandan keyin almashtiring
DEFAULT_PASSWORD_HASH = hashlib.sha256(DEFAULT_PASSWORD_PLAIN.encode()).hexdigest()

# Ruxsat etilgan typelar (faqat soddalashtirish uchun, Streamlit fayl tekshiradi)
ALLOWED_CATEGORIES = ["Files", "Audios", "Images"]

# ---------- Yordamchi funksiyalar ----------
def init_storage():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        filename TEXT,
        original_name TEXT,
        category TEXT,
        notes TEXT,
        uploaded_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT
    )
    """)
    # default user qo'shish (agar mavjud bo'lmasa)
    cur.execute("SELECT username FROM users WHERE username = ?", (DEFAULT_USERNAME,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users(username, password_hash) VALUES(?, ?)",
                    (DEFAULT_USERNAME, DEFAULT_PASSWORD_HASH))
    conn.commit()

def hash_password(password_plain):
    return hashlib.sha256(password_plain.encode()).hexdigest()

def check_login(conn, username, password_plain):
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        return False
    return row["password_hash"] == hash_password(password_plain)

def save_uploaded_file(uploaded_file, dest_dir=UPLOAD_DIR):
    # original filename
    original = uploaded_file.name
    safe = secure_filename(original)
    unique_name = f"{uuid4().hex}_{safe}"
    path = os.path.join(dest_dir, unique_name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return unique_name, original

def insert_item(conn, name, filename, original_name, category, notes):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO items(name, filename, original_name, category, notes, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, filename, original_name, category, notes, datetime.now().isoformat()))
    conn.commit()

def update_item_name(conn, item_id, new_name):
    cur = conn.cursor()
    cur.execute("UPDATE items SET name=? WHERE id=?", (new_name, item_id))
    conn.commit()

def update_item_notes(conn, item_id, new_notes):
    cur = conn.cursor()
    cur.execute("UPDATE items SET notes=? WHERE id=?", (new_notes, item_id))
    conn.commit()

def delete_item(conn, item_id):
    cur = conn.cursor()
    cur.execute("SELECT filename FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row:
        filepath = os.path.join(UPLOAD_DIR, row["filename"])
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            st.error(f"Faylni o'chirishda xatolik: {e}")
    cur.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()

def list_items(conn, category=None):
    cur = conn.cursor()
    if category:
        cur.execute("SELECT * FROM items WHERE category=? ORDER BY uploaded_at DESC", (category,))
    else:
        cur.execute("SELECT * FROM items ORDER BY uploaded_at DESC")
    return cur.fetchall()

def insert_link(conn, name, url):
    cur = conn.cursor()
    cur.execute("INSERT INTO links(name, url, created_at) VALUES (?, ?, ?)", (name, url, datetime.now().isoformat()))
    conn.commit()

def list_links(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM links ORDER BY created_at DESC")
    return cur.fetchall()

def delete_link(conn, link_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM links WHERE id=?", (link_id,))
    conn.commit()

def update_link(conn, link_id, name, url):
    cur = conn.cursor()
    cur.execute("UPDATE links SET name=?, url=? WHERE id=?", (name, url, link_id))
    conn.commit()

# ---------- Init ----------
init_storage()
conn = get_db_connection()
init_db(conn)

# ---------- Streamlit UI ----------
st.set_page_config(APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Session: autentifikatsiya
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

# Login sahifasi
if not st.session_state.logged_in:
    st.subheader("Kirish — Login talab qilinadi")
    with st.form("login_form"):
        username = st.text_input("Foydalanuvchi nomi")
        password = st.text_input("Parol", type="password")
        submitted = st.form_submit_button("Kirish")
        if submitted:
            if check_login(conn, username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Xush kelibsiz, {username}!")
                st.rerun()
            else:
                st.error("Login yoki parol noto'g'ri.")
    st.markdown("---")
    st.info("Shaxsiy fayllarga xo'jayin ruxsatisiz kirmang.")
    st.stop()

# Asosiy menyu
menu = st.sidebar.selectbox("Bo'lim tanlang", ["Dashboard", "📁 Files", "🎵 Audios", "🖼️ Images", "🔗 Links", "⚙️ Boshqaruv (Settings)"])

# Logout tugmasi
if st.sidebar.button("Chiqish (Logout)"):
    st.session_state.logged_in = False
    st.session_state.username = None
    st.rerun()

# DASHBOARD
if menu == "Dashboard":
    st.header("Dashboard")
    st.markdown("Bu yerda umumiy ma'lumotlar ko'rsatiladi.")
    total_files = len(list_items(conn))
    files_by_cat = {cat: len(list_items(conn, cat)) for cat in ALLOWED_CATEGORIES}
    st.metric("Umumiy fayllar soni", total_files)
    for cat, cnt in files_by_cat.items():
        st.write(f"- **{cat}**: {cnt}")

    st.markdown("### Oxirgi qo'shilganlar")
    rows = list_items(conn)[:10]
    for r in rows:
        st.write(f"{r['uploaded_at'][:19]} — **{r['name']}** ({r['category']}) — original: {r['original_name']}")

# FILES / AUDIOS / IMAGES pages are similar
def show_category_page(category_name):
    st.header(f"{category_name} bo'limi")
    st.markdown("### Yangi fayl yuklash")
    with st.form(f"upload_form_{category_name}"):
        uploaded = st.file_uploader("Fayl tanlang", type=None)  # barcha turlar
        display_name = st.text_input("Faylga ko'rsatiladigan nom (ixtiyoriy)")
        notes = st.text_area("Izoh (ixtiyoriy)")
        submit = st.form_submit_button("Yuklash")
        if submit:
            if uploaded is None:
                st.error("Iltimos, fayl tanlang.")
            else:
                saved_filename, original = save_uploaded_file(uploaded)
                name_to_save = display_name.strip() if display_name.strip() else original
                insert_item(conn, name_to_save, saved_filename, original, category_name, notes)
                st.success(f"Fayl yuklandi: {name_to_save}")

    st.markdown("### Mavjud fayllar")
    df_rows = list_items(conn, category_name)
    if not df_rows:
        st.info("Hozircha fayl yo'q.")
    else:
        for row in df_rows:
            col1, col2, col3 = st.columns([3,1,2])
            with col1:
                st.write(f"**{row['name']}**")
                st.write(f"_Original_: {row['original_name']}")
                if row['notes']:
                    st.write(f"_Izoh_: {row['notes']}")
                st.write(f"_Yuklangan_: {row['uploaded_at'][:19]}")
            with col2:
                file_path = os.path.join(UPLOAD_DIR, row['filename'])
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    st.download_button("Yuklab olish", data=data, file_name=row['original_name'])
                except Exception as e:
                    st.error("Fayl topilmadi yoki ochib bo'lmadi.")
            with col3:
                # Rename
                new_name = st.text_input(f"Nomni o'zgartirish ({row['id']})", value=row['name'], key=f"rename_{row['id']}")
                if st.button("Saqlash", key=f"save_name_{row['id']}"):
                    update_item_name(conn, row['id'], new_name)
                    st.success("Nom yangilandi")
                    st.rerun()
                # Notes
                new_notes = st.text_area(f"Izoh ({row['id']})", value=row['notes'] if row['notes'] else "", key=f"notes_{row['id']}")
                if st.button("Izohni saqlash", key=f"save_notes_{row['id']}"):
                    update_item_notes(conn, row['id'], new_notes)
                    st.success("Izoh saqlandi")
                    st.rerun()
                # Delete
                if st.button("O'chirish", key=f"delete_{row['id']}"):
                    delete_item(conn, row['id'])
                    st.success("Fayl o'chirildi")
                    st.rerun()
            st.markdown("---")

# Links page
def show_links_page():
    st.header("🔗 Maxsus havolalar")
    st.markdown("### Yangi havola qo'shish")
    with st.form("add_link"):
        link_name = st.text_input("Havola nomi")
        link_url = st.text_input("Havola URL (https://...)")
        submit = st.form_submit_button("Qo'shish")
        if submit:
            if not link_name or not link_url:
                st.error("Iltimos, nom va URL kiriting.")
            else:
                insert_link(conn, link_name, link_url)
                st.success("Havola qo'shildi")
                st.rerun()

    st.markdown("### Mavjud havolalar")
    rows = list_links(conn)
    if not rows:
        st.info("Hozircha havola yo'q.")
    else:
        for r in rows:
            col1, col2 = st.columns([4,1])
            with col1:
                st.write(f"**{r['name']}** — {r['url']}")
                st.write(f"_Qo'shilgan_: {r['created_at'][:19]}")
            with col2:
                if st.button("Ochish", key=f"open_{r['id']}"):
                    st.write(f"[Ochish]({r['url']})")
                if st.button("Tahrirlash", key=f"edit_{r['id']}"):
                    # simple edit modal
                    new_name = st.text_input("Yangi nom", value=r['name'], key=f"editname_{r['id']}")
                    new_url = st.text_input("Yangi url", value=r['url'], key=f"editurl_{r['id']}")
                    if st.button("Saqlash o'zgarish", key=f"saveedit_{r['id']}"):
                        update_link(conn, r['id'], new_name, new_url)
                        st.success("O'zgardi")
                        st.rerun()
                if st.button("O'chirish", key=f"dellink_{r['id']}"):
                    delete_link(conn, r['id'])
                    st.success("Havola o'chirildi")
                    st.rerun()
            st.markdown("---")

# Settings page
def show_settings():
    st.header("⚙️ Boshqaruv")
    st.markdown("Parolni o'zgartirish yoki yangi foydalanuvchi qo'shish.")
    with st.form("add_user"):
        new_user = st.text_input("Foydalanuvchi nomi")
        new_pass = st.text_input("Parol", type="password")
        submit = st.form_submit_button("Foydalanuvchi qo'shish")
        if submit:
            if not new_user or not new_pass:
                st.error("Iltimos, foydalanuvchi va parol kiriting.")
            else:
                cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO users(username, password_hash) VALUES(?, ?)", (new_user, hash_password(new_pass)))
                    conn.commit()
                    st.success("Foydalanuvchi qo'shildi")
                except sqlite3.IntegrityError:
                    st.error("Bunday foydalanuvchi mavjud.")

    st.markdown("### Parolni o'zgartirish (mavjud foydalanuvchi uchun)")
    with st.form("chg_pass"):
        uname = st.text_input("Foydalanuvchi nomi (parolni o'zgartirmoqchi bo'lgan)")
        newp = st.text_input("Yangi parol", type="password")
        submit2 = st.form_submit_button("O'zgartirish")
        if submit2:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (uname,))
            if cur.fetchone() is None:
                st.error("Bunday foydalanuvchi topilmadi.")
            else:
                cur.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_password(newp), uname))
                conn.commit()
                st.success("Parol yangilandi.")

# Page routing
if menu == "📁 Files":
    show_category_page("Files")
elif menu == "🎵 Audios":
    show_category_page("Audios")
elif menu == "🖼️ Images":
    show_category_page("Images")
elif menu == "🔗 Links":
    show_links_page()
elif menu == "⚙️ Boshqaruv (Settings)":
    show_settings()
