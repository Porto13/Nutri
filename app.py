import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import uuid
import time
from datetime import datetime, date

# -----------------------------------------------------------------------------
# 1. CONFIGURATION & ASSETS
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="NutriComp",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 1.5. HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def safe_float(val, default=0.0):
    """Safely converts a value to float, handling None, empty strings, and errors."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    """Safely converts a value to int."""
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

# -----------------------------------------------------------------------------
# 2. GOOGLE SHEETS CONNECTION
# -----------------------------------------------------------------------------

# CONSTANT SHEET ID
SHEET_ID = "1_9K1IT3zaDGNKfxwnnSIe7L881wJWVdztIwGci3B0vg"

def get_db_connection():
    """Connect to Google Sheets."""
    if "gcp_service_account" not in st.secrets:
        return None
        
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

def get_main_sheet(client):
    """Helper to get the specific worksheet by ID."""
    return client.open_by_key(SHEET_ID).sheet1

# Colors & Theme Constants
THEME_BG = "#0f172a"
THEME_CARD_BG = "rgba(30, 41, 59, 0.5)"
THEME_BORDER = "rgba(51, 65, 85, 0.5)"
ACCENT_CYAN = "#06b6d4"
ACCENT_EMERALD = "#10b981"
ACCENT_INDIGO = "#6366f1"
ACCENT_AMBER = "#f59e0b"

# -----------------------------------------------------------------------------
# 3. CUSTOM CSS
# -----------------------------------------------------------------------------

st.markdown(f"""
<style>
    /* Global Font & Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Outfit:wght@400;700;900&display=swap');
    
    .stApp {{
        background-color: {THEME_BG};
        font-family: 'Inter', sans-serif;
    }}
    
    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 800 !important;
        color: #f8fafc !important;
    }}
    
    p, label, span, div {{
        color: #cbd5e1;
    }}

    /* Custom Scrollbar */
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: #1e293b; }}
    ::-webkit-scrollbar-thumb {{ background: #475569; border-radius: 10px; }}

    /* Cards */
    .glass-card {{
        background: {THEME_CARD_BG};
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid {THEME_BORDER};
        border-radius: 1.5rem;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }}
    
    .glass-card:hover {{
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }}

    /* Inputs */
    .stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div > div {{
        background-color: #020617 !important;
        border: 1px solid #334155 !important;
        border-radius: 0.75rem !important;
        color: white !important;
        font-family: 'Inter', sans-serif;
    }}
    
    .stTextInput > div > div > input:focus {{
        border-color: {ACCENT_EMERALD} !important;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2) !important;
    }}

    /* Buttons */
    .stButton > button {{
        width: 100%;
        border-radius: 0.75rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.75rem 1rem;
        border: none;
        transition: all 0.2s;
    }}
    
    .primary-btn > button {{
        background: linear-gradient(135deg, {ACCENT_EMERALD}, #059669) !important;
        color: white !important;
        box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3);
    }}

    /* Progress Bar */
    .progress-container {{
        background-color: #1e293b;
        border-radius: 9999px;
        height: 0.75rem;
        width: 100%;
        overflow: hidden;
        position: relative;
    }}
    
    .progress-bar {{
        height: 100%;
        border-radius: 9999px;
        transition: width 1s ease-in-out;
        position: relative;
    }}
    
    .shimmer {{
        position: absolute;
        top: 0; left: 0; bottom: 0; right: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        transform: skewX(-20deg);
        animation: shimmer 2s infinite;
    }}
    
    @keyframes shimmer {{
        0% {{ transform: translateX(-100%) skewX(-20deg); }}
        100% {{ transform: translateX(200%) skewX(-20deg); }}
    }}

    /* Streamlit overrides */
    div[data-testid="stSidebar"] {{
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }}
    div[data-testid="stMetricValue"] {{
        color: white !important;
    }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. BACKEND LOGIC
# -----------------------------------------------------------------------------

# Initialize Session State
if 'user' not in st.session_state:
    st.session_state.user = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Dashboard"

def get_gemini_response(prompt, image=None, json_mode=False):
    """Call Gemini API."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: 
        return "ERROR_NO_KEY"
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        config = genai.GenerationConfig(response_mime_type="application/json") if json_mode else None
        
        parts = [prompt]
        if image:
            parts.insert(0, image)
            
        response = model.generate_content(parts, generation_config=config)
        return response.text
    except Exception as e:
        return f"ERROR_DETAILS: {str(e)}"

# DATA HELPERS

def fetch_all_users():
    """Fetch all users for leaderboard."""
    client = get_db_connection()
    if not client:
        return [] # Return empty list if no DB
    try:
        sheet = get_main_sheet(client)
        return sheet.get_all_records()
    except:
        return []

def register_user(username, password):
    """Register new user."""
    client = get_db_connection()
    if not client:
        return False, "Database not connected. Add GCP secrets."
        
    try:
        sheet = get_main_sheet(client)
        records = sheet.get_all_records()
        for r in records:
            if str(r.get('Username')).lower() == username.lower():
                return False, "Username taken."
        
        # Create new row
        new_id = f"u_{str(uuid.uuid4())[:6]}"
        # Headers: User_ID, Username, Password, Calorie_Goal, ... (Defaults)
        row = [
            new_id, username, password, 
            2000, 150, 200, 20, 50, 25, 30, 2000, 3000, 15, # Default Macros
            "Bronze", 1.0, 0, 0, 0, # Rank Data
            25, "Male", 70, 175, 1.2, "Maintain", "metric", # Demographics
            "No" # Approval Status
        ]
        sheet.append_row(row)
        return True, "Registration successful! Account pending admin approval."
    except Exception as e:
        return False, f"Error: {str(e)}"

def log_food_to_sheet(user_id, entry_data):
    client = get_db_connection()
    if not client:
        if 'mock_logs' not in st.session_state: st.session_state.mock_logs = []
        st.session_state.mock_logs.append(entry_data)
        return

    try:
        # Assuming Food_Logs is a separate sheet/tab. 
        # Safe approach: Open by key, then get worksheet by title "Food_Logs"
        sheet = client.open_by_key(SHEET_ID).worksheet("Food_Logs")
        
        row = [
            entry_data['Log_ID'], entry_data['Timestamp'], entry_data['Date_Ref'], 
            user_id, entry_data['Meal_Name'], entry_data['Calories'], 
            entry_data['Protein'], entry_data['Carbs'], entry_data['Saturated_Fat'],
            entry_data['Unsaturated_Fat'], entry_data['Fiber'], entry_data['Sugar'],
            entry_data['Sodium'], entry_data['Potassium'], entry_data['Iron']
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Log Error: {e}")

def get_today_logs(user_id):
    client = get_db_connection()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if not client:
        return [l for l in st.session_state.get('mock_logs', []) if l['Date_Ref'] == today_str]
        
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Food_Logs")
        records = sheet.get_all_records()
        return [r for r in records if str(r['User_ID']) == str(user_id) and r['Date_Ref'] == today_str]
    except:
        return []

def update_user_targets_db(user_id, new_data):
    """Updates user profile using the Submit Button in Identity Tab."""
    client = get_db_connection()
    if not client:
        st.session_state.user.update(new_data)
        return True

    try:
        sheet = get_main_sheet(client)
        # Find row by User_ID (Column 1)
        cell = sheet.find(user_id)
        if cell:
            r = cell.row
            headers = sheet.row_values(1)
            for key, val in new_data.items():
                if key in headers:
                    col_idx = headers.index(key) + 1
                    sheet.update_cell(r, col_idx, val)
            
            st.session_state.user.update(new_data)
            return True
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return False

# -----------------------------------------------------------------------------
# 5. UI COMPONENTS
# -----------------------------------------------------------------------------

def render_rank_card(user):
    pts = safe_int(user.get('Rank_Points_Counter', 0))

    if pts > 450:
        tier, next_tier, min_p, max_p, color, icon = 'Platinum', 'Max Rank', 450, 1000, 'linear-gradient(to right, #22d3ee, #2563eb)', '💠'
    elif pts > 250:
        tier, next_tier, min_p, max_p, color, icon = 'Gold', 'Platinum', 250, 450, 'linear-gradient(to right, #fde047, #d97706)', '🥇'
    elif pts > 100:
        tier, next_tier, min_p, max_p, color, icon = 'Silver', 'Gold', 100, 250, 'linear-gradient(to right, #cbd5e1, #64748b)', '🥈'
    else:
        tier, next_tier, min_p, max_p, color, icon = 'Bronze', 'Silver', 0, 100, 'linear-gradient(to right, #fb923c, #9a3412)', '🥉'

    pct = 100 if tier == 'Platinum' else ((pts - min_p) / (max_p - min_p)) * 100
    
    html = f"""
    <div class="glass-card" style="position: relative; overflow: hidden;">
        <div style="position: absolute; top: -50px; right: -50px; width: 200px; height: 200px; background: {color}; opacity: 0.15; filter: blur(60px); border-radius: 50%;"></div>
        <div style="display: flex; align-items: center; gap: 1.5rem; position: relative; z-index: 1;">
            <div style="position: relative;">
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed={user.get('Username', 'User')}" style="width: 80px; height: 80px; border-radius: 20px; border: 2px solid #334155; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5); object-fit: cover;">
                <div style="position: absolute; bottom: -5px; right: -5px; background: #0f172a; padding: 2px; border-radius: 8px; border: 1px solid #1e293b; font-size: 1.2rem;">
                    {icon}
                </div>
            </div>
            <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: end; margin-bottom: 0.5rem;">
                    <div>
                        <h2 style="margin: 0; font-size: 1.5rem; line-height: 1;">{user.get('Username', 'User')}</h2>
                        <span style="font-size: 0.75rem; font-weight: 800; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.1em;">{tier} Tier • {user.get('Current_Rank_Multiplier', 1.0)}x Boost</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 0.75rem; font-weight: 800; text-transform: uppercase; color: #64748b;">Next: {next_tier}</span>
                    </div>
                </div>
                
                <div class="progress-container">
                    <div class="progress-bar" style="width: {pct}%; background: {color};">
                        <div class="shimmer"></div>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
                    <span style="font-size: 0.75rem; font-weight: 600; color: #cbd5e1;">{pts} PTS</span>
                    <span style="font-size: 0.75rem; font-weight: 600; color: #64748b;">{max_p - pts} to go</span>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_dashboard():
    user = st.session_state.user
    
    # FIX: Only show warning if goal is explicitly 0 (Profile Incomplete check)
    goal_check = safe_float(user.get('Calorie_Goal', 0))
    if goal_check == 0:
        st.warning("⚠️ Profile Incomplete. Your nutrition targets are set to default.")
        if st.button("Set Nutrition Targets Now"):
            st.session_state.active_tab = "Identity"
            st.rerun()

    render_rank_card(user)
    st.write("") # Spacer

    logs = get_today_logs(user['User_ID'])
    
    # Aggregations using safe_float to prevent crashes
    totals = {k: sum(safe_float(l.get(k, 0)) for l in logs) for k in ['Calories', 'Protein', 'Carbs', 'Saturated_Fat', 'Unsaturated_Fat', 'Fiber', 'Sugar', 'Sodium', 'Potassium', 'Iron']}
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Default calorie goal to 2000 if 0 to avoid division by zero
        goal = safe_float(user.get('Calorie_Goal', 2000))
        if goal == 0: goal = 2000

        pct = min((totals['Calories']/goal)*100, 100)
        
        # Fixed: Added unsafe_allow_html=True
        st.markdown(f"""
        <div class="glass-card" style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
            <h4 style="color: #64748b; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 1rem;">Energy Balance</h4>
            <div style="position: relative; width: 160px; height: 160px; border-radius: 50%; border: 12px solid #1e293b; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <svg viewBox="0 0 36 36" style="position: absolute; width: 100%; height: 100%; transform: rotate(-90deg);">
                    <path stroke-dasharray="{pct}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" stroke="{ACCENT_EMERALD}" stroke-width="3" fill="none" />
                </svg>
                <span style="font-size: 2rem; font-weight: 900; color: white;">{int(totals['Calories'])}</span>
                <span style="font-size: 0.75rem; color: #64748b; font-weight: 700;">/ {int(goal)} kcal</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # Fixed: Added unsafe_allow_html=True
        st.markdown(f'<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='color: #64748b; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 1rem;'>Nutrient Tally</h4>", unsafe_allow_html=True)
        
        m_cols = st.columns(3)
        # Default values map to ensure we don't display 0/0
        defaults = {
            'Protein': 150, 'Carbs': 200, 'Fiber': 30,
            'Saturated_Fat': 20, 'Unsaturated_Fat': 50, 'Sugar': 30,
            'Sodium': 2300, 'Potassium': 3500, 'Iron': 18
        }
        
        metrics = [
            ("Protein", totals['Protein'], user.get('Protein_Goal',0), 'g'),
            ("Carbs", totals['Carbs'], user.get('Carbs_Goal',0), 'g'),
            ("Fiber", totals['Fiber'], user.get('Fiber_Goal',0), 'g'),
            ("Sat. Fat", totals['Saturated_Fat'], user.get('Saturated_Fat_Goal',0), 'g'),
            ("Unsat. Fat", totals['Unsaturated_Fat'], user.get('Unsaturated_Fat_Goal',0), 'g'),
            ("Sugar", totals['Sugar'], user.get('Sugar_Goal',0), 'g'),
            ("Sodium", totals['Sodium'], user.get('Sodium_Goal',0), 'mg'),
            ("Potassium", totals['Potassium'], user.get('Potassium_Goal',0), 'mg'),
            ("Iron", totals['Iron'], user.get('Iron_Goal',0), 'mg'),
        ]
        
        for i, (label, val, goal, unit) in enumerate(metrics):
            with m_cols[i % 3]:
                goal_f = safe_float(goal)
                # Fix: Default to reasonable values if goal is 0
                if goal_f == 0: 
                    # Map "Sat. Fat" to "Saturated_Fat" key in defaults
                    key = label.replace(". ", "_")
                    goal_f = defaults.get(key, 100)
                
                pct = min((val / goal_f) * 100, 100)
                color = ACCENT_EMERALD if pct <= 100 else "#f43f5e"
                
                # Fixed: Added unsafe_allow_html=True
                st.markdown(f"""
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; margin-bottom: 0.25rem;">
                        <span style="color: #64748b;">{label}</span>
                        <span style="color: white;">{int(val)}/{int(goal_f)}{unit}</span>
                    </div>
                    <div style="height: 6px; width: 100%; background: #0f172a; border-radius: 99px;">
                        <div style="height: 100%; width: {pct}%; background: {color}; border-radius: 99px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        # Fixed: Added unsafe_allow_html=True
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    # Fixed: Added unsafe_allow_html=True
    st.markdown(f"""
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {THEME_BORDER}; padding-bottom: 1rem; margin-bottom: 1rem;">
            <h3 style="margin: 0; font-size: 1.25rem;">Today's Logs</h3>
            <span style="font-size: 0.75rem; color: #64748b;">{date.today().strftime('%B %d, %Y')}</span>
        </div>
    """, unsafe_allow_html=True)
    
    if not logs:
        st.info("No logs recorded today. Use the 'Log Food' tab.")
    else:
        df = pd.DataFrame(logs)
        display_df = df[['Meal_Name', 'Calories', 'Protein', 'Carbs', 'Saturated_Fat', 'Sodium']].copy()
        display_df.columns = ['Meal', 'Kcal', 'Prot (g)', 'Carbs (g)', 'Sat.Fat (g)', 'Sod (mg)']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Fixed: Added unsafe_allow_html=True
    st.markdown("</div>", unsafe_allow_html=True)

def render_food_logger():
    st.title("Add Food 🍎")
    st.markdown("Describe your meal and AI will analyze nutritional content.")

    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            description = st.text_area("Meal Description", placeholder="E.g. Large Caesar salad with extra chicken", height=150)
        with col2:
            uploaded_file = st.file_uploader("📸 Add Photo Context", type=['jpg', 'png', 'jpeg'])
            
        if st.button("Log & Analyze", type="primary", use_container_width=True):
            if not description:
                st.warning("Please provide a description.")
            else:
                with st.spinner("AI analyzing nutrient profile..."):
                    img_blob = None
                    if uploaded_file:
                        try:
                            from PIL import Image
                            img = Image.open(uploaded_file)
                            img_blob = img
                        except: pass

                    # Prompt asking for JSON specifically
                    prompt = f"""
                    Analyze this food: "{description}". 
                    Return JSON with keys: Meal_Name, Calories, Protein, Carbs, Saturated_Fat, Unsaturated_Fat, Fiber, Sugar, Sodium, Potassium, Iron.
                    Values should be numbers (no units). Estimates.
                    """
                    
                    res_text = get_gemini_response(prompt, img_blob, json_mode=True)
                    
                    # --- CHECK FOR ERRORS BEFORE PARSING ---
                    if res_text.startswith("ERROR"):
                        if "NO_KEY" in res_text:
                            st.error("Please add `GEMINI_API_KEY` to `.streamlit/secrets.toml`.")
                        else:
                            st.error(f"AI Connection Failed. Details: {res_text}")
                    elif res_text:
                        try:
                            clean_res = res_text.replace("```json", "").replace("```", "").strip()
                            data = json.loads(clean_res)
                            
                            data['Log_ID'] = str(uuid.uuid4())[:8]
                            data['Timestamp'] = time.time()
                            data['Date_Ref'] = datetime.now().strftime("%Y-%m-%d")
                            
                            log_food_to_sheet(st.session_state.user['User_ID'], data)
                            st.success(f"Logged: {data.get('Meal_Name', 'Food')}")
                            time.sleep(1)
                            st.session_state.active_tab = "Dashboard"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to parse AI response.")
                            with st.expander("Debug Raw Output"):
                                st.code(res_text)
                    else:
                        st.error("AI returned no response.")

        st.markdown('</div>', unsafe_allow_html=True)

def render_leaderboard():
    st.title("Global Arena Sync 🔥")
    
    # FETCH REAL DATA
    users = fetch_all_users()
    if not users:
        st.warning("No users found or database not connected. Please check secrets.")
        return

    # Filter/Sort
    for u in users:
        u['Rank_Points_Counter'] = safe_int(u.get('Rank_Points_Counter', 0))
            
    leaderboard_data = sorted(users, key=lambda x: x['Rank_Points_Counter'], reverse=True)
    
    # Update: Added Daily Quest Card
    st.markdown("""
    <div class="glass-card" style="margin-bottom: 2rem; border-left: 4px solid #f59e0b;">
        <h3 style="margin: 0; font-size: 1.1rem; color: #f59e0b;">⚔️ Daily Quest: The Protein Wager</h3>
        <p style="font-size: 0.8rem; color: #cbd5e1; margin-top: 0.5rem;">Log over 100g of protein today to unlock a 1.5x Rank Point multiplier for tomorrow's tally.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="display: flex; gap: 1rem; margin-bottom: 2rem;">
        <div class="glass-card" style="flex: 1; text-align: center;">
            <p style="font-size: 0.75rem; font-weight: 800; color: #64748b; text-transform: uppercase;">Weekly Wins</p>
            <p style="font-size: 2rem; font-weight: 900; color: {ACCENT_AMBER};">{st.session_state.user.get('Total_Weekly_Wins', 0)}</p>
        </div>
        <div class="glass-card" style="flex: 1; text-align: center;">
            <p style="font-size: 0.75rem; font-weight: 800; color: #64748b; text-transform: uppercase;">Rank Points</p>
            <p style="font-size: 1.5rem; font-weight: 800; color: {ACCENT_EMERALD}; text-transform: uppercase;">{st.session_state.user.get('Rank_Points_Counter', 0)} PTS</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    for i, p in enumerate(leaderboard_data):
        username = p.get('Username', 'Unknown')
        is_me = username == st.session_state.user['Username']
        rank_pts = p.get('Rank_Points_Counter', 0)
        tier = p.get('Current_Rank_Tier', 'Bronze')
        
        border = f"1px solid {ACCENT_INDIGO}" if is_me else "1px solid rgba(51, 65, 85, 0.5)"
        bg = "rgba(99, 102, 241, 0.1)" if is_me else "rgba(30, 41, 59, 0.3)"
        
        tier_colors = {'Platinum': '#22d3ee', 'Gold': '#fde047', 'Silver': '#cbd5e1', 'Bronze': '#fb923c'}
        t_color = tier_colors.get(tier, '#fff')
        
        st.markdown(f"""
        <div style="background: {bg}; border: {border}; border-radius: 1.5rem; padding: 1.5rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 1.5rem; font-weight: 900; color: #475569; width: 30px;">#{i+1}</span>
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed={username}" style="width: 50px; height: 50px; border-radius: 12px; object-fit: cover;">
                <div>
                    <h4 style="margin: 0; font-size: 1.1rem;">{username} { '(You)' if is_me else ''}</h4>
                    <span style="font-size: 0.7rem; font-weight: 800; text-transform: uppercase; color: {t_color};">{tier}</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.7rem; font-weight: 800; color: #64748b; text-transform: uppercase;">Rank Points</div>
                <div style="font-size: 1.5rem; font-weight: 900; color: white;">{rank_pts}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_profile_settings():
    user = st.session_state.user
    col_h, col_act = st.columns([3, 1])
    with col_h:
        st.title("Identity Matrix 👤")
        st.markdown("Manage your biometric profile and nutrient directives.")
    with col_act:
        edit_mode = st.toggle("Edit Mode")
    
    st.markdown(f'<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {THEME_BORDER}; padding-bottom: 1rem; margin-bottom: 1.5rem;">
        <h3 style="margin: 0;">{ 'Configuring Targets' if edit_mode else 'Current Targets' }</h3>
        { '<span style="background: rgba(16, 185, 129, 0.1); color: #10b981; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 800; border: 1px solid rgba(16, 185, 129, 0.2);">ACTIVE</span>' if not edit_mode else ''}
    </div>
    """, unsafe_allow_html=True)

    if edit_mode:
        with st.container():
            st.markdown(f"""
            <div style="background: rgba(99, 102, 241, 0.05); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 1rem; padding: 1rem; display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
                <div>
                    <h4 style="color: #818cf8; font-size: 0.8rem; text-transform: uppercase; margin: 0;">AI Nutritionist Assessment</h4>
                    <p style="font-size: 0.75rem; color: #94a3b8; margin: 0;">Auto-calculate based on: {user.get('Age')}y / {user.get('Weight')} {user.get('Measurement_System')} / {user.get('Primary_Directive')}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🤖 Auto-Tune Targets"):
                with st.spinner("Calculating optimal biometrics..."):
                    w_kg = safe_float(user.get('Weight', 70))
                    h_cm = safe_float(user.get('Height', 170))
                    if user.get('Measurement_System') == 'imperial':
                        w_kg = w_kg * 0.453
                        h_cm = h_cm * 2.54
                    
                    prompt = f"""
                    User: Age {user.get('Age')}, Gender {user.get('Gender')}, Weight {w_kg}kg, Height {h_cm}cm, Activity {user.get('Activity_Level')}, Goal {user.get('Primary_Directive')}.
                    Calculate daily targets. Return JSON:
                    Calorie_Goal, Protein_Goal, Carbs_Goal, Saturated_Fat_Goal, Unsaturated_Fat_Goal, Fiber_Goal, Sugar_Goal, Sodium_Goal, Potassium_Goal, Iron_Goal.
                    """
                    res = get_gemini_response(prompt, json_mode=True)
                    if res.startswith("ERROR"):
                        st.error(res)
                    elif res:
                        try:
                            clean_res = res.replace("```json", "").replace("```", "")
                            new_targets = json.loads(clean_res)
                            st.session_state.user.update(new_targets)
                            st.success("Targets updated by AI.")
                            st.rerun()
                        except:
                            st.error("AI output invalid.")

    # Form Mode
    if edit_mode:
        with st.form("profile_form"):
            st.markdown("<h4 style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;'>Nutrient Profile</h4>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            
            new_goals = {}
            new_goals['Calorie_Goal'] = c1.number_input("Calories (kcal)", value=int(safe_float(user.get('Calorie_Goal', 2000))))
            new_goals['Protein_Goal'] = c2.number_input("Protein (g)", value=int(safe_float(user.get('Protein_Goal', 150))))
            new_goals['Carbs_Goal'] = c3.number_input("Carbs (g)", value=int(safe_float(user.get('Carbs_Goal', 200))))
            
            c4, c5 = st.columns(2)
            new_goals['Saturated_Fat_Goal'] = c4.number_input("Sat. Fat (g)", value=int(safe_float(user.get('Saturated_Fat_Goal', 20))))
            new_goals['Unsaturated_Fat_Goal'] = c5.number_input("Unsat. Fat (g)", value=int(safe_float(user.get('Unsaturated_Fat_Goal', 50))))

            st.markdown("<br><h4 style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;'>Micronutrient Profile</h4>", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            new_goals['Fiber_Goal'] = m1.number_input("Fiber (g)", value=int(safe_float(user.get('Fiber_Goal', 25))))
            new_goals['Sugar_Goal'] = m2.number_input("Sugar (g)", value=int(safe_float(user.get('Sugar_Goal', 30))))
            new_goals['Sodium_Goal'] = m3.number_input("Sodium (mg)", value=int(safe_float(user.get('Sodium_Goal', 2000))))
            
            m4, m5 = st.columns(2)
            new_goals['Potassium_Goal'] = m4.number_input("Potassium (mg)", value=int(safe_float(user.get('Potassium_Goal', 3500))))
            new_goals['Iron_Goal'] = m5.number_input("Iron (mg)", value=int(safe_float(user.get('Iron_Goal', 15))))

            st.write("")
            submitted = st.form_submit_button("Commit Changes & Sync", type="primary")
            if submitted:
                success = update_user_targets_db(user['User_ID'], new_goals)
                if success:
                    st.success("Profile Synced to Database.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Sync Failed.")
    else:
        # READ ONLY VIEW
        st.markdown("<h4 style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;'>Nutrient Profile</h4>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        def display_field(col, label, val, unit):
             with col:
                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(51, 65, 85, 0.5); border-radius: 0.75rem; padding: 1rem; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.7rem; font-weight: 800; color: #64748b; text-transform: uppercase;">{label}</span>
                    <span style="font-size: 0.9rem; font-weight: 800; color: white;">{val} <span style="font-size: 0.7rem; color: #475569;">{unit}</span></span>
                </div>
                """, unsafe_allow_html=True)
        
        display_field(c1, "Calories", safe_int(user.get('Calorie_Goal')), "kcal")
        display_field(c2, "Protein", safe_int(user.get('Protein_Goal')), "g")
        display_field(c3, "Carbs", safe_int(user.get('Carbs_Goal')), "g")
        c4, c5 = st.columns(2)
        display_field(c4, "Sat. Fat", safe_int(user.get('Saturated_Fat_Goal')), "g")
        display_field(c5, "Unsat. Fat", safe_int(user.get('Unsaturated_Fat_Goal')), "g")

        st.markdown("<br><h4 style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;'>Micronutrient Profile</h4>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        display_field(m1, "Fiber", safe_int(user.get('Fiber_Goal')), "g")
        display_field(m2, "Sugar", safe_int(user.get('Sugar_Goal')), "g")
        display_field(m3, "Sodium", safe_int(user.get('Sodium_Goal')), "mg")
        m4, m5 = st.columns(2)
        display_field(m4, "Potassium", safe_int(user.get('Potassium_Goal')), "mg")
        display_field(m5, "Iron", safe_int(user.get('Iron_Goal')), "mg")

    st.markdown("</div>", unsafe_allow_html=True)

def render_login():
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='font-size: 4rem; color: {ACCENT_EMERALD} !important;'>NutriComp</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 1.2rem; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase;'>Precision Health Lab</p>", unsafe_allow_html=True)

    with col2:
        st.markdown(f'<div class="glass-card" style="margin-top: 2rem;">', unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["Login", "Register"])
        
        with tab_login:
            st.markdown("<h3>Identity Verification</h3>", unsafe_allow_html=True)
            username = st.text_input("Identity Name", placeholder="Enter username", key="login_user")
            password = st.text_input("Private Key", type="password", placeholder="••••••••", key="login_pass")
            
            if st.button("Authorize Session", type="primary"):
                if username and password:
                    try:
                        # 1. GET ALL USERS FROM SHEET
                        all_users = fetch_all_users()
                        
                        # 2. FIND THE MATCH
                        found_user = None
                        for user in all_users:
                            # Check Username, Password
                            if str(user.get("Username")) == username and str(user.get("Password")) == password:
                                # APPROVAL CHECK
                                approved_status = str(user.get("Approved", "No")).lower()
                                if "y" in approved_status:
                                    found_user = user
                                    break
                                else:
                                    st.error("ACCESS DENIED: Account awaiting admin approval.")
                                    found_user = None
                                    break 
                        
                        # 3. SUCCESS
                        if found_user:
                            st.success(f"Welcome back, {username}!")
                            st.session_state.authenticated = True
                            st.session_state.user = found_user
                            st.session_state.active_tab = "Dashboard"
                            time.sleep(1)
                            st.rerun()
                        elif not any(str(u.get("Username")) == username for u in all_users):
                             st.error("ACCESS DENIED: Incorrect Username or Password.")
                            
                    except Exception as e:
                        st.error(f"System Error: {e}")
                else:
                    st.warning("Please enter your credentials.")

        with tab_register:
            st.markdown("<h3>New Registration</h3>", unsafe_allow_html=True)
            reg_user = st.text_input("Choose Username", key="reg_user")
            reg_pass = st.text_input("Choose Password", type="password", key="reg_pass")
            if st.button("Initialize Identity"):
                if reg_user and reg_pass:
                    success, msg = register_user(reg_user, reg_pass)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Fields cannot be empty.")

        st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. APP ORCHESTRATION
# -----------------------------------------------------------------------------

def main():
    if not st.session_state.user:
        render_login()
    else:
        with st.sidebar:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; padding-left: 0.5rem;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, {ACCENT_INDIGO}, #a855f7); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);">⚡</div>
                <h2 style="margin: 0; font-size: 1.5rem;">NutriComp</h2>
            </div>
            """, unsafe_allow_html=True)
            
            tabs = {
                "Dashboard": "📊",
                "Log Food": "🍎",
                "Arena Sync": "🔥",
                "Identity": "👤"
            }
            
            for name, icon in tabs.items():
                is_active = st.session_state.active_tab == name
                if st.button(f"{icon}  {name}", key=f"nav_{name}"):
                    st.session_state.active_tab = name
                    st.rerun()
            
            st.markdown("---")
            if st.button("Logout"):
                st.session_state.user = None
                st.rerun()

        if st.session_state.active_tab == "Dashboard":
            render_dashboard()
        elif st.session_state.active_tab == "Log Food":
            render_food_logger()
        elif st.session_state.active_tab == "Arena Sync":
            render_leaderboard()
        elif st.session_state.active_tab == "Identity":
            render_profile_settings()

if __name__ == "__main__":
    main()
