import streamlit as st
import sqlite3
import os
import pandas as pd
import math
from datetime import datetime

# 📱 Mobile & Tablet View နှစ်မျိုးလုံးမှာ လှပအောင် Layout ညှိခြင်း
st.set_page_config(page_title="Ultimate KTV POS System", page_icon="🎙️", layout="centered")

# ==================== [ 🗄️ OFFLINE DATABASE CONFIG ] ====================
db_path = "ktv_ultimate_production.db"

def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 1. အခန်းများ Table
    c.execute('''CREATE TABLE IF NOT EXISTS rooms 
                 (id TEXT PRIMARY KEY, name TEXT, rate INTEGER, status TEXT, check_in TEXT)''')
    # 2. လက်ရှိမှာယူမှုများ Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, item_name TEXT, price INTEGER, quantity INTEGER)''')
    # 3. ရောင်းရငွေ စာရင်းမှတ်တမ်း Table
    c.execute('''CREATE TABLE IF NOT EXISTS sales_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, duration INTEGER, room_charge INTEGER, items_charge INTEGER, grand_total INTEGER, date_time TEXT)''')
    # 4. ပြေစာ Settings Table
    c.execute('''CREATE TABLE IF NOT EXISTS receipt_settings 
                 (id INTEGER PRIMARY KEY, shop_name TEXT, phone TEXT, address TEXT, footer_text TEXT, discount_pct REAL, tax_pct REAL)''')
    # 5. 🍔 Menu Items + Inventory Table (Stock ပါဝင်အောင် Upgrade လုပ်ထားသည် ဆစ်)
    c.execute('''CREATE TABLE IF NOT EXISTS menu_items 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT UNIQUE, price INTEGER, stock_qty INTEGER)''')
    
    # Default အခန်းများ ထည့်ခြင်း
    c.execute("SELECT COUNT(*) FROM rooms")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO rooms VALUES (?, ?, ?, ?, ?)", [
            ("V01", "VIP Room 1", 30000, "Available", None),
            ("V02", "VIP Room 2", 30000, "Available", None),
            ("R01", "Standard Room 1", 15000, "Available", None),
            ("R02", "Standard Room 2", 15000, "Available", None)
        ])
        
    # Default Receipt Settings ထည့်ခြင်း
    c.execute("SELECT COUNT(*) FROM receipt_settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO receipt_settings VALUES (1, '🎙️ KTV BAR & LOUNGE', '09-123456789', 'Yangon, Myanmar', 'လာရောက်အားပေးမှုကို ကျေးဇူးတင်ပါသည်', 0.0, 0.0)")
        
    # Default မီနူးများနှင့် Stock ပမာဏ ထည့်ခြင်း
    c.execute("SELECT COUNT(*) FROM menu_items")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO menu_items (item_name, price, stock_qty) VALUES (?, ?, ?)", [
            ("Heineken Beer", 4500, 50),
            ("Tiger Beer", 4000, 100),
            ("Chicken Wings", 8000, 30),
            ("French Fries", 5000, 40),
            ("Coca Cola", 1500, 120)
        ])
        
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(db_path)

def load_menu_items():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_name, price, stock_qty FROM menu_items")
    rows = c.fetchall()
    conn.close()
    # နာမည်၊ စျေးနှုန်း နဲ့ Stock ကို ပို့ပေးမယ် ဆစ်
    return {row[0]: {"price": row[1], "stock": row[2]} for row in rows}

# ---- SESSION STATES FOR SECURITY ----
if "role" not in st.session_state:
    st.session_state.role = None
if "receipt_popup" not in st.session_state:
    st.session_state.receipt_popup = None

# ==================== [ 👥 SECURITY LOGIN GATE ] ====================
if st.session_state.role is None:
    st.subheader("🔑 KTV POS Login System")
    role_choice = st.radio("ဝင်ရောက်မည့် အဆင့်အတန်းကို ရွေးပါ:", ["ကောင်တာ ဝန်ထမ်း (Staff)", "မန်နေဂျာ (Manager)"])
    
    if role_choice == "မန်နေဂျာ (Manager)":
        password = st.text_input("မန်နေဂျာ စကားဝှက်ကို ရိုက်ထည့်ပါ:", type="password")
        if st.button("🔑 Login ဝင်မည်", use_container_width=True):
            if password == "1234":  # Default Password ပါ ဆစ်
                st.session_state.role = "Manager"
                st.rerun()
            else:
                st.error("❌ စကားဝှက် မှားယွင်းနေပါသည် ဆစ်!")
    else:
        if st.button("🚪 ဝန်ထမ်းအဖြစ် အသင့်ဝင်မည်", use_container_width=True):
            st.session_state.role = "Staff"
            st.rerun()
    st.stop()

# ---- LOGOUT BUTTON ON TOP ----
col_title, col_logout = st.columns([3, 1])
with col_title:
    st.caption(f"👤 လက်ရှိဝင်ထားသူ: **{st.session_state.role}**")
with col_logout:
    if st.button("🚪 Logout", type="secondary", use_container_width=True):
        st.session_state.role = None
        st.session_state.receipt_popup = None
        st.rerun()

# 🔄 Role အလိုက် Tab စနစ်ကို ခွဲခြားပြသခြင်း
if st.session_state.role == "Manager":
    tab_pos, tab_dash, tab_set = st.tabs(["🎮 ကောင်တာစနစ် (POS)", "📊 အရောင်းစနစ် (Dashboard)", "⚙️ Settings & Inventory"])
else:
    tab_pos, = st.tabs(["🎮 ကောင်တာစနစ် (POS)"]) # ဝန်ထမ်းဆိုရင် Dashboard နဲ့ Settings လုံးဝ မမြင်ရဘူး ဆစ်

# ==================== [ 🎮 TAB 1: POS SYSTEM (Staff + Manager) ] ====================
with tab_pos:
    if st.session_state.receipt_popup:
        with st.container(border=True):
            st.markdown("### 🧾 CUSTOMER BILL RECEIPT")
            st.code(st.session_state.receipt_popup, language="text")
            if st.button("🖨️ ပြေစာ ပရင့်ထုတ်မည် (Print Receipt)", type="primary", use_container_width=True):
                st.components.v1.html(f"<script>window.print();</script>", height=0)
            if st.button("❌ ပြေစာ ပိတ်မည်", type="secondary", use_container_width=True):
                st.session_state.receipt_popup = None
                st.author = None
                st.rerun()
        st.divider()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM rooms")
    rooms_data = c.fetchall()

    st.subheader("🛎️ အခန်းများ စာရင်းနှင့် Live အခြေအနေ")
    for r_id, r_name, r_rate, r_status, r_check_in in rooms_data:
        is_occupied = r_status == "Occupied"
        
        if is_occupied:
            start_time = datetime.strptime(r_check_in, "%Y-%m-%d %H:%M:%S")
            minutes = max(int((datetime.now() - start_time).total_seconds() // 60), 1)
            billable_hours = math.ceil(minutes / 60)
            room_charge = billable_hours * r_rate
            
            c.execute("SELECT id, item_name, quantity, price FROM orders WHERE room_id=?", (r_id,))
            ordered_items = c.fetchall()
            
            items_charge = sum(item[2] * item[3] for item in ordered_items)
            sub_total = room_charge + items_charge
            
            with st.container(border=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"### 🔴 {r_name} ({r_id})")
                    st.caption(f"🕒 ဖွင့်ချိန်: {r_check_in[11:16]} ({minutes} မိနစ်သုံးပြီး - `{billable_hours}` နာရီစာ)")
                    
                    if ordered_items:
                        st.markdown("**🍟 မှာထားသော မီနူးများ:**")
                        for order_id, name, qty, price in ordered_items:
                            st.markdown(f"• {name} x`{qty}` ({price * qty:,} MMK)")
                            
                            ec1, ec2, ec3, _ = st.columns([1, 1, 1, 4])
                            with ec1:
                                if st.button("➕", key=f"p_{order_id}_{r_id}"):
                                    # Inventory Check အရင်လုပ်မယ် ဆစ်
                                    items_cfg = load_menu_items()
                                    if items_cfg[name]["stock"] > 0:
                                        c.execute("UPDATE orders SET quantity = quantity + 1 WHERE id=?", (order_id,))
                                        c.execute("UPDATE menu_items SET stock_qty = stock_qty - 1 WHERE item_name=?", (name,))
                                        conn.commit()
                                        st.rerun()
                                    else: st.error("❌ Stock မလောက်တော့ပါ!")
                            with ec2:
                                if st.button("➖", key=f"m_{order_id}_{r_id}"):
                                    if qty > 1:
                                        c.execute("UPDATE orders SET quantity = quantity - 1 WHERE id=?", (order_id,))
                                    else:
                                        c.execute("DELETE FROM orders WHERE id=?", (order_id,))
                                    c.execute("UPDATE menu_items SET stock_qty = stock_qty + 1 WHERE item_name=?", (name,))
                                    conn.commit()
                                    st.rerun()
                            with ec3:
                                if st.button("❌", key=f"d_{order_id}_{r_id}"):
                                    c.execute("DELETE FROM orders WHERE id=?", (order_id,))
                                    c.execute("UPDATE menu_items SET stock_qty = stock_qty + ? WHERE item_name=?", (qty, name))
                                    conn.commit()
                                    st.rerun()
                    else:
                        st.caption("🍟 မှာယူထားသော မီနူး မရှိသေးပါ")
                        
                    st.markdown(f"**လက်ရှိကျသင့်ငွေ:** `{sub_total:,} MMK`")
                
                with col2:
                    st.write("") 
                    if st.button("ဘီလ်ပိတ်မည်", key=f"close_{r_id}", type="primary", use_container_width=True):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute("SELECT shop_name, phone, address, footer_text, discount_pct, tax_pct FROM receipt_settings WHERE id=1")
                        cfg_name, cfg_phone, cfg_address, cfg_footer, cfg_disc, cfg_tax = c.fetchone()
                        
                        discount_amount = round(sub_total * (cfg_disc / 100))
                        tax_amount = round((sub_total - discount_amount) * (cfg_tax / 100))
                        grand_total = sub_total - discount_amount + tax_amount
                        
                        item_lines = ""
                        for _, name, qty, price in ordered_items:
                            sub = price * qty
                            item_lines += f"{name[:14].ljust(14)} x{qty}   {sub:,} MMK\n"
                        
                        receipt_template = f"""
=================================
     {cfg_name.center(28)}
=================================
ဖုန်း   : {cfg_phone}
လိပ်စာ : {cfg_address}
ရက်စွဲ : {now_str}
အခန်း  : {r_name} ({r_id})
အသုံးပြုချိန်: {minutes} မိနစ် ({billable_hours} နာရီစာ)
---------------------------------
၁။ အခန်းခကျသင့်ငွေ : {room_charge:,} MMK
---------------------------------
၂။ သုံးဆောင်ခဲ့သော မီနူးများ:
{item_lines if item_lines else "မှာယူထားသော အစားအသောက်မရှိပါ\n"}
---------------------------------
စုစုပေါင်း (Subtotal) : {sub_total:,} MMK
လျှော့စျေး (Discount {cfg_disc}%) : -{discount_amount:,} MMK
အခွန် (Tax {cfg_tax}%)      : +{tax_amount:,} MMK
=================================
🎁 အားလုံးပေါင်းကျသင့်ငွေ: {grand_total:,} MMK
=================================
   ✨ {cfg_footer.center(26)} ✨
=================================
"""
                        st.session_state.receipt_popup = receipt_template
                        
                        c.execute("INSERT INTO sales_history (room_id, duration, room_charge, items_charge, grand_total, date_time) VALUES (?, ?, ?, ?, ?, ?)",
                                  (r_id, minutes, room_charge, items_charge, grand_total, now_str))
                        c.execute("UPDATE rooms SET status='Available', check_in=NULL WHERE id=?", (r_id,))
                        c.execute("DELETE FROM orders WHERE room_id=?", (r_id,))
                        conn.commit()
                        st.rerun()
        else:
            with st.container(border=False):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**🟢 {r_name} ({r_id})** — `{r_rate:,} MMK/hr`")
                with col2:
                    if st.button("အခန်းဖွင့်ရန်", key=f"open_{r_id}", use_container_width=True):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute("UPDATE rooms SET status='Occupied', check_in=? WHERE id=?", (now_str, r_id))
                        conn.commit()
                        st.rerun()

    st.divider()

    # 📦 Inventory ဆွဲယူပြသခြင်း ကဏ္ဍ
    CURRENT_ITEMS = load_menu_items()

    st.subheader("🍟 အစားအသောက်/ဘီယာ မှာယူရန်")
    
    # ⚠️ [Stock Low Warning Alert] လက်ကျန်နည်းတာရှိရင် ဝန်ထမ်းတွေကို သတိပေးမည့်စနစ်
    for name, data in CURRENT_ITEMS.items():
        if data["stock"] <= 5:
            st.warning(f"⚠️ **{name}** လက်ကျန် နည်းနေပါသည်! ({data['stock']} လုံးသာ ကျန်တော့သည် ဆစ်)")

    c.execute("SELECT id FROM rooms WHERE status='Occupied'")
    active_rooms = [r[0] for r in c.fetchall()]

    if active_rooms and CURRENT_ITEMS:
        with st.form("order_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([1, 1.5, 0.8])
            with col1: selected_room = st.selectbox("အခန်း", active_rooms)
            with col2: selected_item = st.selectbox("မီနူး (လက်ကျန်ပြထားသည်)", [f"{k} (Stock: {v['stock']})" for k, v in CURRENT_ITEMS.items()])
            with col3: quantity = st.number_input("Qty", min_value=1, value=1, step=1)
            
            if st.form_submit_button("မှာယူမှု စနစ်ထဲထည့်မည်", use_container_width=True):
                item_pure_name = selected_item.split(" (Stock:")[0]
                # Stock လောက်မလောက် စစ်မယ် ဆစ်
                if CURRENT_ITEMS[item_pure_name]["stock"] >= quantity:
                    c.execute("INSERT INTO orders (room_id, item_name, price, quantity) VALUES (?, ?, ?, ?)", 
                              (selected_room, item_pure_name, CURRENT_ITEMS[item_pure_name]["price"], quantity))
                    # 📦 Stock ထဲကနေ တန်းနှုတ်ချမယ်
                    c.execute("UPDATE menu_items SET stock_qty = stock_qty - ? WHERE item_name=?", (quantity, item_pure_name))
                    conn.commit()
                    st.toast(f"🛒 {item_pure_name} x{quantity} မှာယူမှု အောင်မြင်သည်!")
                    st.rerun()
                else:
                    st.error(f"❌ {item_pure_name} မှာယူရန် Stock မလောက်တော့ပါဘူး ဆစ်!")
    conn.close()

# ==================== [ 📊 TAB 2: DATE-WISE DASHBOARD (Manager Only) ] ====================
if st.session_state.role == "Manager":
    with tab_dash:
        st.subheader("📊 ရက်စွဲအလိုက် ရောင်းအား ခွဲခြမ်းစိတ်ဖြာချက် (Dashboard)")
        
        # 📅 [DATE-WISE FILTER] ရက်စွဲအလိုက် စစ်ထုတ်မည့် စနစ်သစ်
        col_d1, col_d2 = st.columns(2)
        with col_d1: start_date = st.date_input("စတင်မည့်ရက်", value=datetime.now())
        with col_d2: end_date = st.date_input("နောက်ဆုံးရက်", value=datetime.now())
        
        conn = get_db()
        df_sales = pd.read_sql_query("SELECT * FROM sales_history", conn)
        conn.close()
        
        if not df_sales.empty:
            # ရက်စွဲစာသားကို နှိုင်းယှဉ်လို့ရအောင် Pandas Datetime ပြောင်းခြင်း
            df_sales['just_date'] = pd.to_datetime(df_sales['date_time']).dt.date
            # Filter ညှပ်ချလိုက်မယ် ဆစ်
            df_filtered = df_sales[(df_sales['just_date'] >= start_date) & (df_sales['just_date'] <= end_date)]
            
            if not df_filtered.empty:
                t_revenue = df_filtered["grand_total"].sum()
                t_room = df_filtered["room_charge"].sum()
                t_items = df_filtered["items_charge"].sum()
                
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1: st.metric("💰 ရောင်းရငွေစုစုပေါင်း", f"{t_revenue:,} MMK")
                with m_col2: st.metric("🛎️ အခန်းခရငွေစုစုပေါင်း", f"{t_room:,} MMK")
                with m_col3: st.metric("🍔 အစားအသောက်ရငွေ", f"{t_items:,} MMK")
                
                st.divider()
                st.markdown("**🛎️ အခန်းအလိုက် ဝင်ငွေရှာပေးနိုင်မှုဇယား**")
                room_sales = df_filtered.groupby("room_id")["grand_total"].sum()
                st.bar_chart(room_sales)
                
                st.divider()
                st.markdown("**📋 ဤရက်စွဲအတွင်း ရှင်းခဲ့သော ဘီလ်များ**")
                for index, row in df_filtered.iloc[::-1].iterrows():
                    st.markdown(f"📅 `{row['date_time'][:16]}` ➡️ အခန်း **{row['room_id']}** **+{row['grand_total']:,} MMK**")
            else:
                st.info("ရွေးချယ်ထားသော ရက်စွဲအတွင်း ဘီလ်ပိတ်ထားသည့် စာရင်းမရှိသေးပါ ဆစ်။")
        else:
            st.info("စနစ်တစ်ခုလုံးတွင် အရောင်းမှတ်တမ်း လုံးဝ မရှိသေးပါ ဆစ်။")

# ==================== [ ⚙️ TAB 3: SETTINGS & INVENTORY (Manager Only) ] ====================
if st.session_state.role == "Manager":
    with tab_set:
        st.subheader("📝 ပြေစာ အချက်အလက်များ ပြင်ဆင်ရန်")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT shop_name, phone, address, footer_text, discount_pct, tax_pct FROM receipt_settings WHERE id=1")
        s_name, s_phone, s_address, s_footer, s_disc, s_tax = c.fetchone()
        conn.close()
        
        with st.form("settings_form_tab"):
            edit_name = st.text_input("ဆိုင်နာမည် (Shop Name)", value=s_name)
            edit_phone = st.text_input("ဖုန်းနံပါတ် (Phone)", value=s_phone)
            edit_address = st.text_input("လိပ်စာ (Address)", value=s_address)
            edit_footer = st.text_input("အောက်ခြေ နှုတ်ခွန်းဆက်စာ (Footer Text)", value=s_footer)
            
            col_d, col_t = st.columns(2)
            with col_d: edit_disc = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=s_disc, step=1.0)
            with col_t: edit_tax = st.number_input("Tax (%)", min_value=0.0, max_value=100.0, value=s_tax, step=1.0)
            
            if st.form_submit_button("💾 ပြေစာ Setting သိမ်းဆည်းမည်", use_container_width=True):
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE receipt_settings SET shop_name=?, phone=?, address=?, footer_text=?, discount_pct=?, tax_pct=? WHERE id=1",
                          (edit_name, edit_phone, edit_address, edit_footer, edit_disc, edit_tax))
                conn.commit()
                conn.close()
                st.toast("✅ Settings သိမ်းဆည်းပြီးပါပြီ!")
                st.rerun()

        st.divider()
        
        # 📦 [INVENTORY MANAGEMENT AREA] မီနူးနှင့် စတော့အသစ် ထည့်မည့်နေရာ
        st.subheader("📦 မီနူးအသစ်နှင့် Stock ကုန်ပစ္စည်းလက်ကျန် စီမံခြင်း")
        
        with st.form("add_menu_form"):
            st.markdown("**➕ မီနူးအသစ်နှင့် အဝင် Stock သတ်မှတ်ရန်**")
            new_item_name = st.text_input("🍔 မီနူးအမည်သစ်")
            new_item_price = st.number_input("ဈေးနှုန်း (MMK)", min_value=0, value=1000, step=500)
            new_item_stock = st.number_input("စတင်မည့် အဝင် Stock အရေအတွက်", min_value=0, value=50, step=10)
            
            if st.form_submit_button("➕ မီနူးအသစ် ထည့်မည်", use_container_width=True):
                if new_item_name.strip() != "":
                    try:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("INSERT INTO menu_items (item_name, price, stock_qty) VALUES (?, ?, ?)", 
                                  (new_item_name.strip(), new_item_price, new_item_stock))
                        conn.commit()
                        conn.close()
                        st.toast(f"✅ {new_item_name} (Stock: {new_item_stock}) ထည့်ပြီးပါပြီ!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ ဤမီနူးအမည်မှာ ရှိပြီးသားဖြစ်သည်!")
                else: st.warning("⚠️ မီနူးအမည် ရိုက်ထည့်ပါ ဆစ်။")

        st.markdown("**🗑️ လက်ရှိ မီနူးများနှင့် Stock အရေအတွက် ပြင်ဆင်/ဖျက်ပစ်ရန်**")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, item_name, price, stock_qty FROM menu_items")
        all_menus = c.fetchall()
        conn.close()
        
        if all_menus:
            for m_id, m_name, m_price, m_stock in all_menus:
                m_col1, m_col2 = st.columns([3, 1])
                with m_col1:
                    st.write(f"🍔 **{m_name}** — `{m_price:,} MMK` | 📦 Stock လက်ကျန်: `{m_stock}` ခု")
                with m_col2:
                    if st.button("🗑️ ဖျက်မည်", key=f"del_menu_{m_id}", use_container_width=True):
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("DELETE FROM menu_items WHERE id=?", (m_id,))
                        conn.commit()
                        conn.close()
                        st.toast(f"🗑️ {m_name} ကို ဖျက်ပစ်လိုက်ပါပြီ!")
                        st.rerun()
        else:
            st.caption("စနစ်ထဲတွင် ဖျက်ရန် မီနူးမရှိသေးပါ ဆစ်။")