import streamlit as st
import os
from fpdf import FPDF
import pyrebase
import json
from io import BytesIO
from PIL import Image
import mysql.connector
import firebase_admin

from firebase_admin import credentials
from firebase_admin import auth

import pandas as pd
import matplotlib.pyplot as plt

from streamlit_autorefresh import st_autorefresh
from streamlit_option_menu import option_menu

import base64

# Custom CSS to match your HTML theme for edit company
st.markdown("""
<style>
    /* Container that allows side-by-side placement */
    .horizontal-wrapper {
        display: flex;
        gap: 20px;
        align-items: stretch;
        width: 100%;
    }

    .custom-table-container {
        width: 100%;
        border-radius: 12px;
        overflow-x: auto; /* CRITICAL: Allows table to scroll if column is narrow */
        border: 1px solid #eef2f6;
        background: white;
    }

    .styled-table {
        width: 100%;
        min-width: 400px; /* Ensures table doesn't collapse too much */
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
    }

    .styled-table thead tr {
        background-color: #f8fafc;
        color: #4361ee;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid #eef2f6;
    }

    .styled-table th, .styled-table td {
        padding: 12px 15px; /* Slightly tighter padding for horizontal fit */
        font-size: 13px;
        color: #2d3748;
        white-space: nowrap; /* Prevents text wrapping in tight columns */
    }

    .styled-table tbody tr {
        border-bottom: 1px solid #f1f5f9;
        transition: background 0.2s;
    }

    .styled-table tbody tr:hover {
        background-color: #f1f3f9;
    }

    .status-pill {
        padding: 3px 10px;
        border-radius: 50px;
        font-size: 11px;
        font-weight: 500;
    }
    .status-active { background: #e0fcf0; color: #2ecc71; }
    .status-alert { background: #fff0f3; color: #f72585; }
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Cafe Admin", layout="wide", initial_sidebar_state="expanded")

if not firebase_admin._apps: 
 cred = credentials.Certificate('billing-bv-13b1fe4ec85f.json')
 firebase_admin.initialize_app(cred)
 

db = mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4Er7E7yAa5CmneH.root",
        password="JubMX8vnCyJqhX96",
        database="cafe",
        ssl_verify_identity=True,
        ssl_ca="/etc/ssl/certs/ca-certificates.crt"
)

db = get_db_connection() 
cursor = db.cursor(dictionary=True)

def add_bill_page(pdf, order_id):
    cursor.execute("""
        SELECT customer_name, customer_address, order_time, payment_method, display_order_id
        FROM orders
        WHERE id = %s AND email = %s
    """, (order_id, st.session_state["email"]))
    order = cursor.fetchone()
    if not order:
        return

    customer_name = order.get("customer_name", "Guest")
    customer_address = order.get("customer_address", "")
    bill_datetime = order["order_time"].strftime("%d-%m-%Y %I:%M %p")
    payment_method = (order.get("payment_method") or "OFFLINE").upper()
    payment_text = "ONLINE PAYMENT" if payment_method == "ONLINE" else "CASH / OFFLINE"

    pdf.add_page()
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, st.session_state.menu_title, ln=True, align="C")

    pdf.ln(3)
    pdf.set_font("Arial", size=11)
    address = st.session_state.get("company_address", "Company Address Not Set")
    pdf.multi_cell(0, 7, address, align="C")
    pdf.ln(2) 

    if st.session_state.get("gst_number"):
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, f"GST No: {st.session_state.gst_number}", ln=True, align="C")

    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "-" * 40, ln=True)

    pdf.cell(0, 8, f"Order ID : {order['display_order_id']}", ln=True)
    pdf.cell(0, 8, f"Customer Name : {customer_name}", ln=True)
    pdf.multi_cell(0, 8, f"Address : {customer_address}")
    pdf.set_font("Arial", "B", 11)
    if pdf.get_y() > 250:
        pdf.add_page()
    
    pdf.ln(2)
    pdf.cell(0, 8, f"Date & Time : {bill_datetime}", ln=True)
    pdf.set_font("Arial", size=12)

    pdf.ln(3)
    pdf.cell(0, 8, "-" * 40, ln=True)

    cursor.execute("""
        SELECT
            m.name,
            oi.variant_name,
            oi.variant_price,
            oi.quantity
        FROM order_items oi
        JOIN menu_items m ON oi.menu_id = m.id
        WHERE oi.order_id = %s
    """, (order_id,))
    items = cursor.fetchall()

    total = 0
    for i in items:
        variant = i["variant_name"] if i["variant_name"] else "Regular"
        subtotal = i["variant_price"] * i["quantity"]
        total += subtotal

        pdf.cell(
            0, 8,
            f"{i['name']} ({variant}) × {i['quantity']} = Rs.{subtotal}",
            ln=True
        )

    pdf.ln(4)
    pdf.cell(0, 8, "-" * 40, ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total : Rs.{total}", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, f"Payment Method : {payment_text}", ln=True)

def generate_all_bills_pdf(status="COMPLETED"):
    cursor.execute("""
        SELECT id
        FROM orders
        WHERE status = %s
          AND email = %s
        ORDER BY order_time ASC
    """, (status, st.session_state["email"]))

    orders = cursor.fetchall()

    if not orders:
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for o in orders:
        add_bill_page(pdf, o["id"])

    file_path = f"all_{status.lower()}_bills.pdf"
    pdf.output(file_path)

    return file_path

def generate_bill_pdf(order_id):
    cursor.execute("""
        SELECT customer_name, customer_address, order_time, payment_method, display_order_id
        FROM orders
        WHERE id = %s AND email = %s
    """, (order_id, st.session_state["email"]))
    order = cursor.fetchone()

    customer_name = order.get("customer_name", "Guest")
    customer_address = order.get("customer_address", "")
    bill_datetime = order["order_time"].strftime("%d-%m-%Y %I:%M %p")
    payment_method = (order.get("payment_method") or "OFFLINE").upper()
    payment_text = "ONLINE PAYMENT" if payment_method == "ONLINE" else "CASH / OFFLINE"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, st.session_state.menu_title, ln=True, align="C")
    
    pdf.ln(3)
    
    # Company Address
    pdf.set_font("Arial", size=11)
    address = st.session_state.get("company_address", "Company Address Not Set")
    pdf.multi_cell(0, 7, address, align="C")

    
    # GST Number
    if st.session_state.get("gst_number"):
        pdf.ln(1)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, f"GST No: {st.session_state.gst_number}", ln=True, align="C")

    # ✅ Mobile Number
    if st.session_state.get("company_phone"):
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, f"Phone: {st.session_state.company_phone}", ln=True, align="C")

    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "-" * 40, ln=True)

    pdf.cell(0, 8, f"Order ID : {order['display_order_id']}", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, f"Customer Name : {customer_name}", ln=True)
    pdf.multi_cell(0, 8, f"Address : {customer_address}")

    pdf.ln(2)
    pdf.cell(0, 8, f"Date & Time : {bill_datetime}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "-" * 40, ln=True)

    cursor.execute("""
                SELECT
            m.name,
            oi.variant_name,
            oi.variant_price,
            oi.quantity
        FROM order_items oi
        JOIN menu_items m ON oi.menu_id = m.id
        WHERE oi.order_id = %s
    """, (order_id,))
    items = cursor.fetchall()

    total = 0
    for i in items:
        subtotal = i["variant_price"] * i["quantity"]
        total += subtotal
        
        pdf.cell(
            0, 8,
            f"{i['name']} ({i['variant_name']}) × {i['quantity']} = Rs.{subtotal}",
            ln=True
        )

    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "-" * 40, ln=True)

    pdf.ln(3)
    pdf.cell(0, 10, f"Total : Rs.{total}", ln=True)

    pdf.ln(3)
    pdf.cell(0, 8, f"Payment Method : {payment_text}", ln=True)

    file_path = f"bill_{order['display_order_id']}_{st.session_state['email']}.pdf"
    pdf.output(file_path)
    return file_path


if "menu_title" not in st.session_state:
    st.session_state["menu_title"] = "THE TOGADIYA CAFE"  # default title

if "company_loaded" not in st.session_state:
    st.session_state.company_loaded = False


if "email" not in st.session_state:
    st.session_state["email"] = ""

if "company_phone" not in st.session_state:
    st.session_state.company_phone = ""

if "page" not in st.session_state:
   st.session_state["page"]="Login"

if "bill_order_id" not in st.session_state:
    st.session_state["bill_order_id"] = None


# ✅ Only load from DB if not already in session state
# ✅ CORRECT
if not st.session_state.company_loaded and st.session_state.get("email"):
    cursor.execute("""
        SELECT company_name, mobile, company_address, gst_number, upi_qr_image, upi_id, total_tables, online_payment_enabled
        FROM admin_requests
        WHERE email = %s
    """, (st.session_state["email"],))
    row = cursor.fetchone()

    if row:
        st.session_state.menu_title = row.get("company_name", "THE TOGADIYA CAFE")
        st.session_state.company_address = row.get("company_address", "")
        st.session_state.gst_number = row.get("gst_number", "")
        st.session_state.company_phone = row.get("mobile", "")
        st.session_state.upi_qr_image = row.get("upi_qr_image", "")
        st.session_state.upi_id = row.get("upi_id", "")
        st.session_state.total_tables = row.get("total_tables", 0)
        st.session_state.online_payment_enabled = bool(
            row.get("online_payment_enabled", 1)
        )

    st.session_state.company_loaded = True
    if "online_payment_enabled" not in st.session_state:
        st.session_state.online_payment_enabled = True



# 🔴 HANDLE CLEAR ORDERS ACTION (COMMON)
if "clear_status" in st.session_state:
    status = st.session_state.clear_status

    cursor.execute("""
        DELETE FROM order_items
        WHERE order_id IN (
            SELECT id FROM orders
            WHERE status = %s AND email = %s
        )
    """, (status, st.session_state["email"]))
    
    cursor.execute("""
        DELETE FROM orders
        WHERE status = %s AND email = %s
    """, (status, st.session_state["email"]))


    db.commit()
    del st.session_state.clear_status
    st.success(f"✅ {status} orders cleared successfully")
    st.rerun()


firebase_config = {
    "apiKey": "AIzaSyA7TNHcrUDmcGrDIqr2jaHpcVvKirC98Kw",
    "authDomain": "billing-bv.firebaseapp.com",
    "databaseURL": "",
    "storageBucket": "billing-bv.firebasestorage.app",
    "messagingSenderId": "724619916194",
    "appId": "1:724619916194:web:7106554e928562c70838fb",
}

firebase = pyrebase.initialize_app(firebase_config)
auth_fb = firebase.auth()

def check_admin_status(email):
    cursor.execute(
        "SELECT status FROM admin_requests WHERE email=%s",
        (email,)
    )
    row = cursor.fetchone()
    return row["status"] if row else None

def login(email, password):
    if not email.strip() or not password.strip():
        st.error("❌ Please enter both email and password")
        return

    # 🔹 Firebase authentication
    try:
        auth_fb.sign_in_with_email_and_password(email, password)
    except Exception as e:
        error_str = str(e)
        if "EMAIL_NOT_FOUND" in error_str:
            st.error("❌ Email not registered")
        elif "INVALID_PASSWORD" in error_str:
            st.error("❌ Wrong password")
        else:
            st.error("❌ Login failed")
        return

    # 🔹 STRICT MySQL status check
    cursor.execute(
        "SELECT status FROM admin_requests WHERE email=%s",
        (email,)
    )
    row = cursor.fetchone()

    if not row:
        st.error("❌ Account not found. Contact Office.")
        return

    status = row["status"]

    if status == "Pending":
        st.warning("⏳ Your account is pending Office approval.")
        return

    if status == "Paused":
        st.error("⏸ Your account is paused by Office.")
        return

    if status in ["Rejected", "Cancelled"]:
        st.error("🚫 Your membership has been cancelled.")
        return

    # ✅ ONLY APPROVED USERS REACH HERE
    st.session_state["email"] = email
    st.session_state["page"] = "Admin"
    st.session_state.company_loaded = False  # force reload company data

    try:
        cursor.execute(
            "UPDATE admin_requests SET last_login=NOW() WHERE email=%s",
            (email,)
        )
        db.commit()
    except:
        pass

    st.success("✅ Login successful")
    # ✅ mark user as authenticated
    st.session_state["authenticated"] = True
    
    # go to admin page
    st.session_state["email"] = email
    st.session_state["page"] = "Admin"
    st.session_state.company_loaded = False
    
    st.rerun()


   
def toggle_item(item_id):
    cursor.execute("""
        UPDATE menu_items
        SET available = NOT available
        WHERE id=%s AND email=%s
    """, (item_id, st.session_state["email"]))
    db.commit()
    st.rerun()


def delete_item(item_id):
    cursor.execute("""
        UPDATE menu_items
        SET is_active = 0, available = 0
        WHERE id=%s AND email=%s
    """, (item_id, st.session_state["email"]))
    db.commit()
    st.rerun()


# ==========================
# 🔐 LOGIN PAGE LOGIC
# ==========================
if st.session_state["page"] == "Login":
    
    def get_base64(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    # Load your image
    try:
        img_base64 = get_base64("2.jpg")
    except FileNotFoundError:
        img_base64 = "" # Fallback

    # Correctly escaping braces for f-string compatibility
    st.markdown(f"""
    <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/jpeg;base64,{img_base64}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        .background-blobs {{
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            z-index: -1;
            overflow: hidden;
        }}

        .blob {{
            position: absolute;
            background: rgba(124, 58, 237, 0.15);
            filter: blur(80px);
            border-radius: 50%;
            z-index: -1;
            animation: move 20s infinite alternate ease-in-out;
        }}

        .blob-1 {{ width: 400px; height: 400px; top: -100px; left: -100px; background: rgba(124, 58, 237, 0.2); }}
        .blob-2 {{ width: 300px; height: 300px; bottom: 10%; right: 10%; background: rgba(59, 130, 246, 0.15); animation-duration: 25s; }}
        .blob-3 {{ width: 200px; height: 200px; top: 40%; left: 30%; background: rgba(139, 92, 246, 0.10); animation-duration: 30s; }}
    
    
        /******** BLUE PRIMARY BUTTONS ********/
        div.stButton > button:not([data-testid="baseButton-forgot_btn"]) {{
            background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 10px 20px !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
        }}
        
        div.stButton > button:not([data-testid="baseButton-forgot_btn"]):hover {{
            background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
            transform: scale(1.03);
            box-shadow: 0 0 20px rgba(59,130,246,0.6);
        }}
        
        /******** FORGOT PASSWORD TEXT BUTTON ********/
        button[data-testid="baseButton-forgot_btn"] {{
            background: none !important;
            color: white !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
            font-size: 14px !important;
        }}
        
        button[data-testid="baseButton-forgot_btn"]:hover {{
            text-decoration: underline;
            color: #60a5fa !important;
            background: none !important;
        }}

        
        @keyframes move {{
            from {{ transform: translate(0, 0) scale(1); }}
            to {{ transform: translate(50px, 100px) scale(1.1); }}
        }}

        /* Target Streamlit's container to apply Glassmorphism */
        [data-testid="stVerticalBlock"] > div:has(.login-card-trigger) {{
            background: rgba(30, 41, 59, 0.4);
            padding: 40px;
            border-radius: 28px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
        }}

        .stTextInput label, .stTabs [data-baseweb="tab"] {{
            color: white !important;
        }}
    </style>
    
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
        <div class="blob blob-3"></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="background:#7c3aed; width:60px; height:60px; border-radius:15px; display:flex; align-items:center; justify-content:center; margin-bottom:20px;">
                <span style="font-size:30px;">☕</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown('<h1 style="color:#7c3aed; margin:0; font-size:60px; font-weight:800;">THE TOGADIYA CAFE</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color:#94a3b8; letter-spacing:2px; font-size:21px; margin-bottom:30px;">ADMIN PORTAL</p>', unsafe_allow_html=True)
        st.markdown('<h1 style="color: white; font-size:48px; font-weight:800; line-height:1.1;">Elevate Your Cafe<br>Management<br>Experience</h1>', unsafe_allow_html=True)
        st.markdown("<p style='color:#94a3b8; font-size:18px;'>Access your comprehensive dashboard to manage menus, track orders, monitor inventory, analyze sales performance, and streamline your cafe operations from anywhere</p>", unsafe_allow_html=True)

    with col2:
        # Invisible marker to trigger the CSS selector above
        st.markdown('<h2 style="color:white; text-align:center;">Secure Access</h2>', unsafe_allow_html=True)
        st.markdown('<div class="custom-alert" style="background: rgba(234, 179, 8, 0.1); color: #fbbf24; padding: 10px; border-radius: 10px; border: 1px solid rgba(251, 191, 36, 0.3); text-align: center; margin-bottom: 20px;">🛡️ TO OPEN PORTAL, LOGIN FIRST!</div>', unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
        # ... (rest of your login/signup logic)
    
        # -------------------- LOGIN TAB --------------------
        with tab_login:
            email = st.text_input('Email Address', key="login_email")
            password = st.text_input('Password', type='password', key="login_pass")
        
            if st.button("➜ Login to Dashboard", use_container_width=True):
                if email.strip() == "" or password.strip() == "":
                    st.error("❌ Please enter email and password")
                else:
                    try:
                        # Call your login function
                        user = login(email, password)  # assume it returns user info or raises
                        if not user:
                            st.error("❌ Email not found. Please sign up first.")
                        else:
                            st.session_state["page"] = "admin"
                            st.success("✅ Login successful!")
                            st.rerun()
                    except Exception as e:
                        # Check for Firebase-specific errors
                        err_msg = str(e).lower()
                        if "user not found" in err_msg:
                            st.error("❌ Email not found. Please sign up first.")
                        elif "wrong password" in err_msg:
                            st.error("❌ Incorrect password. Try again.")
                        else:
                            st.error(f"❌ {str(e)}")

                        
            forgot = st.markdown(
                """
                <div style="text-align:right;">
                    <a href="#" id="forgot_link" style="color:white; text-decoration:none; font-size:14px;">
                        Forgot Password?
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )
           
            col_f1, col_f2 = st.columns([3,1])
            
            if forgot:
                if email.strip() == "":
                    st.error("❌ Enter your email to reset password")
                else:
                    try:
                        auth_fb.send_password_reset_email(email)
                        st.success("✅ Password reset link sent!")
                        st.info("Check Spam folder also.")
                    except Exception as e:
                        st.error(f"❌ {str(e)}")


        # -------------------- SIGNUP TAB --------------------
        with tab_signup:
            mail = st.text_input('Enter Email', key="signup_email")
            password = st.text_input('Create Password', type='password', key="signup_pass")
            repassword = st.text_input('Re-enter Password', type='password', key="signup_repass")

            if st.button("✨ Create Account", use_container_width=True):

                if password != repassword:
                    st.error("❌ Password not match")

                elif mail.strip() == "" or password.strip() == "":
                    st.error("❌ All fields required")

                else:
                    try:
                        # Create Firebase user
                        user = auth.create_user(email=mail, password=password)

                        # Insert into MySQL
                        cursor.execute("""
                            INSERT IGNORE INTO admin_requests 
                            (name, email, firebase_uid, status)
                            VALUES (%s, %s, %s, 'Pending')
                        """, (mail.split("@")[0], mail, user.uid))

                        db.commit()

                        st.success("✅ Account created successfully!")
                        st.info("Waiting for Office approval.")

                        # Go back to login tab
                        st.session_state["page"] = "Login"
                        st.rerun()

                    except Exception as e:
                        st.error(str(e))

 
# ==========================
# 🎨 MODERN SIDEBAR THEME & LOGIC
# ==========================
if st.session_state["page"] == "Admin":
    # 1. Access & Security Check
    if not st.session_state.get("authenticated") or not st.session_state.get("email"):
        st.session_state.clear()
        st.session_state["page"] = "Login"
        st.rerun()

    # 2. Sidebar CSS Styling (Matching Jay Vachraj Theme)
    st.markdown("""
    <style>
        /* Sidebar Container */
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 2px solid #e9ecef !important;
            width: 300px !important;
        }

        /* User Profile Card */
        .user-profile-card {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 16px;
            padding: 15px;
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        }

        .avatar-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #4361ee, #7209b7);
            color: white;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
            margin-right: 12px;
            flex-shrink: 0;
        }

        .user-info-text h1 {
            font-size: 16px !important;
            font-weight: 700 !important;
            color: #212529 !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.2 !important;
        }

        .user-info-text p {
            font-size: 12px !important;
            color: #6c757d !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* System Info Box (Bottom) */
        .system-info-box {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-left: 4px solid #4361ee;
            border-radius: 12px;
            padding: 15px;
            margin-top: 30px;
        }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # 3. Dynamic Profile Card
        display_name = st.session_state.get("menu_title", "Jay Vachraj")
        initials = "".join([n[0] for n in display_name.split()[:2]]).upper()
        
        st.markdown(f"""
        <style>
            /* 1. The Main Outer Box */
            .user-profile-card {{
                background: #f8f9fa;
                border: 2px solid #e9ecef;
                border-radius: 20px;
                padding: 25px 20px;         /* Increased padding makes the box bigger */
                display: flex;
                flex-direction: column;    /* Stack icon and text vertically */
                align-items: center;       /* Center everything */
                justify-content: center;
                margin-bottom: 30px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
                text-align: center;
            }}
        
            /* 2. The Big Logo/Icon Circle */
            .avatar-icon {{
                width: 90px;               /* Set size of logo circle here */
                height: 90px;              /* Set size of logo circle here */
                background: linear-gradient(135deg, #4361ee, #7209b7);
                color: white;
                border-radius: 22px;       /* Slightly rounded corners */
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                font-size: 32px;           /* Size of initials inside logo */
                margin-bottom: 15px;       /* Space below logo */
                box-shadow: 0 8px 16px rgba(67, 97, 238, 0.2);
            }}
        
            /* 3. The Company Name Text */
            .user-name-title {{
                font-size: 24px !important; /* Set Company Name size here */
                font-weight: 800 !important;
                color: #1e293b !important;
                margin: 0 !important;
                line-height: 1.1 !important;
                font-family: 'Poppins', sans-serif;
            }}
        
            .system-subtitle {{
                font-size: 14px !important;
                color: #64748b !important;
                margin-top: 8px !important;
            }}
        </style>
        
        <div class="user-profile-card">
            <div class="avatar-icon">{initials}</div>
            <div class="user-text-info">
                <div class="user-name-title">{display_name}</div>
                <div class="system-subtitle">Cafe Management System</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 4. Navigation Menu (Workfull logic)
        # 1. Define your base options that always appear
        options = ["Dashboard", "Add Items", "Manage Menu", "Orders", "Edit Company", "Inventory / Sales"]
        icons = ["grid-fill", "plus-circle", "egg-fried", "receipt", "building", "graph-up-arrow"]
        
        email = st.session_state.get("email")
        
        # Execute query FIRST
        cursor.execute(
            "SELECT total_tables FROM admin_requests WHERE email=%s",
            (email,)
        )
        
        result = cursor.fetchone()
        
        if result and result['total_tables'] > 0:
            options.append("Tables")
            icons.append("table")   # because you used alias
        else:
            table_count = 0
        
        # Add Help & Support at bottom
        options.append("Help & Support")
        icons.append("headset")

        
        # 4. Render the Sidebar Menu
        selected = option_menu(
            menu_title=None,
            options=options,
            icons=icons,
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#6c757d", "font-size": "18px"}, 
                "nav-link": {
                    "font-size": "15px", 
                    "text-align": "left", 
                    "margin":"5px", 
                    "padding": "12px",
                    "border-radius": "10px",
                    "color": "#212529",
                    "font-weight": "500",
                    "--hover-color": "#d7dff8"
                },
                "nav-link-selected": {
                    "background": "linear-gradient(135deg, #4361ee 0%, #7209b7 100%)",
                    "color": "white",
                    "box-shadow": "0 4px 12px rgba(67, 97, 238, 0.3)"
                },
            }
        )
        # 5. System Footer
        st.markdown("""
        <div class="system-info-box">
            <p style="font-weight: 600; font-size: 13px; color: #212529; margin-bottom: 5px;">System Information</p>
            <p style="font-size: 11px; margin: 0;">HD Billing System v2.5.1</p>
            <p style="font-size: 11px; margin: 0;">Status: Stable</p>
        </div>
        """, unsafe_allow_html=True)

    # ==========================
    # 🏛️ TOP HEADER & LOGOUT
    # ==========================
    h_col1, h_col2 = st.columns([5, 1])
    with h_col1:
        st.markdown(f"## {selected}")
    with h_col2:
        if st.button("🚪 Log Out", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.session_state["page"] = "Login"
            st.rerun()
    
    st.divider()

    # ==========================
    # 🏠 DASHBOARD (New Home)
    # ==========================
    if selected == "Dashboard":
        st.title("📊 Dashboard")
        st.markdown("Overview of your cafe performance today.")
        
        # Fetch Data
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) AS completed_count,
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending_count,
                SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END) AS cancelled_count
            FROM orders WHERE email = %s
        """, (st.session_state["email"],))
        counts = cursor.fetchone()

        # --- CUSTOM COLORFUL METRIC CARDS ---
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="css-card" style="text-align: center; border-bottom: 4px solid #4CAF50;">
                <h3 style="margin:0; color:#4CAF50; font-size: 32px;">{counts['completed_count'] or 0}</h3>
                <p style="color:#666; font-weight: 600;">✅ Completed Orders</p>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="css-card" style="text-align: center; border-bottom: 4px solid #ff9800;">
                <h3 style="margin:0; color:#ff9800; font-size: 32px;">{counts['pending_count'] or 0}</h3>
                <p style="color:#666; font-weight: 600;">⏳ Pending Orders</p>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="css-card" style="text-align: center; border-bottom: 4px solid #f44336;">
                <h3 style="margin:0; color:#f44336; font-size: 32px;">{counts['cancelled_count'] or 0}</h3>
                <p style="color:#666; font-weight: 600;">❌ Cancelled Orders</p>
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        st.info("👈 Select an option from the sidebar to manage your cafe.")

    elif selected == "Add Items":
        st.title("🍔 Add Items")
        with st.container(border=True):
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.subheader("➕ Add New Menu Item")
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Item Name", key="add_item_name")
                type_count = st.number_input("How many variants?", min_value=0, max_value=10, step=1, key="add_variant_count")
                variant_data = []
        
                if type_count > 0:
                    st.markdown("### 🔹 Enter Variant Names & Prices")
                    for i in range(int(type_count)):
                        v_col1, v_col2 = st.columns(2)
                        with v_col1:
                            v_name = st.text_input(f"Variant {i+1} Name", key=f"vname_{i}")
                        with v_col2:
                            v_price = st.number_input(f"Price for {i+1}", min_value=0, key=f"vprice_{i}")
                        variant_data.append({"name": v_name, "price": v_price})
    
            with col2:
                image = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"], key="add_item_image")
                available = st.checkbox("Available", value=True, key="add_item_available")
    
            if st.button("Add Item", key="add_item_btn"):
                # --- VALIDATION LOGIC START ---
                if not name.strip():
                    st.error("Please fill the data: **Item Name** is required.")
                elif type_count > 0 and any(not v["name"].strip() for v in variant_data):
                    st.error("Please fill the data: One or more **Variant Names** are empty.")
                elif type_count > 0 and any(v["price"] <= 0 for v in variant_data):
                    st.error("Please fill the data: All **Variant Prices** must be greater than 0.")
                elif type_count == 0:
                     st.error("Please fill the data: You must have at least **1 variant** (or a base price).")
                # --- VALIDATION LOGIC END ---
                
                else:
                    # Proceed with saving if validation passes
                    image_path = None
                    if image:
                        os.makedirs("menu_images", exist_ok=True)
                        image_path = os.path.join("menu_images", image.name)
                        with open(image_path, "wb") as f:
                            f.write(image.getbuffer())
            
                    variants_json = json.dumps(variant_data) if variant_data else None
                    base_price = min([v["price"] for v in variant_data]) if variant_data else 0
            
                    cursor.execute("""
                        INSERT INTO menu_items 
                        (name, price, image, available, is_active, email, variants) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        name, base_price, image_path, available, 1, 
                        st.session_state["email"], variants_json
                    ))
                    db.commit()
                    st.success("✅ Item added successfully!")
                    st.rerun()
    
            st.markdown('</div>', unsafe_allow_html=True)

 
    elif selected == "Manage Menu":
            
            st.title("✏️ Manage Menu")
            # ----------------------
            # MENU SUMMARY
            # ----------------------
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_items,
                    SUM(CASE WHEN available=1 THEN 1 ELSE 0 END) AS available_items,
                    SUM(CASE WHEN available=0 THEN 1 ELSE 0 END) AS disabled_items
                FROM menu_items
                WHERE is_active=1 AND email=%s
            """, (st.session_state["email"],))
        
            menu_counts = cursor.fetchone()
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 Total Items", menu_counts["total_items"] or 0)
            col2.metric("🟢 Available", menu_counts["available_items"] or 0)
            col3.metric("🔴 Disabled", menu_counts["disabled_items"] or 0)
        
            st.divider()
            
            def display_menu_items(menu_items, tab_name):
                final_image_path = None
                if not menu_items:
                    st.info("No menu items found.")
            
                # ----------------------
                # DISPLAY MENU ITEMS
                # ----------------------
                for item in menu_items:
                    col1, col2, col3, col4, col5, col6 = st.columns([3,2,2,1,1,1])
            
                    # Show image
                    with col2:
                        try:
                            if item["image"] and os.path.exists(item["image"]):
                                st.image(Image.open(item["image"]), width=80)
                            else:
                                st.write("No Image")
                        except:
                            st.write("No Image")
            
                    # Show availability
                    with col4:
                        status = "🟢 Available" if item["available"] else "🔴 Disabled"
                        st.write(status)
            
                    # Toggle availability
                    with col5:
                        st.button(
                            "Toggle",
                            key=f"toggle_{tab_name}_{item['id']}",
                            on_click=toggle_item,
                            args=(item["id"],)
                        )
            
                    # Delete item
                    with col6:
                        st.button(
                            "Delete",
                            key=f"delete_{tab_name}_{item['id']}",
                            on_click=delete_item,
                            args=(item["id"],)
                        )

                    # Show item name + variants (variants below name)
                    # ... inside display_menu_items loop ...
                    with col3:
                        try:
                            variants = json.loads(item["variants"]) if item["variants"] else []
                        except:
                            variants = []
                            
                        st.markdown(f"**{item['name']}**")
                        # Show variants below item name
                        if variants:
                            variant_names = ", ".join([v["name"] for v in variants])
                            st.markdown(
                                f"<span style='color:gray; font-size:13px;'>{variant_names}</span>",
                                unsafe_allow_html=True
                            )
            
                        if variants:
                            if tab_name == "active":
                                # In Active Tab: Show only what is available
                                available_vars = [v["name"] for v in variants if v.get("available", True)]
                                st.markdown(f"<span style='color:green; font-size:13px;'>🟢 Active: {', '.join(available_vars)}</span>", unsafe_allow_html=True)
                            
                            elif tab_name == "disabled":
                                # In Disabled Tab: Show only what is paused
                                paused_vars = [v["name"] for v in variants if not v.get("available", True)]
                                if paused_vars:
                                    st.markdown(f"<span style='color:red; font-size:13px;'>🔴 Paused: {', '.join(paused_vars)}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown("<span style='color:gray; font-size:13px;'>Entire Item Disabled</span>", unsafe_allow_html=True)
                    
                    # Edit Item
                    with col1:
                        if st.button("✏️", key=f"edit_{tab_name}_{item['id']}"):
                            st.session_state.edit_id = item['id']
                            st.session_state.edit_name = item['name']
                            st.session_state.edit_price = item['price']
                            st.session_state.edit_image = item['image']
                            st.session_state[f"variants_{item['id']}"] = json.loads(item["variants"]) if item["variants"] else []
                            st.rerun()
            
                    if st.session_state.get("edit_id") == item["id"]:
                        col1, col2 = st.columns(2)
                        with col1:
                            with st.container(border=True):
                                new_name = st.text_input("Item Name", value=st.session_state.edit_name, key=f"name_{tab_name}_{item['id']}")
                                new_price = st.number_input("Base Price", value=float(st.session_state.edit_price), step=1.0, key=f"pricename_{tab_name}_{item['id']}")
                                
                                # Edit variants
                                variants = st.session_state.get(f"variants_{item['id']}")
                                st.markdown("### 🔹 Variants")
                                # ... inside the variants loop ...
                                for i, v in enumerate(variants):
                                    is_v_available = v.get("available", True) 
                                    col_v1, col_v2, col_v3, col_v4 = st.columns([4, 2, 1, 1])
                                    
                                    with col_v1:
                                        # Visual strike-through if paused
                                        v_display = f"~~{v['name']}~~" if not is_v_available else v['name']
                                        st.markdown(f"**{v_display}**", unsafe_allow_html=True)
                                        v_name = st.text_input(f"Name {i+1}", value=v["name"], key=f"vname_edit_{tab_name}_{item['id']}_{i}", label_visibility="collapsed")
                                        
                                    with col_v2:
                                        v_price = st.number_input(f"Price {i+1}", value=v["price"], min_value=0, key=f"vprice_edit_{tab_name}_{item['id']}_{i}", label_visibility="collapsed")
                                    
                                    with col_v3:
                                        btn_label = "⏸️" if is_v_available else "▶️"
                                        # Inside your variant loop
                                        if st.button(btn_label, key=f"toggle_{tab_name}_{item['id']}_{i}"):
                                            variants[i]["available"] = not is_v_available
                                            
                                            # Calculate main item status
                                            item_active_flag = 1 if any(var.get("available", True) for var in variants) else 0
                                            
                                            cursor.execute("""
                                                UPDATE menu_items 
                                                SET variants=%s, available=%s 
                                                WHERE id=%s AND email=%s
                                            """, (json.dumps(variants), item_active_flag, item['id'], st.session_state["email"]))
                                            db.commit()
                                            st.rerun()
                                
                                    with col_v4:
                                        if st.button("❌", key=f"remove_{tab_name}_{item['id']}_{i}"):
                                            variants.pop(i)
                                            # Recalculate item availability after removal
                                            item_available_flag = 1 if (variants and any(var.get("available", True) for var in variants)) else 0
                                            cursor.execute("UPDATE menu_items SET variants=%s, available=%s WHERE id=%s", 
                                                           (json.dumps(variants), item_available_flag, item['id']))
                                            db.commit()
                                            st.session_state[f"variants_{item['id']}"] = variants
                                            st.rerun()
                                
                                    # Sync local variables for the main Save button
                                    variants[i]["name"] = v_name
                                    variants[i]["price"] = v_price
                                    # 'available' is handled by the toggle button above
                            with col2:
                                with st.container(border=True):
                                    st.markdown("### 🖼️ Update Image")
                                    new_image_file = st.file_uploader("Choose new image (leave blank to keep current)", type=['png', 'jpg', 'jpeg'], key=f"img_up_{tab_name}_{item['id']}")
        
                        # Save button
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("✅ Save Item", key=f"save_{tab_name}_{item['id']}"):
                                if new_image_file is not None:
                                    # Create a directory if it doesn't exist
                                    os.makedirs("menu_images", exist_ok=True)
                                    # Define new path (using timestamp or item ID to avoid name collisions)
                                    final_image_path = os.path.join("menu_images", f"{item['id']}_{new_image_file.name}")
                                    with open(final_image_path, "wb") as f:
                                        f.write(new_image_file.getbuffer())
                                variants_json = json.dumps(variants) if variants else None
                                active_prices = [v["price"] for v in variants if v.get("available", True)]
                                base_price = min([v["price"] for v in variants]) if variants else new_price
                                is_item_available = any(v.get("available", True) for v in variants) if variants else 1

                                cursor.execute("""
                                    UPDATE menu_items
                                    SET name=%s, price=%s, image=%s, variants=%s, available = %s
                                    WHERE id=%s AND email=%s
                                """, (
                                    new_name,
                                    base_price,
                                    st.session_state.edit_image,
                                    variants_json,
                                    is_item_available,
                                    item['id'],
                                    st.session_state["email"]
                                ))
                                db.commit()
                                st.success("✅ Item updated successfully")
                                del st.session_state.edit_id
                                st.rerun()
                        with col_cancel:
                            if st.button("❌ Cancel", key=f"cancel_{tab_name}_{item['id']}"):
                                del st.session_state.edit_id
                                st.rerun()
            
            # ----------------------
            # FILTER TABS
            # ----------------------
            tab_all, tab_active, tab_disabled = st.tabs(["📦 All Items", "🟢 Active", "🔴 Disabled"])
            
            with tab_all:
                search_all = st.text_input("🔍 Search Menu Item by Name", key="search_all")
                query = "SELECT * FROM menu_items WHERE is_active=1 AND email=%s"
                params = [st.session_state["email"]]
                
                if search_all:
                    query += " AND name LIKE %s"
                    params.append(f"%{search_all}%")
                
                cursor.execute(query, tuple(params))
                display_menu_items(cursor.fetchall(), "all")
            
            with tab_active:
                search_active = st.text_input("🔍 Search Active Item", key="search_active")
                # Show items that have at least one active variant
                query = "SELECT * FROM menu_items WHERE is_active=1 AND available=1 AND email=%s"
                params = [st.session_state["email"]]
                if search_active:
                    query += " AND name LIKE %s"
                    params.append(f"%{search_active}%")
                cursor.execute(query, tuple(params))
                display_menu_items(cursor.fetchall(), "active")
            
            with tab_disabled:
                search_disabled = st.text_input("🔍 Search Disabled Item", key="search_disabled")
                # NEW LOGIC: Show item if available=0 OR if the variants JSON contains "available": false
                query = """
                    SELECT * FROM menu_items 
                    WHERE is_active=1 AND email=%s 
                    AND (available=0 OR variants LIKE '%"available": false%')
                """
                params = [st.session_state["email"]]
                if search_disabled:
                    query += " AND name LIKE %s"
                    params.append(f"%{search_disabled}%")
                cursor.execute(query, tuple(params))
                display_menu_items(cursor.fetchall(), "disabled")


    elif selected == "Orders":
        st.title("🧾 Order Management")
        st_autorefresh(interval=5000, key="orders_autorefresh")  # Auto-refresh every 5s
        st.divider()

        # ----------------------------
        # 🔹 ORDER SUMMARY MATRIX
        # ----------------------------
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) AS completed_count,
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending_count,
                SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END) AS cancelled_count
            FROM orders
            WHERE email = %s
        """, (st.session_state["email"],))
        counts = cursor.fetchone()
    
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Completed Orders", counts["completed_count"] or 0)
        with col2:
            st.metric("⏳ Pending Orders", counts["pending_count"] or 0)
        with col3:
            st.metric("❌ Cancelled Orders", counts["cancelled_count"] or 0)
    
        st.divider()

        # 🔹 Search box for specific order
        search_order_id = st.text_input("🔍 Search Order ID", placeholder="Enter ID...")
        

        # ----------------------------
        # 🔹 Function to show orders
        # ----------------------------
        def show_orders(status, key_prefix):
            query_params = [status, st.session_state["email"]]
        
            sql = """
                SELECT *
                FROM orders
                WHERE status = %s
                  AND email = %s
                  AND table_no = 0
                ORDER BY order_time DESC
            """
        
            cursor.execute(sql, tuple(query_params))
            orders = cursor.fetchall()
        
            if not orders:
                st.info(f"No {status.lower()} orders found")
                return
        
            for order in orders:
                customer_name = order.get("customer_name", "Guest")
                payment_method = (order.get("payment_method") or "OFFLINE").upper()
                payment_badge = "💳 ONLINE" if payment_method == "ONLINE" else "💵 OFFLINE"
                
                with st.expander(
                    f"🧾 Order #{order['display_order_id']} | {customer_name} | {status} | {payment_badge}"):
                    st.markdown(f"👤 **Customer Name:** `{customer_name}`")
                    st.markdown(f"📍 **Address:** `{order.get('customer_address','')}`")
                    st.markdown(f"💳 **Payment:** `{payment_method}`")
                    st.markdown(f"🕒 **Time:** `{order.get('order_time')}`")
        
                    # Fetch order items
                    cursor.execute("""
                        SELECT
                            m.name,
                            oi.variant_name,
                            oi.variant_price,
                            m.image,
                            oi.quantity
                        FROM order_items oi
                        JOIN menu_items m ON oi.menu_id = m.id
                        WHERE oi.order_id = %s
                    """, (order["id"],))
        
                    items = cursor.fetchall()
                    total = 0
        
                    for i in items:
                        # ✅ FIXED: handle None variant_name
                        variant = i["variant_name"] if i["variant_name"] else "Regular"  
    
                        subtotal = i["variant_price"] * i["quantity"]
                        total += subtotal
        
                        col_img, col_text = st.columns([1, 4])
                        with col_img:
                            try:
                                if i["image"] and os.path.exists(i["image"]):
                                    st.image(Image.open(i["image"]), width=70)
                                else:
                                    st.write("No image")
                            except:
                                st.write("No image")
                        with col_text:
                            st.markdown(
                                f"**{i['name']} ({variant})**  \n"
                                f"₹ {i['variant_price']} × {i['quantity']} = **₹ {subtotal}**"
                            )
    
                    st.markdown(f"### 💰 Total: ₹{total}")
        
                    col1, col2, col3 = st.columns(3)
        
                    with col1:
                        if status == "PENDING":
                            if st.button("✅ Mark Completed", key=f"{key_prefix}_done_{order['id']}"):
                                cursor.execute("""
                                    UPDATE orders
                                    SET status='COMPLETED'
                                    WHERE id=%s AND email=%s
                                """, (order["id"], st.session_state["email"]))
                                db.commit()
                                st.experimental_rerun()
        
                    with col2:
                        if status == "PENDING":
                            if st.button("❌ Cancel Order", key=f"{key_prefix}_cancel_{order['id']}"):
                                cursor.execute("""
                                    UPDATE orders
                                    SET status='CANCELLED'
                                    WHERE id=%s AND email=%s
                                """, (order["id"], st.session_state["email"]))
                                db.commit()
                                st.experimental_rerun()
        
                    # ✅ NEW: Download single order bill
                    with col3:
                        file_path = generate_bill_pdf(order["id"])
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    "Download PDF",
                                    f,
                                    file_name=os.path.basename(file_path),
                                    mime="application/pdf",
                                    key=f"dl_btn_{order['id']}"
                                )
                        else:
                            st.warning("❌ Bill not found")
    
        # ----------------------------
        # Show Orders by Status Tabs
        # ----------------------------
    
        subtab_completed, subtab_pending, subtab_cancelled = st.tabs(
                 ["✅ Completed", "⏳ Pending", "❌ Cancelled"]
            )
            
        with subtab_completed:
            file_path = generate_all_bills_pdf("COMPLETED")
            if file_path:
                with open(file_path, "rb") as f:
                    st.download_button(
                        "📥 Download All PDF",
                        f,
                        file_name=os.path.basename(file_path),
                        mime="application/pdf"
                    )
            else:
                st.warning("No completed orders found")
    
            st.divider()
            show_orders("COMPLETED", "completed")
            
    
        with subtab_pending:
            col1, col2 = st.columns([2,3])
            with col1:
                if st.button("✅ Mark ALL Pending as Completed"):
                    cursor.execute("""
                        UPDATE orders
                        SET status='COMPLETED'
                        WHERE status='PENDING' AND email=%s
                    """, (st.session_state["email"],))
                    db.commit()
                    st.success("✅ All pending orders marked as COMPLETED")
                    st.experimental_rerun()
            st.divider()
            show_orders("PENDING", "pending")
    
        with subtab_cancelled:
            if st.button("🧹 Clear Cancelled Orders"):
                cursor.execute("""
                    DELETE FROM order_items
                    WHERE order_id IN (
                        SELECT id FROM orders
                        WHERE status = 'CANCELLED'
                        AND email = %s
                    )
                """, (st.session_state["email"],))
                
                cursor.execute("""
                    DELETE FROM orders
                    WHERE status = 'CANCELLED'
                    AND email = %s
                """, (st.session_state["email"],))
                
                db.commit()
                st.success("✅ Cancelled orders cleared successfully")
                st.rerun()
    
            st.divider()
            show_orders("CANCELLED", "cancelled")

    elif selected == "Tables":
        st.title("🪑 Live Table Status")
        
        # 🟢 FIX: Added Missing Table Logic
        total_tables = st.session_state.total_tables 
        cols = st.columns(4)
        for i in range(1, total_tables + 1):
            with cols[(i - 1) % 4]:
                if st.button(f"🪑 Table {i}", key=f"table_{i}", use_container_width=True):
                    st.session_state.selected_table = i 
        
        if st.session_state.get("selected_table"):
            table_no = st.session_state.selected_table
            st.divider()
            st.markdown(f"## 📋 Orders for Table {table_no}") 
            
            # Fetch Pending Orders for this table
            cursor.execute("""
                SELECT * FROM orders
                WHERE table_no=%s AND email=%s AND status='PENDING'
                ORDER BY order_time DESC
            """, (table_no, st.session_state["email"]))

            orders = cursor.fetchall() 
            if not orders:
                st.info(f"No active orders for Table {table_no}")
            else:
                for order in orders:
                    with st.expander(f"Order #{order['display_order_id']} ({order['customer_name']})", expanded=True):
                        # Fetch Items
                        cursor.execute("""
                            SELECT m.name, oi.variant_name, oi.variant_price, oi.quantity
                            FROM order_items oi
                            JOIN menu_items m ON oi.menu_id = m.id
                            WHERE oi.order_id = %s
                        """, (order["id"],))
                        items = cursor.fetchall()
                        
                        total_bill = 0
                        for i in items:
                            variant = i["variant_name"] if i["variant_name"] else "Regular"
                            subtotal = i["variant_price"] * i["quantity"]
                            total_bill += subtotal
                            st.write(f"• {i['name']} ({variant}) x {i['quantity']} = ₹{subtotal}")
                        
                        st.markdown(f"**Total: ₹{total_bill}**")
                        
                        # Actions
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Complete", key=f"tbl_done_{order['id']}"):
                                cursor.execute("UPDATE orders SET status='COMPLETED', table_no=0 WHERE id=%s", (order['id'],))
                                db.commit()
                                st.success("Order Completed")
                                st.rerun()
                        with c2:
                            if st.button("❌ Cancel", key=f"tbl_cancel_{order['id']}"):
                                cursor.execute("UPDATE orders SET status='CANCELLED', table_no=0 WHERE id=%s", (order['id'],))
                                db.commit()
                                st.rerun()



    elif selected == "Edit Company":
        # --- 1. THEME HEADER ---
        # Using your gradient header style from the CSS
        st.markdown('<div class="header-style"><h1>✏️ Edit Company Details</h1></div>', unsafe_allow_html=True)
    
        # Success Message Handling
        if st.session_state.get("company_updated"):
            st.success("✅ Company details updated successfully!")
            del st.session_state.company_updated
    
        # --- BOX 1: CORE INFORMATION ---
        
        with st.container(border=True):
            st.markdown("### 🏢 Basic Information")
            
            company_name = st.text_input("Company / Cafe Name", value=st.session_state.get("menu_title", "Jay Vachraj"))
            
            # Internal columns for compact inputs within the vertical box
            row_a, row_b = st.columns(2)
            with row_a:
                gst_number = st.text_input("GST Number", value=st.session_state.get("gst_number", ""))
            with row_b:
                mobile = st.text_input("Company Phone Number", value=st.session_state.get("company_phone", ""), placeholder="+91 ...")
            
            company_address = st.text_area("Company Address", value=st.session_state.get("company_address", ""), height=100)
            total_tables = st.number_input("🪑 Total Tables in Cafe", min_value=0, max_value=100, value=st.session_state.get("total_tables", 0))

        # --- BOX 2: PAYMENT SETTINGS ---
            st.divider()
            st.markdown("### 📱 UPI / Payment Settings")
            
            upi_id = st.text_input("UPI ID (for Online Payments)", value=st.session_state.get("upi_id", ""), placeholder="example@okaxis")
            
            up_col, preview_col = st.columns([2, 1])
            with up_col:
                upi_image = st.file_uploader("Upload New QR Image", type=["png", "jpg", "jpeg"])
            with preview_col:
                if st.session_state.get("upi_qr_image"):
                    try:
                        st.image(st.session_state.upi_qr_image, width=120, caption="Current QR")
                    except:
                        st.caption("⚠️ QR not found")
    
        # --- BOX 3: ACTIONS ---
            with st.container(border=True):
                online_payment_enabled = st.toggle(
                    "Enable Online Payment", 
                    value=st.session_state.get("online_payment_enabled", True),
                    help="Toggle UPI / GPay / PhonePe visibility for customers"
                )

        st.space("small")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
                <style>
                .css-card {
                    border: 2px solid #f0f2f6;
                    border-radius: 10px;
                    padding: 25px;
                    margin-bottom: 20px;
                    background-color: #ffffff;
                    box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
                    color: #31333F;
                }
                </style>
            """, unsafe_allow_html=True)
            # Save Button (Uses your primary gradient CSS)
            if st.button("💾 Save Company Details"):
                qr_filename = st.session_state.get("upi_qr_image")
                
                if upi_image:
                    os.makedirs("company_qr", exist_ok=True)
                    qr_filename = f"company_qr/{upi_image.name}"
                    with open(qr_filename, "wb") as f:
                        f.write(upi_image.getbuffer())
                
                # Database Update Logic
                cursor.execute("""
                    UPDATE admin_requests
                    SET company_name=%s, company_address=%s, gst_number=%s, mobile=%s, 
                        upi_qr_image=%s, upi_id=%s, total_tables=%s, online_payment_enabled=%s
                    WHERE email=%s
                """, (company_name, company_address, gst_number, mobile, qr_filename, 
                      upi_id, total_tables, int(online_payment_enabled), st.session_state["email"]))
                db.commit()
    
                # Update session state
                st.session_state.update({
                    "menu_title": company_name,
                    "company_address": company_address,
                    "gst_number": gst_number,
                    "company_phone": mobile,
                    "upi_qr_image": qr_filename,
                    "upi_id": upi_id,
                    "total_tables": total_tables,
                    "online_payment_enabled": online_payment_enabled,
                    "company_updated": True
                })
                st.rerun()
        
        with col2:
            # Cancel Button (Uses your white/gray .cancel-container CSS)
            if st.button("❌ Discard Changes"):
                st.info("Changes discarded.")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    

    elif selected == "Inventory / Sales":
        st.title("📈 Analytics & Reports")
        col1, col2 = st.columns(2)
    
        # --- COLUMN 1: ANALYTICS & REPORTS ---
        with col1:
            with st.container(border=True):
                # Wrap in a div for the border
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.subheader("📊 Inventory / Sales")
                
                report_type = st.selectbox("Select Type", ["Daily", "Monthly", "Yearly"])
                    
                # Prepare query parameters
                query_params = []
                query = """
                    SELECT
                    o.id AS id,
                    m.name,
                    o.order_time,
                    o.customer_name,
                    o.customer_address,
                    oi.variant_name,
                    oi.quantity,
                    oi.variant_price,
                    (oi.quantity * oi.variant_price) AS total
                    FROM orders o
                    JOIN order_items oi ON o.id = oi.order_id
                    JOIN menu_items m ON oi.menu_id = m.id
                    WHERE o.status = 'COMPLETED'
                      AND o.email = %s
                """
                query_params.append(st.session_state["email"])
        
                
                if report_type == "Daily":
                    selected_date = st.date_input("Select Date _(yyyy-mm-dd)_")
                    query += " AND DATE(o.order_time) = %s"
                    query_params.append(selected_date)
        
                    
                elif report_type == "Monthly":
                    month = st.selectbox("Month", range(1, 13))
                    year = st.selectbox("Year", range(2025, 2035))
                    query += " AND MONTH(o.order_time) = %s AND YEAR(o.order_time) = %s"
                    query_params.extend([month, year])
        
                    
                else:  # Yearly
                    year = st.selectbox("Year", range(2025, 2035))
                    query += " AND YEAR(o.order_time) = %s"
                    query_params.append(year)
        
                
                query += " ORDER BY o.order_time ASC"
                
                cursor.execute(query, tuple(query_params))
                sales = cursor.fetchall()
                
                if not sales:
                    st.info("No sales data found.")
                else:
                    df = pd.DataFrame(sales)
                    df['order_time'] = df['order_time'].astype(str)  # convert datetime to string
                    
                    st.dataframe(df)  # show table in Streamlit
                    
                    total_revenue = df['total'].sum()
                    st.markdown(f"## 💰 Total Revenue: ₹ {total_revenue:.2f}")
                    
                    # Excel download
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sales')
                        writer.close()
                    output.seek(0)
                    
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=output,
                        file_name=f"sales_report_{report_type.lower()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        
        with col2:
            with st.container(border=True):
                # Wrap in a div for the border
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.subheader("📈 Sales Comparison")
                
                compare_type = st.selectbox(
                    "Compare By",
                    ["Day vs Day", "Month vs Month", "Year vs Year"],
                    key="compare_type"
                )
                    
                # Helper function to plot and show comparison
                def plot_comparison(label1, value1, label2, value2):
                    fig, ax = plt.subplots(figsize=(6,4))
                    bars = ax.bar([label1, label2], [value1, value2], color=["#4CAF50", "#2196F3"])
                    ax.set_ylabel("Total Sales (₹)")
                    ax.set_title("Sales Comparison")
            
                    # Add value labels on top of bars
                    for bar in bars:
                        yval = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 10, f"₹ {yval:.2f}", ha='center', va='bottom')
            
                    st.pyplot(fig)
            
                    # Calculate difference
                    diff = value2 - value1
                    if diff > 0:
                        st.success(f"📈 Profit/Increase: ₹ {diff:.2f}")
                    elif diff < 0:
                        st.error(f"📉 Loss/Decrease: ₹ {abs(diff):.2f}")
                    else:
                        st.info("⚖️ No Change")
            
                # --- Day vs Day ---
                if compare_type == "Day vs Day":
                    col1_cmp, col2_cmp = st.columns(2)
                    with col1_cmp:
                        day1 = st.date_input("Select First Day", key="day1")
                    with col2_cmp:
                        day2 = st.date_input("Select Second Day", key="day2")
                    
                    cursor.execute("""
                        SELECT DATE(o.order_time) AS day,
                               SUM(oi.quantity * oi.variant_price) AS total
                        FROM orders o
                        JOIN order_items oi ON o.id = oi.order_id
                        JOIN menu_items m ON oi.menu_id = m.id
                        WHERE DATE(o.order_time) IN (%s, %s)
                          AND o.status = 'COMPLETED'
                          AND o.email = %s
                        GROUP BY DATE(o.order_time)
                    """, (day1, day2, st.session_state["email"]))
        
                    
                    data = cursor.fetchall()
                    # Default to 0 if no sales
                    total1 = next((x['total'] for x in data if str(x['day']) == str(day1)), 0)
                    total2 = next((x['total'] for x in data if str(x['day']) == str(day2)), 0)
                    
                    plot_comparison(str(day1), total1, str(day2), total2)
            
                # --- Month vs Month ---
                elif compare_type == "Month vs Month":
                    col1_cmp, col2_cmp = st.columns(2)
                    with col1_cmp:
                        m1 = st.selectbox("Month 1", range(1,13), key="m1")
                        y1 = st.selectbox("Year 1", range(2025,2035), key="y1")
                    with col2_cmp:
                        m2 = st.selectbox("Month 2", range(1,13), key="m2")
                        y2 = st.selectbox("Year 2", range(2025,2035), key="y2")
                    
                    cursor.execute("""
                        SELECT CONCAT(MONTH(o.order_time), '-', YEAR(o.order_time)) AS period,
                               SUM(oi.quantity * oi.variant_price) AS total
                        FROM orders o
                        JOIN order_items oi ON o.id = oi.order_id
                        JOIN menu_items m ON oi.menu_id = m.id
                        WHERE (
                            (MONTH(o.order_time)=%s AND YEAR(o.order_time)=%s)
                            OR
                            (MONTH(o.order_time)=%s AND YEAR(o.order_time)=%s)
                        )
                        AND o.status='COMPLETED'
                        AND o.email=%s
                        GROUP BY period
                    """, (m1, y1, m2, y2, st.session_state["email"]))
        
                    
                    data = cursor.fetchall()
                    label1 = f"{m1}-{y1}"
                    label2 = f"{m2}-{y2}"
                    total1 = next((x['total'] for x in data if x['period']==label1), 0)
                    total2 = next((x['total'] for x in data if x['period']==label2), 0)
                    
                    plot_comparison(label1, total1, label2, total2)
            
                # --- Year vs Year ---
                elif compare_type == "Year vs Year":
                    col1_cmp, col2_cmp = st.columns(2)
                    with col1_cmp:
                        year1 = st.selectbox("Select Year 1", range(2025,2035), key="y_y_1")
                    with col2_cmp:
                        year2 = st.selectbox("Select Year 2", range(2025,2035), key="y_y_2")
                    
                    cursor.execute("""
                        SELECT YEAR(o.order_time) AS y,
                               SUM(oi.quantity * oi.variant_price) AS total
                        FROM orders o
                        JOIN order_items oi ON o.id = oi.order_id
                        JOIN menu_items m ON oi.menu_id = m.id
                        WHERE YEAR(o.order_time) IN (%s,%s)
                          AND o.status='COMPLETED'
                          AND o.email=%s
                        GROUP BY YEAR(o.order_time)
                    """, (year1, year2, st.session_state["email"]))
                
                    data = cursor.fetchall()
                    total1 = next((x['total'] for x in data if x['y']==year1), 0)
                    total2 = next((x['total'] for x in data if x['y']==year2), 0)
                    
                    plot_comparison(str(year1), total1, str(year2), total2)


    elif selected == "Help & Support":
        # ==========================
        # 🎨 HELP PAGE SPECIFIC CSS & LAYOUT
        # ==========================

        # Load FontAwesome for Icons
        st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">', unsafe_allow_html=True)

        # Custom CSS to achieve the "Separation" look
        st.markdown("""
        <style>
            /* 1. Force Sidebar to be White with a Border (The Separation) */
            section[data-testid="stSidebar"] {
                background-color: #ffffff !important;
                border-right: 1px solid #e5e7eb !important; /* Subtle gray border */
                box-shadow: none !important;
            }

            /* 2. Main Area Background */
            .stApp {
                background-color: #f8fafc; /* Very light gray bg to make white cards pop */
            }

            /* 3. Card Styling */
            .support-card {
                background-color: #E1E8F3;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                border: 1px solid #111111;
                height: 100%;
                min-height: 550px; /* Ensure equal height */
                display: flex;
                flex-direction: column;
            }
            
            /* Hover Effect */
            .support-card:hover {
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                transform: translateY(-2px);
                transition: all 0.3s ease;
            }

            /* Gradient Icon Boxes */
            .icon-container {
                width: 64px;
                height: 64px;
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                color: white;
                margin-bottom: 24px;
            }

            .icon-blue { background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%); }
            .icon-pink { background: linear-gradient(135deg, #ec4899 0%, #d946ef 100%); }

            /* Text Styling */
            .card-title {
                font-size: 22px;
                font-weight: 700;
                color: #1e293b;
                margin-bottom: 12px;
            }

            .card-text {
                font-size: 15px;
                color: #64748b;
                line-height: 1.6;
                margin-bottom: 20px;
            }

            /* Inner Contact Boxes (Phone/Hours) */
            .contact-box {
                background-color: #E1E8F3;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
            }

            .small-icon {
                width: 42px;
                height: 42px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 18px;
                margin-right: 14px;
                flex-shrink: 0;
            }

            .bg-green { background-color: #10b981; }
            .bg-orange { background-color: #f59e0b; }

            .contact-label {
                font-size: 13px;
                font-weight: 700;
                color: #334155;
                margin-bottom: 2px;
            }
            
            .contact-value {
                font-size: 15px;
                font-weight: 600;
                color: #2563eb; /* Blue links */
            }
            
            .contact-sub {
                font-size: 12px;
                color: #94a3b8;
            }
        </style>
        """, unsafe_allow_html=True)

        # UI Header (Matches screenshot placement)
        st.title("Help & Support")
        st.markdown(f"<p style='color: #64748b; margin-top: -10px;'>Get assistance with the {st.session_state.menu_title} management system</p>", unsafe_allow_html=True)
        st.write("") # Spacer

        # --- NEW INTEGRATED HELP & SUPPORT HTML ---
        import streamlit.components.v1 as components
    
        # 1. Define your variables (or pull from session state)
        def get_office():
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT mobile_1, mobile_2 FROM office LIMIT 1")
            row = cursor.fetchone()
            cursor.close()
            db.close()
            return row

        
        # Fetch the data
        office_data = get_office()
        phone_1 = office_data.get('mobile_1') if office_data else ""
        phone_2 = office_data.get('mobile_2') if office_data else ""
        
        # 2. Use an f-string (notice the 'f' before the triple quotes)
        help_html = f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@700&display=swap" rel="stylesheet">
        <style>
            :root {{ --primary: #4361ee; --primary-dark: #3a56d4; --secondary: #7209b7; --accent: #f72585; --success: #4cc9f0; --light: #f8f9fa; --dark: #212529; --gray: #6c757d; --border-radius: 16px; }}
            body {{ font-family: 'Inter', sans-serif; background-color: transparent; margin: 0; padding: 0; }}
            .help-card {{ background: white; border-radius: var(--border-radius); padding: 30px; margin-bottom: 20px; border: 1px solid #eee; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .help-card-icon {{ width: 60px; height: 60px; border-radius: 14px; display: flex; align-items: center; justify-content: center; margin-bottom: 20px; font-size: 24px; color: white; }}
            .card-support .help-card-icon {{ background: linear-gradient(135deg, #4cc9f0, #4895ef); }}
            .card-contact .help-card-icon {{ background: linear-gradient(135deg, #f72585, #b5179e); }}
            .contact-item {{ display: flex; align-items: center; gap: 15px; padding: 15px; background: #f8f9fa; border-radius: 12px; margin-top: 10px; }}
            .contact-icon {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; }}
            .phone .contact-icon {{ background: #2ecc71; }}
            .feature-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 30px; }}
            .feature-card {{ background: white; padding: 20px; border-radius: 16px; border: 1px solid #eee; }}
            .feature-icon {{ font-size: 24px; color: var(--primary); margin-bottom: 10px; }}
            h2 {{ font-family: 'Poppins'; color: var(--dark); }}
        </style>
        
        <div class="help-content" style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div class="help-card card-support" style="flex: 1; min-width: 300px;">
                <div class="help-card-icon"><i class="fas fa-headset"></i></div>
                <h2>Need Help?</h2>
                <p>If you face any issues with the system, our dedicated support team is here to assist you.</p>
                <p><strong>Support Hours:</strong> 9:00 AM – 9:00 PM (All Days)</p>
            </div>
        
            <div class="help-card card-contact" style="flex: 1; min-width: 300px;">
                <div class="help-card-icon"><i class="fas fa-phone-alt"></i></div>
                <h2>Contact Support</h2>
                <div class="contact-item phone">
                    <div class="contact-icon"><i class="fas fa-phone"></i></div>
                    <div>
                        <div style="font-weight:600; color:#4361ee;">{phone_1}</div>
                        <div style="font-weight:600; color:#4361ee;">{phone_2}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="background: #f1f3f9; padding: 30px; border-radius: 20px; margin-top: 20px;">
            <h2 style="text-align:center;">System Features</h2>
            <div class="feature-grid">
                <div class="feature-card">
                    <i class="fas fa-file-invoice-dollar feature-icon"></i>
                    <h3>Automated Billing</h3>
                    <p>Generate GST-compliant bills and track payments efficiently.</p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-boxes feature-icon"></i>
                    <h3>Stock Management</h3>
                    <p>Track stock levels in real-time and reduce waste.</p>
                </div>
            </div>
        </div>
        """
        # Render the HTML inside Streamlit
        components.html(help_html, height=800, scrolling=True)

        st.divider()
        st.caption("© 2023 HD Billing Solutions. All rights reserved.")


if st.session_state["page"] == "downloadbill":
    order_id = st.session_state.get("bill_order_id")

    if "company_phone" not in st.session_state:
        cursor.execute("""
        SELECT mobile
        FROM admin_requests
        WHERE email = %s
    """, (st.session_state["email"],))

        row = cursor.fetchone()
        st.session_state.company_phone = row.get("mobile", "") if row else ""

    if not order_id:
        st.error("No order selected")
        st.stop()
    
    file_path = generate_bill_pdf(order_id)
    
    with open(file_path, "rb") as f:
        st.download_button(
            "📥 Download Bill PDF",
            f,
            file_name=os.path.basename(file_path),
            mime="application/pdf"
        )
    
    if st.button("⬅ Back to Orders"):
        st.session_state.page = "Admin"
        st.session_state.bill_order_id = None
        st.rerun()


    
