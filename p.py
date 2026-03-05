import streamlit as st
from PIL import Image
import qrcode
import io
from fpdf import FPDF
from datetime import datetime
import uuid
import mysql.connector
import urllib.parse
import json
import os
import time

# --- INITIAL CONFIGURATION ---
st.set_page_config(
    page_title="Admin Login · Company Portal",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- DATABASE CONNECTION ---
# Note: Ensure your local MySQL server is running
port = os.getenv("MYSQLPORT")

if port is None:
    port = 3306
else:
    port = int(port)
# --- DATABASE CONNECTION (TiDB Cloud) ---
db = mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4Er7E7yAa5CmneH.root",
        password="JubMX8vnCyJqhX96",
        database="cafe",
        ssl_verify_identity=True,
        ssl_ca="/etc/ssl/certs/ca-certificates.crt"
)
# This line must be indented exactly like 'db =' above it
cursor = db.cursor(dictionary=True)  
# --- DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "menu_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- SESSION STATE INITIALIZATION ---
if "page" not in st.session_state:
    st.session_state["page"] = "login"
if "items" not in st.session_state:
    st.session_state["items"] = []
if "email" not in st.session_state:
    st.session_state["email"] = None

def load_image(image_path):
    if not image_path:
        return Image.new("RGB", (300, 300), (200, 200, 200))

    # If DB path is relative, resolve it
    full_path = image_path
    if not os.path.isabs(image_path):
        full_path = os.path.join(BASE_DIR, image_path)

    if os.path.exists(full_path):
        try:
            return Image.open(full_path)
        except:
            pass

    return Image.new("RGB", (300, 300), (200, 200, 200))

# --- CUSTOM CSS (Your Design) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    .stApp {
        background: hsl(33, 39%, 82%);
        font-family: 'Inter', sans-serif;
    }
    
    .login-card {
        background: #ffffff;
        max-width: 440px;
        width: 90%; /* Changed from 100% for better margins on mobile */
        padding: 2rem 1.5rem; /* Reduced padding for mobile */
        border-radius: 24px;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.05);
        border: 1px solid hsla(30, 2%, 21%, 0.2);
        margin: 2rem auto;
    }

    /* Media Query for larger screens */
    @media (min-width: 480px) {
        .login-card {
            padding: 2.8rem 2.5rem 3.2rem 2.5rem;
            width: 100%;
        }
    }
    
    .stButton > button {
        width: 100%;
        height: 3.5rem; /* Explicit height for easier tapping */
        background: hsla(21, 81%, 51%, 0.9) !important;
        border-radius: 50px !important;
        color: white !important;
        font-weight: 600 !important;
    }

    /* Make images rounded and mobile-friendly */
    img {
        border-radius: 15px;
    }
</style>
""", unsafe_allow_html=True)


def get_today_order_number(cursor, db, email):
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

# --- PAGE LOGIC ---

if st.session_state["page"] == "login":
    # Wrapper for Design
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<h1><i class="fas fa-lock-keyhole"></i> Admin Login</h1>', unsafe_allow_html=True)
    st.markdown('<div class="company-label"><i class="far fa-building"></i> Enter company name:</div>', unsafe_allow_html=True)
    
    # Logic Input
    company_input = st.text_input("Company Name", placeholder="your company name", label_visibility="collapsed")
    
    if st.button("Login"):
        if company_input.strip():
            cursor.execute("SELECT email, company_name, online_payment_enabled FROM admin_requests WHERE LOWER(company_name) = LOWER(%s)", (company_input.strip(),))
            admin_row = cursor.fetchone()
            
            if admin_row:
                st.session_state["email"] = admin_row["email"]
                st.session_state["menu_title"] = admin_row["company_name"]
                st.session_state["online_payment_enabled"] = bool(admin_row["online_payment_enabled"])
                st.session_state["page"] = "menu"
                st.success(f"Welcome, {admin_row['company_name']}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Company not found!")
        else:
            st.warning("Please enter company name.")
            
    st.markdown('<div style="margin-top:20px; text-align:center; color:gray; font-size:0.8rem;">Demo Version</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Jay Vachraj", layout="centered", initial_sidebar_state="collapsed")
db_menu = []

# Get all unique categories from the items fetched from DB
db_categories = sorted(list(set([item['name'] for item in db_menu if item.get('name')])))

# Create the dynamic list starting with "All"
categories = [{"id": "all", "label": "🍽️ All"}]
for cat in db_categories:
    categories.append({"id": cat.lower(), "label": cat})

email = st.session_state.get("email")

st.write("DEBUG EMAIL:", email)

cursor = db.cursor(dictionary=True)

cursor.execute("""
SELECT id, name, image, variants
FROM menu_items
WHERE available = 1
AND is_active = 1
AND email = %s
""", (email,))

db_menu = cursor.fetchall()

st.write("DEBUG MENU:", db_menu)

if st.session_state["page"] == "menu":    # Custom CSS for styling
    st.markdown("""
    <style>
        /* Main container styling */
        .stApp {
            background-color: #f5f3f0;
        }
        
        /* Welcome title styling */
        .welcome-title {
            font-size: 24px;
            font-weight: 600;
            color: #2d2d2d;
            margin-bottom: 12px;
        }
        
        .welcome-title span {
            background: #fceee6;
            padding: 2px 8px 2px 0;
            border-radius: 30px;
            font-weight: 500;
            color: #a5512c;
        }
        
        /* Category pills styling */
        .category-pill {
            display: inline-block;
            background: #f2ece7;
            border: 1px solid #e2d3c8;
            border-radius: 40px;
            padding: 10px 24px;
            font-size: 16px;
            font-weight: 500;
            color: #3b2c22;
            margin: 0 5px;
            cursor: pointer;
            transition: all 0.15s;
            white-space: nowrap;
        }
        
        .category-pill.active {
            background: #1e1e1e;
            color: white;
            border-color: #1e1e1e;
        }
        
        /* Search bar styling */
        .search-wrapper {
            display: flex;
            align-items: center;
            background: #f7f7f7;
            border-radius: 30px;
            padding: 6px 18px;
            border: 1px solid #eaeaea;
            margin: 15px 0;
        }
        
        /* Item card styling */
        .item-card {
            background: #ffffff;
            border-radius: 20px;
            padding: 12px;
            border: 1px solid #f0e3da;
            margin-bottom: 15px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .item-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.06);
        }
        
        .item-image {
            width: 100%;
            height: 130px;
            border-radius: 16px;
            object-fit: cover;
            margin-bottom: 12px;
        }
        
        .item-name {
            font-size: 16px;
            font-weight: 600;
            color: #2b2b2b;
        }
        
        .item-name small {
            font-weight: 400;
            font-size: 12px;
            color: #6b4f3a;
            display: block;
        }
        
        .item-price {
            font-weight: 650;
            font-size: 18px;
            color: #1e1e1e;
            margin: 8px 0;
        }
        
        .item-description {
            font-size: 11px;
            color: #8f7a6a;
            margin-bottom: 8px;
        }
        
        /* Quantity selector */
        .quantity-selector {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f8f8f8;
            border: 1px solid #ddcfc4;
            border-radius: 40px;
            padding: 4px 2px;
            margin-top: 8px;
        }
        
        .qty-btn {
            background: white;
            border: 1px solid #ddcfc4;
            border-radius: 30px;
            width: 36px;
            height: 36px;
            font-size: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #7b5f4b;
            cursor: pointer;
        }
        
        .qty-number {
            min-width: 30px;
            text-align: center;
            font-weight: 600;
            font-size: 18px;
        }
        
        /* Cart button */
        .cart-button {
            background: #1e1e1e;
            color: white;
            border: none;
            width: 100%;
            padding: 16px 20px;
            border-radius: 60px;
            font-weight: 600;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            cursor: pointer;
            margin-top: 20px;
            border: 1px solid #262626;
        }
        
        /* Remove default Streamlit padding */
        .main > div {
            padding: 0 !important;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
                
        /* Ensure the column container doesn't add extra padding */
        [data-testid="column"] {
            padding: 0px 5px !important;
        }
        
    
        .custom-item-image {
            width: 100%;
            height: 130px;
            border-radius: 16px;
            object-fit: cover;
            margin-bottom: 10px;
        }
    
        .item-name {
            font-size: 16px;
            font-weight: 600;
            color: #2b2b2b;
            margin-bottom: 8px;
        }
                
        /* 1. Add this to your existing <style> block */
        /* Horizontal scrolling for category buttons on mobile */
        div[data-testid="stHorizontalBlock"]:has(button[key^="cat_"]) {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
            padding-bottom: 10px !important;
        }
        
        div[data-testid="stHorizontalBlock"]:has(button[key^="cat_"]) > div {
            min-width: 120px !important; /* Ensures buttons don't shrink too much */
        }
        
        /* Make number input buttons more touch-friendly for mobile */
        div[data-testid="stNumberInput"] {
            width: 100% !important;
        }
        
        .item-price {
            font-size: 16px !important; /* Slightly smaller for mobile grid */
            margin-top: 5px !important;
        }
        
        .item-name {
            line-height: 1.2;
            min-height: 40px; /* Keeps grid aligned */
        }
                
        .scrollable-menu {
            max-height: 70vh !important; /* Takes up 70% of the screen height */
            overflow-y: auto !important;
            padding: 10px !important;
            border-radius: 15px !important;
            background: rgba(255, 255, 255, 0.2) !important; /* Subtle contrast */
        }
            
        .sticky-footer {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            width: 100% !important;
            background-color: white !important;
            padding: 15px !important;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.1) !important;
    </style>
    """, unsafe_allow_html=True)
    
    menu_to_show = db_menu
    
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = 'all'
    
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ''


    # Create a dictionary for quick access
    item_dict = {item["id"]: item for item in menu_to_show}
    
    # Header
    st.markdown("""
    <div class="welcome-title">
        WELCOME TO <span>'jay vachraj'</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Search bar
    search = st.text_input("🔍", placeholder="Search item...", 
                           key="search_input", label_visibility="collapsed")
    st.session_state.search_term = search.lower() if search else ""

    # --- DYNAMIC CATEGORY EXTRACTION ---
    # 1. Get unique categories from your DB results
    unique_cats = sorted(list(set([item['name'] for item in db_menu if item.get('name')])))
    
    # 2. Build the categories list dynamically
    categories = [{"id": "all", "label": "🍽️ All"}]
    for cat in unique_cats:
        categories.append({"id": cat.lower(), "label": cat})
    
    # --- RENDER CATEGORY BUTTONS ---
    # These will scroll horizontally on mobile thanks to the CSS above
    cat_cols = st.columns(len(categories))
    for i, category in enumerate(categories):
        with cat_cols[i]:
            if st.button(
                category["label"],
                key=f"cat_{category['id']}",
                use_container_width=True,
                type="primary" if st.session_state.selected_category == category['id'] else "secondary"
            ):
                st.session_state.selected_category = category['id']
                st.rerun()
    
    # Menu items display
    st.markdown("### 📋 OUR MENU · <span style='color: #a5512c; font-size: 14px;'>fresh & tasty</span>", 
                unsafe_allow_html=True)
    
    # Category Filtering logic (based on your dynamic categories)
    # Filter logic based on selected category and search term
    # Filter and Flatten Logic
    search_query = st.session_state.get('search_input', '').lower()
    selected_cat = st.session_state.get('selected_category', 'all')

    menu_to_show = []
    for item in db_menu:
        # 1. Check Category and Search
        match_cat = (selected_cat == "all" or item['name'].lower() == selected_cat)
        match_search = (not search_query or search_query in item["name"].lower())
        
        if match_cat and match_search:
            item_variants = json.loads(item.get("variants") or "[]")
            if not item_variants:
                item_variants = [{"name": "Standard", "price": 0}]
            
            # 2. CREATE A SEPARATE CARD FOR EVERY VARIANT
            for v in item_variants:
                variant_item = item.copy()
                variant_item['active_variant_name'] = v['name']
                variant_item['active_variant_price'] = v['price']
                # Unique key for identifying this specific card
                variant_item['unique_key'] = f"{item['id']}_{v['name']}"
                menu_to_show.append(variant_item)
    
    import base64

    def get_image_base64(img):
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    
    # --- START SCROLLABLE AREA ---
    st.markdown('<div class="scrollable-menu">', unsafe_allow_html=True)

    # Grid Layout
    for i in range(0, len(menu_to_show), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(menu_to_show):
                item = menu_to_show[i + j]
                v_name = item['active_variant_name']
                price = item['active_variant_price']
                u_key = item['unique_key'] # Use this for the key

                with cols[j]:
                    pil_img = load_image(item["image"])
                    img_base64 = get_image_base64(pil_img)

                    with st.container(border=True):
                        st.markdown(f"""
                            <img src="data:image/png;base64,{img_base64}" class="custom-item-image">
                            <div class="item-name"><strong>{v_name}</strong><br>
                            <small style='color:gray;'>{item['name']}</small></div>
                        """, unsafe_allow_html=True)
    
                        v_col1, v_col2 = st.columns([1, 1.2])
                        with v_col1:
                            st.markdown(f"<div class='item-price'>₹{price}</div>", unsafe_allow_html=True)
                        
                        with v_col2:
                            existing_item = next((x for x in st.session_state["items"] 
                                                if x["menu_id"] == item["id"] and x["variant"] == v_name), None)
                            
                            # Fix: Use unique_key to prevent duplicate widget ID errors
                            qty = st.number_input(
                                label="Qty",
                                min_value=0, step=1,
                                value=existing_item["quantity"] if existing_item else 0,
                                key=f"qty_{v_name}_{price}_{i}", 
                                label_visibility="collapsed"
                            )

                        # Update Cart Logic
                        if qty > 0:
                            if existing_item:
                                existing_item["quantity"] = qty
                                existing_item["total"] = qty * price
                            else:
                                st.session_state["items"].append({
                                    "item": item["name"], "menu_id": item["id"],
                                    "price": price, "quantity": qty, "total": qty * price,
                                    "image": item["image"], "variant": v_name
                                })
                        elif existing_item:
                            st.session_state["items"] = [x for x in st.session_state["items"] if not (x["menu_id"] == item["id"] and x["variant"] == v_name)]

    # --- CLOSE SCROLLABLE AREA (OUTSIDE THE LOOP) ---
    st.markdown("</div>", unsafe_allow_html=True)

    # We use a container to wrap the button so we can apply the sticky CSS
    st.markdown('<div class="sticky-footer">', unsafe_allow_html=True)
    
    # Calculate totals for the button label
    total_qty = sum(x["quantity"] for x in st.session_state["items"])
    total_price = sum(x["total"] for x in st.session_state["items"])

    if total_qty > 0:
        if st.button(f"🛒 View Cart ({total_qty} items) · ₹{total_price}", use_container_width=True, type="primary"):
            st.session_state["page"] = "cart"
            st.rerun()
    else:
        st.button("🛒 Cart is Empty", use_container_width=True, disabled=True)
        
    st.markdown('</div>', unsafe_allow_html=True)
        
    
elif st.session_state["page"]== "cart":
 st.title("Your Cart")
 
 if not st.session_state["items"]:
     st.warning("Your Cart Is Empty!")
 
 for i in st.session_state["items"].copy():
    idx = st.session_state["items"].index(i)
    col1, col2, col3, col4 = st.columns([4,3,2,1])

    with col1:
        # Display image from session (PIL)
        if i["image"]:
            img = load_image(i["image"])
            st.image(img, width=60)

        else:
            st.image(Image.new("RGB", (60, 60), color=(200, 200, 200)))

        st.write(f"**{i['item']}**")

    with col2:
        st.markdown(
            f"""
            **{i['item']}**  
            <span style="color:gray;">Variant: {i['variant']}</span>
            """,
            unsafe_allow_html=True
        )


    with col3:
        new_qty = st.number_input(
            "Qty",
            min_value=0,
            value=i["quantity"],
            key=f"cart_{i['menu_id']}_{i['variant']}"
        )
        i["quantity"] = new_qty
        i["total"] = new_qty * i["price"]

    with col4:
        if st.button("❌", key=f"remove_{i['menu_id']}_{i['variant']}"):
            st.session_state["items"].remove(i)
            st.rerun()


    if new_qty == 0:
        st.session_state["items"].remove(i)
        st.rerun()
         
 
 total = sum(i["total"] for i in st.session_state["items"])
 st.markdown(f"### 💰 Total: {total}₹")
 
 col1, col2, col3 = st.columns(3)
 
 with col1:
     if st.button("Add item "):
         st.session_state["page"]="menu"
         st.rerun()
 
 with col2:
     if st.button("Clear all"):
         st.session_state["items"]=[]
         st.rerun()

 # 🔹 Table number input
 st.session_state["table_no"] = st.number_input(
     "🍽️ Table Number",
     min_value=0,
     step=1,
     value=st.session_state.get("table_no", 0)
 )


 # 🔹 Customer name input (always visible before clicking Done)
 st.session_state["customer_name"] = st.text_input(
    "Enter your name:", st.session_state.get("customer_name", "")
 )
    
 st.session_state["customer_address"] = st.text_area(
    "Enter your address:",
    st.session_state.get("customer_address", ""),
    height=80
 )

 if "customer_address" not in st.session_state:
    st.session_state["customer_address"] = ""


 with col3:
    if st.button("Done"):
        if not st.session_state["customer_name"].strip():
            st.warning("⚠️ Please enter your name")
            st.stop()

        st.session_state["bill_items"] = st.session_state["items"].copy()
        st.session_state["total_amount"] = sum(
            i["total"] for i in st.session_state["bill_items"]
        )
        st.session_state["page"] = "bill"
        st.rerun()



# payment (bill page)
# payment (bill page)
elif st.session_state["page"] == "bill":
    st.title("Your Bill :")

    subtotal = sum(i["total"] for i in st.session_state["bill_items"])
    gst_percent = st.session_state.get("gst_percent", 0)
    gst_amount = (subtotal * gst_percent) / 100
    grand_total = subtotal + gst_amount

    for i in st.session_state["bill_items"]:
        st.write(
            f"{i['item']} ({i['variant']}) : "
            f"{i['price']} x {i['quantity']} = {i['total']}₹"
        ) 

    st.divider()
    st.write(f"Subtotal: ₹{subtotal}")
    if gst_percent > 0:
        st.write(f"GST ({gst_percent}%): ₹{gst_amount:.2f}")
    st.subheader(f"Total Amount: ₹{grand_total:.2f}")

    st.session_state["total_with_gst"] = grand_total
    
    col1, col2 = st.columns(2)
    
    # ---------------- PAY OFFLINE ----------------
    with col1:
        if st.button("Pay Offline"):
            display_order_id = get_today_order_number(
                cursor,
                db,
                st.session_state["email"]
            )

            cursor.execute("""
                INSERT INTO orders
                (email, customer_name, customer_address, table_no, payment_method, total_amount, display_order_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                st.session_state["email"],
                st.session_state["customer_name"],
                st.session_state["customer_address"],
                st.session_state.get("table_no", 0),
                "OFFLINE",
                grand_total,
                display_order_id
            ))
    
            order_id = cursor.lastrowid
            db.commit()
            
            # 🔥 INSERT ORDER ITEMS
            for i in st.session_state["bill_items"]:
                cursor.execute("""
                    INSERT INTO order_items
                    (order_id, menu_id, item_name, variant_name, variant_price, quantity, total)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    order_id,
                    i["menu_id"],
                    i["item"],
                    i["variant"],
                    i["price"],
                    i["quantity"],
                    i["total"]
                ))
    
            db.commit()
    
            st.session_state["last_order_id"] = order_id
            st.session_state["payment_method"] = "OFFLINE"
            st.session_state["display_order_id"] = display_order_id
            st.session_state["last_order_id"] = order_id

            st.session_state["cart"] = []
    
            st.success("✅ Order placed successfully!")
            st.session_state["page"] = "endoffline"
            st.rerun()
    
    # ---------------- PAY ONLINE ----------------
    with col2:
        if st.session_state.get("online_payment_enabled"):
           if st.button("💳 Pay Online"):
              display_order_id = get_today_order_number(
                  cursor,
                  db,
                  st.session_state["email"]
              )
  
              cursor.execute("""
                  INSERT INTO orders
                  (email, customer_name, customer_address, table_no, payment_method, total_amount, display_order_id)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)
              """, (
                  st.session_state["email"],
                  st.session_state["customer_name"],
                  st.session_state["customer_address"],
                  st.session_state.get("table_no", 0),
                  "ONLINE",
                  grand_total,
                  display_order_id
              ))
      
              order_id = cursor.lastrowid
              db.commit()
      
              for i in st.session_state["bill_items"]:
                  cursor.execute("""
                      INSERT INTO order_items
                      (order_id, menu_id, item_name, variant_name, variant_price, quantity, total)
                      VALUES (%s,%s,%s,%s,%s,%s,%s)
                  """, (
                      order_id,
                      i["menu_id"],
                      i["item"],
                      i["variant"],
                      i["price"],
                      i["quantity"],
                      i["total"]
                  ))
      
              db.commit()
      
              st.session_state["last_order_id"] = order_id
              st.session_state["payment_method"] = "ONLINE"
              st.session_state["display_order_id"] = display_order_id
              st.session_state["last_order_id"] = order_id
  
      
              st.success("✅ Order created. Proceed to payment.")
              st.session_state["page"] = "endonline"
              st.rerun()

        else:
              st.info("💵 Only Cash Payment Available")


elif st.session_state["page"] == "endoffline":
   st.subheader("Thank you 😊, Visit again!")
   st.success("YOUR ORDER IS CONFIRMED")

   if st.button("Download Bill"):
      st.session_state["page"] = "downloadbill"

elif st.session_state["page"] == "endonline":
    total = st.session_state.get("total_with_gst", 0)
    amount = f"{total:.2f}"

    upi_id = st.session_state.get("upi_id", "").strip()

    if not upi_id:
        st.error("❌ UPI ID not configured. Please contact staff.")
        st.stop()

    order_id = st.session_state.get("display_order_id", 0)

    amount = f"{total:.2f}"  # ✅ Decimal format

    final_upi_url = (
        "upi://pay?"
        f"pa={upi_id}"
        f"&pn={urllib.parse.quote(st.session_state["menu_title"])}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn=Order%20{order_id}"
    )


    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(final_upi_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    
    st.image(buf.getvalue(), caption=f"Scan & Pay ₹{amount}", width=300)

    st.markdown(f"""
    ### 🧾 Order ID: **{order_id}**
    📲 Scan using **Google Pay / PhonePe / Paytm**
    """)

    st.subheader("Thank you 😊, Visit again!")
    st.success("YOUR ORDER IS CONFIRMED")

    if st.button("Download Bill"):
        st.session_state["page"] = "downloadbill"


elif st.session_state["page"] == "downloadbill":
   st.title("🧾 Your Bill")

   customer_name = st.session_state.get("customer_name", "Guest")
   customer_address = st.session_state.get("customer_address", "N/A")
   bill_datetime = datetime.now().strftime("%d-%m-%y %I:%M %p")
   

   pdf = FPDF()
   pdf.add_page()
   
   # 🔥 Highlighted Company Name
   pdf.set_font("Arial", "B", 18)
   pdf.cell(0, 12, st.session_state["menu_title"], ln=True, align="C")
   
   pdf.ln(3)
   
   # Company Address
   pdf.set_font("Arial", size=11)
   pdf.multi_cell(0, 7, st.session_state["company_address"], align="C")
   
   # GST Number
   if st.session_state.get("company_gst"):
       pdf.ln(1)
       pdf.set_font("Arial", "B", 11)
       pdf.cell(0, 7, f"GST No: {st.session_state['company_gst']}", ln=True, align="C")

   # Company Mobile Number
   if st.session_state.get("company_phone"):
       pdf.set_font("Arial", "B", 11)
       pdf.cell(
           0,
           7,
           f"Mobile: {st.session_state['company_phone']}",
           ln=True,
           align="C"
       )
   
   pdf.ln(5)
   pdf.set_font("Arial", size=12)
   pdf.cell(0, 8, "-" * 40, ln=True)

   # 🔹 Reset font before printing date/time
   pdf.set_font("Arial", size=12)
   display_order_id = st.session_state.get("display_order_id", 0)
   pdf.cell(0, 8, f"Order ID : {display_order_id}", ln=True)

   pdf.cell(0, 8, f"Customer Name : {customer_name}", ln=True)
   pdf.multi_cell(0, 8, f"Customer Address : {customer_address}")
   
   pdf.ln(1)
   pdf.set_font("Arial", size=12)  
   pdf.cell(0, 8, f"Date & Time : {bill_datetime}", ln=True)

   pdf.ln(3)
   pdf.cell(0, 8, "-" * 40, ln=True)

   subtotal = 0
   for i in st.session_state["bill_items"]:
       line = f"{i['item']} ({i['variant']}) : {i['price']} x {i['quantity']} = Rs.{i['total']}"
       pdf.cell(0, 8, line, ln=True)
       subtotal += i['total']      
   # GST Calculations
   gst_percent = st.session_state.get("gst_percent", 0)
   gst_amount = (subtotal * gst_percent) / 100
   grand_total = subtotal + gst_amount      
   pdf.ln(2)
   pdf.cell(0, 8, "-"*40, ln=True)
   
   # Financial Summary
   pdf.set_font("Arial", size=11)
   pdf.cell(0, 8, f"Subtotal : Rs.{subtotal:.2f}", ln=True)
   if gst_percent > 0:
       pdf.cell(0, 8, f"GST ({gst_percent}%) : Rs.{gst_amount:.2f}", ln=True)
   
   pdf.set_font("Arial", "B", 13)
   pdf.cell(0, 10, f"TOTAL Bill : Rs.{grand_total:.2f}", ln=True)
   pdf.ln(3)
   pdf.set_font("Arial", "B", 12)
   pdf.cell(0, 8, f"Payment Method: {st.session_state.get('payment_method','')}", ln=True)

   pdf.ln(5)
   pdf.cell(0, 8, "Thank you, Visit again!", ln=True, align="C")
   
   safe_name = customer_name.replace(" ", "_")
   display_order_id = st.session_state.get("display_order_id", 0)
   file_name = f"bill_{safe_name}_{display_order_id}.pdf"

   st.markdown(
    f"### 💳 Payment Method: **{st.session_state.get('payment_method', 'N/A')}**"
    )

   print(f"Bill saved as {file_name}")

   if st.button("Save PDF"):
     st.session_state["customer_name"] = customer_name
     pdf.output(file_name)

     st.success("Bill saved to your system!")




















