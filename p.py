import streamlit as st
from PIL import Image
import qrcode
import io
from fpdf import FPDF
from datetime import datetime
import mysql.connector
import urllib.parse
import json
import os
import base64

# --- 1. INITIAL CONFIGURATION ---
st.set_page_config(
    page_title="Jay Vachraj · Digital Menu",
    page_icon="🍽️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. DATABASE CONNECTION ---
try:
    db = mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4Er7E7yAa5CmneH.root",
        password="jubMX8vnCyJqhX96",
        database="cafe",
        ssl_verify_identity=True,
        ssl_ca="/etc/ssl/certs/ca-certificates.crt"
    )
    cursor = db.cursor(dictionary=True) 
except Exception as e:
    st.error(f"Database Connection Failed: {e}")
    st.stop()

# --- 3. DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "menu_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- 4. SESSION STATE ---
if "page" not in st.session_state:
    st.session_state["page"] = "login"
if "items" not in st.session_state:
    st.session_state["items"] = []
if "email" not in st.session_state:
    st.session_state["email"] = None

# --- 5. STYLING (THE DESIGN) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Glassmorphism Card */
    .menu-card {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 15px;
        border: 1px solid rgba(255,255,255,0.3);
        margin-bottom: 20px;
        transition: transform 0.3s ease;
    }

    /* Sticky Footer Design */
    .sticky-footer {
        position: fixed;
        bottom: 20px;
        left: 5%;
        right: 5%;
        background: #1a1a1a;
        color: white;
        padding: 15px 25px;
        border-radius: 50px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        z-index: 1000;
        cursor: pointer;
    }

    .item-image {
        width: 100%;
        height: 140px;
        border-radius: 15px;
        object-fit: cover;
    }

    /* Login Box */
    .login-container {
        background: white;
        padding: 40px;
        border-radius: 30px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 6. HELPER FUNCTIONS ---
def load_image(image_path):
    if not image_path: return Image.new("RGB", (300, 300), (220, 220, 220))
    full_path = os.path.join(BASE_DIR, image_path)
    if os.path.exists(full_path):
        return Image.open(full_path)
    return Image.new("RGB", (300, 300), (220, 220, 220))

def get_order_no(email):
    today = datetime.now().date()
    cursor.execute("SELECT last_order_no FROM daily_order_counter WHERE order_date = %s AND email = %s FOR UPDATE", (today, email))
    row = cursor.fetchone()
    if row:
        new_no = row["last_order_no"] + 1
        cursor.execute("UPDATE daily_order_counter SET last_order_no = %s WHERE order_date = %s AND email = %s", (new_no, today, email))
    else:
        new_no = 1
        cursor.execute("INSERT INTO daily_order_counter (email, order_date, last_order_no) VALUES (%s, %s, %s)", (email, today, new_no))
    db.commit()
    return new_no

# --- 7. MAIN APP LOGIC ---

# PAGE: LOGIN
if st.session_state["page"] == "login":
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("Admin Access")
    company_name = st.text_input("Enter Company Name", placeholder="e.g. Jay Vachraj")
    
    if st.button("Enter Portal", use_container_width=True):
        cursor.execute("SELECT * FROM admin_requests WHERE LOWER(company_name) = LOWER(%s)", (company_name.strip(),))
        admin = cursor.fetchone()
        if admin:
            st.session_state.update({
                "email": admin["email"],
                "menu_title": admin["company_name"],
                "upi_id": admin.get("upi_id"),
                "online_payment": bool(admin.get("online_payment_enabled")),
                "page": "menu"
            })
            st.rerun()
        else:
            st.error("Admin not found. Please check the name.")
    st.markdown('</div>', unsafe_allow_html=True)

# PAGE: MENU
elif st.session_state["page"] == "menu":
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['menu_title']}</h1>", unsafe_allow_html=True)
    
    # Corrected SQL Query (Added WHERE clause)
    cursor.execute("SELECT * FROM menu_items WHERE email = %s", (st.session_state["email"],))
    menu_data = cursor.fetchall()

    search = st.text_input("🔍 Search for dishes...", label_visibility="collapsed")
    
    # Process items and variants
    display_items = []
    for item in menu_data:
        if not search or search.lower() in item['name'].lower():
            variants = json.loads(item['variants'] or '[]')
            if not variants: variants = [{"name": "Regular", "price": 0}]
            for v in variants:
                display_items.append({**item, "v_name": v['name'], "v_price": v['price'], "uid": f"{item['id']}_{v['name']}"})

    # Grid Display
    for i in range(0, len(display_items), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(display_items):
                item = display_items[i+j]
                with cols[j]:
                    st.markdown('<div class="menu-card">', unsafe_allow_html=True)
                    st.image(load_image(item['image']), use_container_width=True)
                    st.markdown(f"**{item['name']}**<br><small>{item['v_name']}</small>", unsafe_allow_html=True)
                    st.write(f"₹{item['v_price']}")
                    
                    # Quantity Logic
                    q_key = f"q
