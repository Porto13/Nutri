import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from google import genai  # <--- THIS IS THE NEW LIBRARY
import json
import uuid
import time
from datetime import datetime, date

# -----------------------------------------------------------------------------
# 1. CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="NutriComp", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def safe_float(val, default=0.0):
    if val is None or val == "": return default
    try: return float(val)
    except: return default

def safe_int(val, default=0):
    if val is None or val == "": return default
    try: return int(float(val))
    except: return default

# -----------------------------------------------------------------------------
# 3. CONNECTIONS
# -----------------------------------------------------------------------------
SHEET_ID = "1_9K1IT3zaDGNKfxwnnSIe7L881wJWVdztIwGci3B0vg"

def get_db_connection():
    if "gcp_service_account" not in st.secrets: return None
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def get_main_sheet(client):
    return client.open_by_key(SHEET_ID).sheet1

def get_gemini_response(prompt, image=None, json_mode=False):
    """Call Gemini API using the NEW google-genai SDK."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "ERROR_NO_KEY"
    
    try:
        # Initialize the new Client
        client = genai.Client(api_key=api_key)
        
        contents = [prompt]
        if image:
            contents.append(image)
            
        config = {'response_mime_type': 'application/json'} if json_mode else None

        # The New Syntax
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=contents,
            config=config
        )
        return response.text
    except Exception as e:
        return f"ERROR_DETAILS: {str(e)}"

# -----------------------------------------------------------------------------
# 4. STYLING
# -----------------------------------------------------------------------------
THEME_BG = "#0f172a"
THEME_CARD_BG = "rgba(30, 41, 59, 0.5)"
THEME_BORDER = "rgba(51, 65, 85, 0.5)"
ACCENT_EMERALD = "#10b981"
ACCENT_AMBER = "#f59e0b"
ACCENT_INDIGO = "#6366f1"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Outfit:wght@400;700;900&display=swap');
    .stApp {{ background-color: {THEME_BG}; font-family: 'Inter', sans-serif; }}
    h1, h2, h3, h4, h5, h6 {{ font-family: 'Outfit', sans-serif !important; font-weight: 800 !important; color: #f8fafc !important; }}
    p, label, span, div {{ color: #cbd5e1; }}
    .glass-card {{
        background: {THEME_CARD_BG};
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid {THEME_BORDER}; border-radius: 1.5rem; padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    .progress-container {{ background-color: #1e293b; border-radius: 999px; height: 0.75rem; width: 100%; overflow: hidden; position: relative; }}
    .progress-bar {{ height: 100%; border-radius: 999px; transition: width 1s ease-in-out; position: relative; }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. DATA LOGIC
# -----------------------------------------------------------------------------
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "Dashboard"

def fetch_all_users():
    client = get_db_connection()
    if not client: return []
    try: return get_main_sheet(client).get_all_records()
    except: return []

def register_user(username, password):
    client = get_db_connection()
    if not client: return False, "DB Error"
    try:
        sheet = get_main_sheet(client)
        records = sheet.get_all_records()
        for r in records:
            if str(r.get('Username')).lower() == username.lower(): return False, "Username taken."
        
        new_id = f"u_{str(uuid.uuid4())[:6]}"
        row = [new_id, username, password, 2000, 150, 200, 20, 50, 25, 30, 2000, 3000, 15, "Bronze", 1.0, 0, 0, 0, 25, "Male", 70, 175, 1.2, "Maintain", "metric", "No"]
        sheet.append_row(row)
        return True, "Registered! Pending Admin Approval."
    except Exception as e: return False, f"Error: {e}"

def log_food_to_sheet(user_id, entry_data):
    client = get_db_connection()
    if not client: return
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Food_Logs")
        row = [
            entry_data.get('Log_ID'), entry_data.get('Timestamp'), entry_data.get('Date_Ref'), 
            user_id, entry_data.get('Meal_Name'), entry_data.get('Calories'), 
            entry_data.get('Protein'), entry_data.get('Carbs'), entry_data.get('Saturated_Fat'),
            entry_data.get('Unsaturated_Fat'), entry_data.get('Fiber'), entry_data.get('Sugar'),
            entry_data.get('Sodium'), entry_data.get('Potassium'), entry_data.get('Iron')
        ]
        sheet.append_row(row)
    except: st.error("Log Error: 'Food_Logs' tab might be missing in Sheet.")

def get_today_logs(user_id):
    client = get_db_connection()
    if not client: return []
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Food_Logs")
        records = sheet.get_all_records()
        today = datetime.now().strftime("%Y-%m-%d")
        return [r for r in records if str(r['User_ID']) == str(user_id) and r['Date_Ref'] == today]
    except: return []

def update_user_targets_db(user_id, new_data):
    client = get_db_connection()
    if not client:
        st.session_state.user.update(new_data)
        return True
    try:
        sheet = get_main_sheet(client)
        cell = sheet.find(user_id)
        if not cell: return False
        
        row_num = cell.row
        headers = sheet.row_values(1)
        cells = []
        for key, val in new_data.items():
            if key in headers:
                col = headers.index(key) + 1
                cells.append(gspread.Cell(row_num, col, val))
        if cells: sheet.update_cells(cells)
        st.session_state.user.update(new_data)
        return True
    except: return False

# -----------------------------------------------------------------------------
# 6. UI PAGES
# -----------------------------------------------------------------------------
def render_rank_card(user):
    pts = safe_int(user.get('Rank_Points_Counter', 0))
    if pts > 450: tier, color, icon, max_p = 'Platinum', 'linear-gradient(to right, #22d3ee, #2563eb)', '💠', 1000
    elif pts > 250: tier, color, icon, max_p = 'Gold', 'linear-gradient(to right, #fde047, #d97706)', '🥇', 450
    elif pts > 100: tier, color, icon, max_p = 'Silver', 'linear-gradient(to right, #cbd5e1, #64748b)', '🥈', 250
    else: tier, color, icon, max_p = 'Bronze', 'linear-gradient(to right, #fb923c, #9a3412)', '🥉', 100
    
    pct = min((pts / max_p) * 100, 100)
    
    st.markdown(f"""
    <div class="glass-card">
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="position: relative;">
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed={user.get('Username')}" style="width: 80px; height: 80px; border-radius: 20px; object-fit: cover; border: 2px solid #334155;">
                <div style="position: absolute; bottom: -5px; right: -5px; font-size: 1.2rem;">{icon}</div>
            </div>
            <div style="flex: 1;">
                <h2>{user.get('Username')}</h2>
                <span style="color: {THEME_BG}; background: {color}; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 0.7rem;">{tier} TIER</span>
                <div class="progress-container" style="margin-top: 0.5rem;">
                    <div class="progress-bar" style="width: {pct}%; background: {color};"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-top: 5px;">
                    <span>{pts} PTS</span>
                    <span>{max_p - pts} to go</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_dashboard():
    user = st.session_state.user
    goal = safe_float(user.get('Calorie_Goal')) or 2000
    if goal == 0: st.warning("⚠️ Profile targets are defaults.")

    render_rank_card(user)
    st.write("") 

    logs = get_today_logs(user['User_ID'])
    totals = {k: sum(safe_float(l.get(k, 0)) for l in logs) for k in ['Calories', 'Protein', 'Carbs', 'Saturated_Fat', 'Unsaturated_Fat', 'Fiber', 'Sugar', 'Sodium', 'Potassium', 'Iron']}
    
    col1, col2 = st.columns([1, 2])
    with col1:
        pct = min((totals['Calories']/goal)*100, 100)
        st.markdown(f"""
        <div class="glass-card" style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
            <h4 style="color: #64748b; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 1rem;">ENERGY BALANCE</h4>
            <div style="position: relative; width: 140px; height: 140px; display: flex; align-items: center; justify-content: center;">
                 <svg viewBox="0 0 36 36" style="position: absolute; width: 100%; height: 100%; transform: rotate(-90deg);">
                    <path stroke-dasharray="{pct}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" stroke="{ACCENT_EMERALD}" stroke-width="3" fill="none" />
                </svg>
                <div style="z-index: 10;">
                    <div style="font-size: 1.8rem; font-weight: 900; color: white;">{int(totals['Calories'])}</div>
                    <div style="font-size: 0.7rem; color: #64748b;">/ {int(goal)} kcal</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f'<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='color: #64748b; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 1rem;'>NUTRIENT TALLY</h4>", unsafe_allow_html=True)
        m_cols = st.columns(3)
        metrics = [
            ("Protein", totals['Protein'], safe_float(user.get('Protein_Goal')) or 150, 'g'),
            ("Carbs", totals['Carbs'], safe_float(user.get('Carbs_Goal')) or 200, 'g'),
            ("Fiber", totals['Fiber'], safe_float(user.get('Fiber_Goal')) or 25, 'g'),
            ("Sat. Fat", totals['Saturated_Fat'], safe_float(user.get('Saturated_Fat_Goal')) or 20, 'g'),
            ("Unsat. Fat", totals['Unsaturated_Fat'], safe_float(user.get('Unsaturated_Fat_Goal')) or 50, 'g'),
            ("Sugar", totals['Sugar'], safe_float(user.get('Sugar_Goal')) or 30, 'g'),
            ("Sodium", totals['Sodium'], safe_float(user.get('Sodium_Goal')) or 2000, 'mg'),
            ("Potassium", totals['Potassium'], safe_float(user.get('Potassium_Goal')) or 3500, 'mg'),
            ("Iron", totals['Iron'], safe_float(user.get('Iron_Goal')) or 15, 'mg'),
        ]
        
        for i, (label, val, goal_val, unit) in enumerate(metrics):
            with m_cols[i % 3]:
                pct = min((val / goal_val) * 100, 100)
                color = ACCENT_EMERALD if pct <= 100 else "#f43f5e"
                st.markdown(f"""
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.7rem; font-weight: 700; margin-bottom: 0.25rem;">
                        <span style="color: #64748b;">{label}</span>
                        <span style="color: white;">{int(val)}/{int(goal_val)}{unit}</span>
                    </div>
                    <div style="height: 6px; width: 100%; background: #0f172a; border-radius: 99px;">
                        <div style="height: 100%; width: {pct}%; background: {color}; border-radius: 99px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="glass-card" style="margin-top: 1rem;"><h3 style="margin:0">Today\'s Logs</h3></div>', unsafe_allow_html=True)
    if logs:
        st.dataframe(pd.DataFrame(logs)[['Meal_Name', 'Calories', 'Protein', 'Carbs']], use_container_width=True, hide_index=True)

def render_food_logger():
    st.title("Add Food 🍎")
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            desc = st.text_area("Meal Description", placeholder="E.g. Large Caesar salad...", height=150)
        with col2:
            img_file = st.file_uploader("Add Photo", type=['jpg', 'png'])
            
        if st.button("Log & Analyze", type="primary", use_container_width=True):
            if not desc: st.warning("Describe your food.")
            else:
                with st.spinner("AI Analyzing..."):
                    img = None
                    if img_file:
                        try:
                            from PIL import Image
                            img = Image.open(img_file)
                        except: pass
                    
                    prompt = f"Analyze: '{desc}'. Return JSON: Meal_Name, Calories, Protein, Carbs, Saturated_Fat, Unsaturated_Fat, Fiber, Sugar, Sodium, Potassium, Iron. Numbers only. NO MARKDOWN."
                    res_text = get_gemini_response(prompt, img, json_mode=True)
                    
                    if "ERROR" in str(res_text):
                        st.error(f"AI Failed: {res_text}")
                    else:
                        try:
                            clean_res = res_text.replace("```json", "").replace("```", "").strip()
                            data = json.loads(clean_res)
                            data.update({'Log_ID': str(uuid.uuid4())[:8], 'Timestamp': time.time(), 'Date_Ref': datetime.now().strftime("%Y-%m-%d")})
                            log_food_to_sheet(st.session_state.user['User_ID'], data)
                            st.success(f"Logged: {data.get('Meal_Name')}")
                            time.sleep(1)
                            st.session_state.active_tab = "Dashboard"
                            st.rerun()
                        except Exception as e:
                            st.error("AI Parse Error. Raw Output:")
                            st.code(res_text)
                            
        st.markdown('</div>', unsafe_allow_html=True)

def render_leaderboard():
    st.title("Global Arena Sync 🔥")
    st.markdown(f"""
    <div class="glass-card" style="border: 1px solid {ACCENT_AMBER}; margin-bottom: 2rem;">
        <h3 style="color: {ACCENT_AMBER}; margin:0;">⚔️ Daily Quest</h3>
        <p style="margin:0;">Log 3 meals with >20g Protein to earn a Streak Bonus!</p>
    </div>
    """, unsafe_allow_html=True)
    
    users = fetch_all_users()
    users_clean = []
    for u in users:
        u['Rank_Points_Counter'] = safe_int(u.get('Rank_Points_Counter', 0))
        users_clean.append(u)
    
    lb = sorted(users_clean, key=lambda x: x['Rank_Points_Counter'], reverse=True)
    
    for i, p in enumerate(lb):
        is_me = p.get('Username') == st.session_state.user['Username']
        bg = "rgba(99, 102, 241, 0.1)" if is_me else "rgba(30, 41, 59, 0.3)"
        border = f"1px solid {ACCENT_INDIGO}" if is_me else "none"
        
        st.markdown(f"""
        <div style="background: {bg}; border: {border}; border-radius: 1rem; padding: 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 1.2rem; font-weight: 900; color: #64748b;">#{i+1}</span>
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed={p.get('Username')}" style="width: 40px; height: 40px; border-radius: 50%;">
                <span style="font-weight: 700;">{p.get('Username')}</span>
            </div>
            <span style="font-weight: 900; color: white;">{p.get('Rank_Points_Counter')} PTS</span>
        </div>
        """, unsafe_allow_html=True)

def render_profile_settings():
    user = st.session_state.user
    col1, col2 = st.columns([3, 1])
    with col1: st.title("Identity Matrix 👤")
    with col2: edit_mode = st.toggle("Edit Mode")

    if edit_mode:
        with st.form("profile"):
            c1, c2, c3 = st.columns(3)
            ng = {}
            ng['Calorie_Goal'] = c1.number_input("Calories", value=int(safe_float(user.get('Calorie_Goal')) or 2000))
            ng['Protein_Goal'] = c2.number_input("Protein", value=int(safe_float(user.get('Protein_Goal')) or 150))
            ng['Carbs_Goal'] = c3.number_input("Carbs", value=int(safe_float(user.get('Carbs_Goal')) or 200))
            if st.form_submit_button("Save"):
                update_user_targets_db(user['User_ID'], ng)
                st.rerun()
    else:
        st.markdown(f"""
        <div class="glass-card">
            <h4>Current Targets</h4>
            <div style="display: flex; gap: 2rem; margin-top: 1rem;">
                <div>
                    <span style="display:block; font-size:0.7rem; color:#64748b;">CALORIES</span>
                    <span style="font-weight:800; color:white;">{int(safe_float(user.get('Calorie_Goal')) or 2000)} kcal</span>
                </div>
                <div>
                    <span style="display:block; font-size:0.7rem; color:#64748b;">PROTEIN</span>
                    <span style="font-weight:800; color:white;">{int(safe_float(user.get('Protein_Goal')) or 150)} g</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_login():
    st.title("NutriComp Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        users = fetch_all_users()
        found = next((x for x in users if str(x.get('Username')) == u and str(x.get('Password')) == p), None)
        if found:
            if "y" in str(found.get("Approved", "No")).lower():
                st.session_state.user = found
                st.rerun()
            else: st.error("Account pending approval.")
        else: st.error("Invalid credentials.")

def main():
    if not st.session_state.user: render_login()
    else:
        with st.sidebar:
            st.title("NutriComp")
            for t in ["Dashboard", "Log Food", "Arena Sync", "Identity"]:
                if st.button(t): st.session_state.active_tab = t
                st.write("")
            if st.button("Logout"): 
                st.session_state.user = None
                st.rerun()
        
        if st.session_state.active_tab == "Dashboard": render_dashboard()
        elif st.session_state.active_tab == "Log Food": render_food_logger()
        elif st.session_state.active_tab == "Arena Sync": render_leaderboard()
        elif st.session_state.active_tab == "Identity": render_profile_settings()

if __name__ == "__main__":
    main()
