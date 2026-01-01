import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import time
import os
import base64

# 1. Configure Page
st.set_page_config(page_title="The Dig", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Logo Styling */
    .logo-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 2rem; text-align: center; }
    .logo-img { max-width: 180px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); margin-bottom: 0.5rem; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 2.5rem; background: linear-gradient(to bottom, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 2px 10px rgba(0,0,0,0.3); margin-top: 0px; }

    /* Modern Tabs & Containers */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; color: #94A3B8; padding: 10px 20px; border: 1px solid #334155; }
    .stTabs [aria-selected="true"] { background-color: #3B82F6; color: white; border-color: #3B82F6; }

    [data-testid="stExpander"] { background-color: #1E293B; border-radius: 15px; border: 1px solid #334155; }
    [data-testid="stFileUploader"] { background-color: #1E293B; border: 2px dashed #475569; border-radius: 15px; padding: 2rem; text-align: center; }
    [data-testid="stFileUploader"] section > button { background-color: #3B82F6; color: white; border: none; border-radius: 8px; font-weight: 600; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #334155; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 900; color: #10B981; }

    /* Slab/Card Result */
    .slab-container { background-color: #1E293B; border-radius: 15px; padding: 1rem; margin-top: 1rem; border: 1px solid #334155; border-left: 5px solid #3B82F6; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    .slab-header { font-size: 1.1rem; font-weight: 900; color: #F8FAFC; }
    .slab-detail { color: #94A3B8; font-size: 0.9rem; }
    .slab-price { font-size: 1.4rem; font-weight: 900; color: #10B981; text-align: right; }
</style>
""", unsafe_allow_html=True)

# 2. Helper Functions
def get_price_range(value_str):
    if not isinstance(value_str, str): return 0.0, 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers: return 0.0, 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums: return 0.0, 0.0
    if len(clean_nums) == 1: return clean_nums[0], clean_nums[0]
    else: return min(clean_nums), max(clean_nums)

# 3. Initialize State
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 4. Sidebar (Stats & Restore)
with st.sidebar:
    st.title("💎 Collection Stats")
    
    total_low, total_high = 0.0, 0.0
    for item in st.session_state.inventory:
        val_str = str(item.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    
    st.metric(label="Total Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"{len(st.session_state.inventory)} items scanned.")
    
    st.divider()
    
    st.subheader("📂 Import / Export")
    st.info("Use this to save your work or restore a previous session.")
    
    # Improved "Resume" Box
    uploaded_file = st.file_uploader("📥 Restore from CSV", type=['csv'], help="Upload a 'card_inventory.csv' from a previous session to add new cards to it.")
    if uploaded_file is not None and len(st.session_state.inventory) == 0:
        try:
            df_load = pd.read_csv(uploaded_file)
            st.session_state.inventory = df_load.to_dict('records')
            st.success(f"✅ Restored {len(df_load)} items!")
            time.sleep(1)
            st.rerun()
        except Exception as e: st.error("Error loading file.")
        
    if len(st.session_state.inventory) > 0:
        df_save = pd.DataFrame(st.session_state.inventory)
        csv = df_save.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Save Session to CSV", csv, "card_inventory.csv", "text/csv", type="primary")

# 5. SPLIT LAYOUT (Action vs Data)
col_action, col_data = st.columns([1, 1.2], gap="large") # 1:1.2 ratio gives Table slightly more room

# --- LEFT COLUMN: ACTION ZONE ---
with col_action:
    # Logo
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <div class="logo-container">
                <img src="data:image/png;base64,{data}" class="logo-img">
                <div class="main-title">THE DIG</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="main-title" style="text-align: center;">⛏️ THE DIG</div>', unsafe_allow_html=True)

    # Settings
    with st.expander("⚙️ Session Settings", expanded=True):
        archive_location = st.text_input("📦 Archive Box / Location", value="Box 1")
        series_hint = st.text_input("🔍 Series Hint (Optional)", placeholder="e.g. '1986 Fleer'")

    # Upload Tabs
    st.markdown("### 📸 Scan Tools")
    tab_single, tab_batch = st.tabs(["💎 Single Item", "🚀 Batch Dig"])

    # --- TAB 1: SINGLE ---
    with tab_single:
        col_f, col_b = st.columns(2)
        with col_f: s_front = st.file_uploader("Front (Req)", type=['jpg','png','jpeg'], key="sf")
        with col_b: s_back = st.file_uploader("Back (Opt)", type=['jpg','png','jpeg'], key="sb")
        
        if st.button("🔍 Analyze Single", type="primary", use_container_width=True):
            if not s_front: st.warning("Need Front Image")
            else:
                status = st.empty()
                status.write("Analyzing...")
                try:
                    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                    model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
                    ctx = f"HINT: {series_hint}" if series_hint else ""
                    prompt = f"""Identify item. JSON: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value' ($ Range). {ctx}"""
                    inputs = [prompt, Image.open(s_front)]
                    if s_back: inputs.append(Image.open(s_back))
                    
                    resp = model.generate_content(inputs)
                    new = json.loads(resp.text)
                    new['Archive_Location'] = archive_location
                    st.session_state.inventory.append(new)
                    
                    # Show Slab Result Here
                    st.markdown(f"""
                    <div class="slab-container">
                        <div class="slab-header">✅ {new.get('Player')}</div>
                        <div class="slab-detail">{new.get('Year')} {new.get('Set')} #{new.get('Card_Number')}</div>
                        <div class="slab-price">{new.get('Estimated_Raw_Value')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.success("Added to list!")
                    
                except Exception as e: st.error(f"Error: {e}")

    # --- TAB 2: BATCH ---
    with tab_batch:
        st.info("Order: Front, Back, Front, Back...")
        b_files = st.file_uploader("Upload Batch", type=['jpg','png','jpeg'], accept_multiple_files=True, key="bf")
        
        if st.button("🚀 Run Batch", type="primary", use_container_width=True):
            if not b_files: st.warning("No files")
            else:
                sorted_files = sorted(b_files, key=lambda x: x.name)
                if len(sorted_files) % 2 != 0: st.error("Uneven batch! Need pairs.")
                else:
                    prog = st.progress(0)
                    stat = st.empty()
                    total = len(sorted_files)//2
                    
                    for i in range(0, len(sorted_files), 2):
                        stat.markdown(f"**Card {(i//2)+1}/{total}**")
                        try:
                            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                            model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
                            ctx = f"HINT: {series_hint}" if series_hint else ""
                            prompt = f"""Identify item using Front (Img1) & Back (Img2). JSON keys: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value'. {ctx}"""
                            inputs = [prompt, Image.open(sorted_files[i]), Image.open(sorted_files[i+1])]
                            
                            resp = model.generate_content(inputs)
                            new = json.loads(resp.text)
                            new['Archive_Location'] = archive_location
                            st.session_state.inventory.append(new)
                            
                        except Exception as e: st.error(f"Error: {e}")
                        prog.progress(((i//2)+1)/total)
                        time.sleep(4)
                    
                    st.success("Batch Done!")
                    time.sleep(1)
                    st.rerun()

# --- RIGHT COLUMN: DATA ZONE ---
with col_data:
    st.markdown("### 📋 Live Inventory")
    if len(st.session_state.inventory) > 0:
        df = pd.DataFrame(st.session_state.inventory)
        # Reorder columns for readability
        cols = ['Player', 'Year', 'Set', 'Card_Number', 'Variation', 'Estimated_Raw_Value', 'Archive_Location', 'Condition_Notes']
        visible_cols = [c for c in cols if c in df.columns]
        
        # Display Dataframe with fixed height so it scrolls
        st.dataframe(
            df[visible_cols], 
            use_container_width=True, 
            height=600, 
            hide_index=True
        )
    else:
        st.info("Waiting for scans... Your list will appear here.")
