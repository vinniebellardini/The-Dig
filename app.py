import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import time
import os
import base64  # <--- Added this standard library

# 1. Configure Page
st.set_page_config(page_title="The Dig", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS (Modern AI Studio Style) ---
st.markdown("""
<style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* --- Main Titles & Logo --- */
    .logo-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 2rem;
    }
    .logo-img {
        max-width: 250px;
        border-radius: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .main-title {
        font-family: 'Inter', sans-serif;
        font-weight: 900;
        font-size: 2.5rem;
        margin-top: 1rem;
        background: linear-gradient(to right, #F8FAFC, #94A3B8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
    }

    /* --- Modern Containers & Cards --- */
    [data-testid="stExpander"] {
        background-color: #1E293B;
        border-radius: 15px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* --- Styled File Uploader (Dashed Box) --- */
    [data-testid="stFileUploader"] {
        background-color: #1E293B;
        border: 2px dashed #475569;
        border-radius: 15px;
        padding: 2rem;
        text-align: center;
        transition: all 0.2s ease-in-out;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #3B82F6;
        background-color: #253148;
    }
    [data-testid="stFileUploader"] section > button {
        background-color: #3B82F6;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }

    /* --- Buttons & Inputs --- */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        border: none;
        box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.5);
        transition: all 0.2s;
    }
    .stButton > button:hover {
        box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.6);
        transform: translateY(-2px);
    }
    .stTextInput > div > div > input {
        background-color: #0F172A;
        border: 1px solid #334155;
        border-radius: 10px;
        color: #F8FAFC;
        padding: 0.5rem 1rem;
    }

    /* --- Sidebar & Metrics --- */
    [data-testid="stSidebar"] {
        background-color: #1E293B;
        border-right: 1px solid #334155;
    }
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 900;
        color: #10B981; /* Bright Green for Value */
    }
    [data-testid="stMetricLabel"] {
        font-weight: 600;
        color: #94A3B8;
    }

    /* --- Inventory Slab (Modern) --- */
    .slab-container {
        background-color: #1E293B;
        border-radius: 15px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        border: 1px solid #334155;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .slab-header {
        font-size: 1.25rem;
        font-weight: 900;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    .slab-detail {
        color: #94A3B8;
        font-size: 0.95rem;
        margin-bottom: 0.25rem;
    }
    .slab-price {
        font-size: 1.5rem;
        font-weight: 900;
        color: #10B981;
        text-align: right;
        margin-top: 1rem;
    }
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
if 'inventory' not in st.session_state: st.session_state.inventory = []

# 4. Sidebar
with st.sidebar:
    st.title("💎 Collection Stats")
    
    total_low, total_high = 0.0, 0.0
    for item in st.session_state.inventory:
        val_str = str(item.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    
    st.metric(label="Total Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"{len(st.session_state.inventory)} items scanned in this session.")
    
    st.divider()
    
    st.subheader("📁 Data Manager")
    uploaded_file = st.file_uploader("Resume Session (Upload CSV)", type=['csv'])
    if uploaded_file is not None and len(st.session_state.inventory) == 0:
        try:
            df_load = pd.read_csv(uploaded_file)
            st.session_state.inventory = df_load.to_dict('records')
            st.success(f"✅ Loaded {len(df_load)} items!")
            st.rerun()
        except Exception as e: st.error("Error loading file.")
        
    if len(st.session_state.inventory) > 0:
        df_save = pd.DataFrame(st.session_state.inventory)
        csv = df_save.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "card_inventory.csv", "text/csv", type="primary")

# 5. Main Content
# Logo & Title Section
col1, col2, col3 = st.columns([1,2,1])
with col2:
    if os.path.exists("logo.png"):
        # We open the file and encode it using standard base64 library
        with open("logo.png", "rb") as f:
            data = base64.b64encode(f.read()).decode()
            
        st.markdown(f"""
            <div class="logo-container">
                <img src="data:image/png;base64,{data}" class="logo-img">
                <div class="main-title">THE DIG</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="main-title">⛏️ THE DIG</div>', unsafe_allow_html=True)

# Settings & Hints Expander to reduce clutter
with st.expander("⚙️ Scan Settings & Hints", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        archive_location = st.text_input("📦 Archive Location", value="Box 1")
    with col_b:
        series_hint = st.text_input("🔍 Context Hint (Optional)", placeholder="e.g., '1989 Upper Deck' or 'Signed Ball'")
    st.caption("Tip: Use the Context Hint for better accuracy with bulk card scans or memorabilia.")

# Main Action Area
st.markdown("### 📸 Add Items")
st.caption("Upload photos to automatically identify and value your cards & memorabilia.")

front_images = st.file_uploader("Drag & drop photos here", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True, help="Upload one or more front photos.")

back_image = None
if front_images and len(front_images) == 1:
    st.info("Single item detected. You can add a back/COA image for greater precision.")
    back_image = st.file_uploader("Add Back/COA Image (Optional)", type=['jpg', 'png', 'jpeg'], key="back")

# Analysis Logic
if st.button("🚀 Launch Analysis", type="primary", use_container_width=True):
    if not front_images:
        st.warning("Please upload at least one image to start.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_files = len(front_images)
        
        for i, img_file in enumerate(front_images):
            status_text.markdown(f"**Processing item {i+1} of {total_files}...**")
            try:
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
                
                context_instruction = f"IMPORTANT CONTEXT: The user provided this hint: '{series_hint}'. Use this to help identification." if series_hint else ""
                prompt = f"""
                Identify this sports item (Card OR Memorabilia). Return a single JSON object with these exact keys:
                'Player', 'Team', 'Year', 'Set', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value'
                {context_instruction}
                RULES:
                1. If it is a CARD: Standard identification.
                2. If it is MEMORABILIA: Map 'Player' to Signer/Subject, 'Set' to Manufacturer/Type, 'Card_Number' to COA/Serial#, 'Variation' to Inscriptions.
                For 'Estimated_Raw_Value', provide a dollar range (e.g. '$10-15').
                """
                inputs = [prompt, Image.open(img_file)]
                if len(front_images) == 1 and back_image: inputs.append(Image.open(back_image))
                
                response = model.generate_content(inputs)
                new_entry = json.loads(response.text)
                new_entry['Archive_Location'] = archive_location
                st.session_state.inventory.append(new_entry)
                
                # Modern "Slab" Result
                st.markdown(f"""
                <div class="slab-container">
                    <div class="slab-header">✅ {new_entry.get('Player')}</div>
                    <div class="slab-detail">Goal: {new_entry.get('Year')} {new_entry.get('Set')} #{new_entry.get('Card_Number')}</div>
                    <div class="slab-detail">{new_entry.get('Team')} | {new_entry.get('Variation')}</div>
                    <div class="slab-detail" style="font-style: italic;">Notes: {new_entry.get('Condition_Notes')}</div>
                    <div class="slab-price">{new_entry.get('Estimated_Raw_Value')}</div>
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e: st.error(f"Error on file {img_file.name}: {e}")
            progress_bar.progress((i + 1) / total_files)
            if total_files > 1: time.sleep(4)
            
        st.success("Analysis Complete!")
        time.sleep(1)
        st.rerun()

# Inventory Table
st.divider()
st.markdown("### 📋 Session Inventory")
if len(st.session_state.inventory) > 0:
    df = pd.DataFrame(st.session_state.inventory)
    preferred_order = ['Archive_Location', 'Player', 'Year', 'Set', 'Card_Number', 'Variation', 'Estimated_Raw_Value', 'Condition_Notes']
    cols = [c for c in preferred_order if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)
else:
    st.info("Your inventory is empty. Upload photos to get started.")
