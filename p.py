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
db = mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4Er7E7yAa5CmneH.root",
        password="JubMX8vnCyJqhX96",
        database="cafe",
        ssl_verify_identity=True,
        ssl_ca="/etc/ssl/certs/ca-certificates.crt"
)
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

    full_path = os.path.join(IMAGE_DIR, os.path.basename(image_path))

    if os.path.exists(full_path):
        try:
            return Image.open(full_path)
        except:
            pass

    return Image.new("RGB", (300, 300), (200, 200, 200))


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

    
if st.session_state.get("email"):
    cursor.execute("""
        SELECT id, name, image, variants, available, email
        FROM menu_items
        WHERE available=1 AND email=%s
    """, (st.session_state["email"],))
    db_menu = cursor.fetchall()

if st.session_state["page"] == "menu":
    # --- UPDATED CSS (Removed Horizontal Forced Scroll) ---
    st.markdown("""
    <style>
        /* Keep the pill shape for buttons */
        .stButton > button {
            border-radius: 20px !important; 
            padding: 5px 15px !important;
            border: 1px solid #ddd !important;
        }
                
        .fixed-top {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background: #f5f3f0;
            z-index: 1000;
            padding: 10px 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* Fixed Footer Styling */
        .mobile-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: white;
            padding: 10px;
            z-index: 1000;
            border-top: 1px solid #ddd;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # --- 1. RENDER THE CATEGORY SELECTOR ---
    with st.container():
        # 1. RENDER STICKY HEADER AREA
        # We use an empty markdown with a class 'sticky-header' to let CSS find this container
        st.markdown(f"""
            <div class="fixed-top">
                <div style="font-size:18px; font-weight:bold; margin-bottom:10px;">
                    WELCOME TO <span style="color:#a5512c;">{st.session_state.get('menu_title', 'Jay Vachraj')}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        unique_cats = sorted(list(set([item['name'] for item in db_menu])))
        cat_options = ["All"] + unique_cats
        search_query = st.text_input("🔍 Search", placeholder="Search items...", key="search_input", label_visibility="collapsed")
        
        # Using a selectbox or simple buttons without the "flex-nowrap" CSS 
        # allows them to behave normally.
        selected_cat = st.radio("Categories", cat_options, horizontal=True, label_visibility="collapsed")
        st.session_state.selected_category = selected_cat

    # --- 2. FILTER AND FLATTEN DATA ---
    display_items = []
    for item in db_menu:
        if (selected_cat == "All" or item['name'] == selected_cat) and \
           (not search_query or search_query.lower() in item["name"].lower()):
            
            import json
            variants = json.loads(item.get("variants") or "[]")
            if not variants: variants = [{"name": "Standard", "price": 0}]
            
            for v in variants:
                display_items.append({
                    "id": item["id"], "name": item["name"], "image": item["image"],
                    "v_name": v["name"], "v_price": v["price"]
                })

    # --- 3. RENDER MENU ITEMS (Single Column - No Scroll) ---
    for item in display_items:
        # Each item gets its own container, creating a natural vertical list
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.write("DB Image Path:", item["image"])

                full_path = os.path.join(BASE_DIR, item["image"])
                st.write("Server Path:", full_path)
                st.write("File Exists:", os.path.exists(full_path))

                img = load_image(item["image"])
                st.image(img, use_container_width=True)
            
            with c2:
                st.markdown(f"""
                    <div style="line-height: 1.2;">
                        <strong style="font-size: 14px;">{item['v_name']}</strong><br>
                        <span style="color:gray; font-size:11px;">{item['name']}</span>
                    </div>
                    <div style="font-weight:bold; font-size:16px; margin-top: 5px;">₹{item['v_price']}</div>
                """, unsafe_allow_html=True)
                
                # Existing Qty Logic
                existing = next((x for x in st.session_state["items"] if x["menu_id"] == item["id"] and x["variant"] == item['v_name']), None)
                st.markdown("<p style='font-size:12px; margin-top:10px; margin-bottom:0px;'>Qty:</p>", unsafe_allow_html=True)
                qty = st.number_input(
                    "Qty", 
                    min_value=0, 
                    step=1, 
                    value=existing["quantity"] if existing else 0, 
                    key=f"q_{item['id']}_{item['v_name']}", 
                    label_visibility="collapsed"
                )
                
                # Update Session State
                if qty > 0:
                    if existing:
                        existing["quantity"] = qty
                        existing["total"] = qty * item['v_price']
                    else:
                        st.session_state["items"].append({
                            "item": item["name"], "menu_id": item["id"], "price": item['v_price'],
                            "quantity": qty, "total": qty * item['v_price'], "variant": item['v_name'], "image": item["image"]
                        })
                elif existing:
                    st.session_state["items"] = [x for x in st.session_state["items"] if not (x["menu_id"] == item["id"] and x["variant"] == item['v_name'])]

    # --- 4. RENDER FIXED FOOTER ---
    total_qty = sum(x["quantity"] for x in st.session_state["items"])
    total_price = sum(x["total"] for x in st.session_state["items"])

    st.markdown('<div class="mobile-footer">', unsafe_allow_html=True)
    if total_qty > 0:
        if st.button(f"🛒 View Cart ({total_qty}) · ₹{total_price}", use_container_width=True, type="primary"):
            st.session_state["page"] = "cart"
            st.rerun()
    else:
        st.button("🛒 Your Cart is Empty", use_container_width=True, disabled=True)
    st.markdown('</div>', unsafe_allow_html=True)
        
    
elif st.session_state["page"] == "cart":
    st.markdown("<h2 style='text-align: center;'>🛒 Your Shopping Cart</h2>", unsafe_allow_html=True)
    
    if not st.session_state["items"]:
        st.info("Your cart is empty!")
        if st.button("Go to Menu"):
            st.session_state["page"] = "menu"
            st.rerun()
    else:
        # Loop through items
        for i in st.session_state["items"].copy():
            # Create a "Card" for each item using a container
            with st.container(border=True):
                # We use 2 columns for the top row: Image + Details/Price
                top_col1, top_col2 = st.columns([1, 3])
                
                with top_col1:
                    if i["image"]:
                        img = load_image(i["image"])
                        st.image(img, use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/100", use_container_width=True)

                with top_col2:
                    st.markdown(f"**{i['item']}**")
                    st.caption(f"Variant: {i['variant']} | Price: {i['price']}₹")
                
                # We use 2 columns for the bottom row: Quantity + Remove button
                # This stacks perfectly on mobile
                bot_col1, bot_col2 = st.columns([3, 1])
                
                with bot_col1:
                    new_qty = st.number_input(
                        "Qty",
                        min_value=0,
                        value=i["quantity"],
                        key=f"cart_{i['menu_id']}_{i['variant']}",
                        label_visibility="collapsed" # Hides label to save vertical space
                    )
                    i["quantity"] = new_qty
                    i["total"] = new_qty * i["price"]
                
                with bot_col2:
                    if st.button("🗑️", key=f"remove_{i['menu_id']}_{i['variant']}", use_container_width=True):
                        st.session_state["items"].remove(i)
                        st.rerun()

                # Logic check for zero quantity
                if new_qty == 0:
                    st.session_state["items"].remove(i)
                    st.rerun()

        # --- Footer Section ---
        st.divider()
        total = sum(i["total"] for i in st.session_state["items"])
        st.markdown(f"### Total Amount: <span style='color:green'>{total}₹</span>", unsafe_allow_html=True)

        # Checkout Form
        with st.expander("👤 Checkout Details", expanded=True):
            st.session_state["customer_name"] = st.text_input("Name", st.session_state.get("customer_name", ""))
            st.session_state["table_no"] = st.number_input("Table #", min_value=0, value=st.session_state.get("table_no", 1))
            st.session_state["customer_address"] = st.text_area("Notes/Address", st.session_state.get("customer_address", ""))

        # Action Buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("➕ Add More", use_container_width=True):
                st.session_state["page"] = "menu"
                st.rerun()
        with btn_col2:
            if st.button("🧹 Clear", use_container_width=True):
                st.session_state["items"] = []
                st.rerun()

        if st.button("✅ Confirm Order", type="primary", use_container_width=True):
            if not st.session_state["customer_name"].strip():
                st.warning("Please enter your name")
            else:
                st.session_state["bill_items"] = st.session_state["items"].copy()
                st.session_state["total_amount"] = total
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



