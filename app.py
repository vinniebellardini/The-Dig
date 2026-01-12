import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import pandas as pd
import json
import re
import time
import os
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 1. Configure Page
st.set_page_config(page_title="The Dig", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .logo-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 2rem; text-align: center; }
    .logo-img { max-width: 180px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); margin-bottom: 0.5rem; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 2.5rem; background: linear-gradient(to bottom, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 2px 10px rgba(0,0,0,0.3); margin-top: 0px; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; color: #94A3B8; padding: 10px 20px; border: 1px solid #334155; }
    .stTabs [aria-selected="true"] { background-color: #3B82F6; color: white; border-color: #3B82F6; }

    [data-testid="stExpander"] { background-color: #1E293B; border-radius: 15px; border: 1px solid #334155; }
    [data-testid="stFileUploader"] { background-color: #1E293B; border: 2px dashed #475569; border-radius: 15px; padding: 2rem; text-align: center; }
    [data-testid="stFileUploader"] section > button { background-color: #3B82F6; color: white; border: none; border-radius: 8px; font-weight: 600; }
    [data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #334155; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 900; color: #10B981; }

    .slab-container { background-color: #1E293B; border-radius: 15px; padding: 1rem; margin-top: 1rem; border: 1px solid #334155; border-left: 5px solid #3B82F6; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    .slab-header { font-size: 1.1rem; font-weight: 900; color: #F8FAFC; }
    .slab-detail { color: #94A3B8; font-size: 0.9rem; }
    .slab-price { font-size: 1.4rem; font-weight: 900; color: #10B981; text-align: right; }
</style>
""", unsafe_allow_html=True)

# 2. Connections (Sheets & Drive)
def get_creds():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

def connect_to_sheets():
    try:
        creds = get_creds()
        client = gspread.authorize(creds)
        sheet = client.open("Card Inventory").sheet1
        return sheet, None
    except Exception as e:
        return None, str(e)

def upload_image_to_drive(image_file, filename):
    try:
        creds = get_creds()
        service = build('drive', 'v3', credentials=creds)
        folder_id = st.secrets["GDRIVE_FOLDER_ID"]
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        image_file.save(img_byte_arr, format=image_file.format)
        img_byte_arr.seek(0)
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(img_byte_arr, mimetype=f'image/{image_file.format.lower()}')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Drive Upload Error: {e}")
        return None

# 3. Helper Functions
def get_price_range(value_str):
    if not isinstance(value_str, str): return 0.0, 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers: return 0.0, 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums: return 0.0, 0.0
    if len(clean_nums) == 1: return clean_nums[0], clean_nums[0]
    else: return min(clean_nums), max(clean_nums)

def save_to_google_sheets(data_dict):
    sheet, err = connect_to_sheets()
    if sheet:
        try:
            # Check/Add Headers
            if not sheet.row_values(1):
                headers = ['Player', 'Year', 'Set', 'Team', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value', 'Archive_Location', 'Front_Image', 'Back_Image']
                sheet.append_row(headers)
            
            # If headers exist but match old format, we might need to be careful, but gspread append usually handles it.
            # Ideally, user should clear sheet or add columns manually if using old sheet.
            
            row = [
                data_dict.get('Player', ''),
                data_dict.get('Year', ''),
                data_dict.get('Set', ''),
                data_dict.get('Team', ''),
                data_dict.get('Card_Number', ''),
                data_dict.get('Variation', ''),
                data_dict.get('Condition_Notes', ''),
                data_dict.get('Estimated_Raw_Value', ''),
                data_dict.get('Archive_Location', ''),
                data_dict.get('Front_Image', ''),
                data_dict.get('Back_Image', '')
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            return False
    return False

# 4. Initialize State
if 'inventory' not in st.session_state: st.session_state.inventory = []

# 5. Sidebar
with st.sidebar:
    st.title("💎 Collection Stats")
    sheet_conn, conn_err = connect_to_sheets()
    if sheet_conn: st.success("🟢 Cloud Connected")
    else: st.error(f"🔴 Cloud Error: {conn_err}")

    total_low, total_high = 0.0, 0.0
    for item in st.session_state.inventory:
        val_str = str(item.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    st.metric(label="Total Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"{len(st.session_state.inventory)} items scanned.")
    st.divider()
    st.info("ℹ️ Items & Photos saved to Cloud.")

# 6. SPLIT LAYOUT
col_action, col_data = st.columns([1, 1.2], gap="large")

with col_action:
    # Logo
    if os.path.exists("logo.png"):
        import base64
        with open("logo.png", "rb") as f: data = base64.b64encode(f.read()).decode()
        st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{data}" class="logo-img"><div class="main-title">THE DIG</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="main-title" style="text-align: center;">⛏️ THE DIG</div>', unsafe_allow_html=True)

    with st.expander("⚙️ Session Settings", expanded=True):
        archive_location = st.text_input("📦 Archive Box / Location", value="Box 1")
        series_hint = st.text_input("🔍 Series Hint (Optional)", placeholder="e.g. '1986 Fleer'")

    st.markdown("### 📸 Scan Tools")
    tab_single, tab_batch = st.tabs(["💎 Single Item", "🚀 Batch Dig"])

    # --- SINGLE ITEM ---
    with tab_single:
        col_f, col_b = st.columns(2)
        with col_f: s_front = st.file_uploader("Front (Req)", type=['jpg','png','jpeg'], key="sf")
        with col_b: s_back = st.file_uploader("Back (Opt)", type=['jpg','png','jpeg'], key="sb")
        
        if st.button("🔍 Analyze & Upload", type="primary", use_container_width=True):
            if not s_front: st.warning("Need Front Image")
            else:
                status = st.empty()
                status.write("Analyzing...")
                try:
                    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
                    ctx = f"HINT: {series_hint}" if series_hint else ""
                    prompt_text = f"""Identify item. JSON: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value' ($ Range). {ctx}"""
                    
                    img_front = Image.open(s_front)
                    img_back = Image.open(s_back) if s_back else None
                    
                    inputs = [prompt_text, img_front]
                    if img_back: inputs.append(img_back)
                    
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=inputs,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    new = json.loads(response.text)
                    new['Archive_Location'] = archive_location
                    
                    # UPLOAD IMAGES
                    status.write("Uploading Photos to Drive...")
                    safe_name = f"{new.get('Player', 'Unknown')}_{new.get('Year', '')}_{new.get('Set', '')}".replace(" ", "_")
                    
                    front_url = upload_image_to_drive(img_front, f"{safe_name}_FRONT.jpg")
                    new['Front_Image'] = front_url
                    
                    if img_back:
                        back_url = upload_image_to_drive(img_back, f"{safe_name}_BACK.jpg")
                        new['Back_Image'] = back_url
                    
                    # SAVE TO SHEET
                    status.write("Saving to Sheet...")
                    cloud_success = save_to_google_sheets(new)
                    st.session_state.inventory.append(new)
                    
                    st.markdown(f"""
                    <div class="slab-container">
                        <div class="slab-header">✅ {new.get('Player')}</div>
                        <div class="slab-detail">{new.get('Year')} {new.get('Set')} #{new.get('Card_Number')}</div>
                        <div class="slab-price">{new.get('Estimated_Raw_Value')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if cloud_success: st.toast("☁️ Saved Data & Photos!", icon="✅")
                    else: st.toast("⚠️ Saved locally only", icon="⚠️")
                    status.empty()
                    
                except Exception as e: st.error(f"Error: {e}")

    # --- BATCH ---
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
                    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
                    
                    for i in range(0, len(sorted_files), 2):
                        stat.markdown(f"**Card {(i//2)+1}/{total}**")
                        try:
                            img_f = Image.open(sorted_files[i])
                            img_b = Image.open(sorted_files[i+1])
                            
                            ctx = f"HINT: {series_hint}" if series_hint else ""
                            prompt_text = f"""Identify item using Front (Img1) & Back (Img2). JSON keys: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value'. {ctx}"""
                            
                            resp = client.models.generate_content(
                                model="gemini-1.5-flash",
                                contents=[prompt_text, img_f, img_b],
                                config=types.GenerateContentConfig(response_mime_type="application/json")
                            )
                            new = json.loads(resp.text)
                            new['Archive_Location'] = archive_location
                            
                            # Upload Images
                            safe_name = f"{new.get('Player', 'Unknown')}_{new.get('Year', '')}_{new.get('Set', '')}".replace(" ", "_")
                            new['Front_Image'] = upload_image_to_drive(img_f, f"{safe_name}_FRONT.jpg")
                            new['Back_Image'] = upload_image_to_drive(img_b, f"{safe_name}_BACK.jpg")
                            
                            save_to_google_sheets(new)
                            st.session_state.inventory.append(new)
                            
                        except Exception as e: st.error(f"Error: {e}")
                        prog.progress(((i//2)+1)/total)
                    
                    st.success("Batch Done!")
                    time.sleep(1)
                    st.rerun()

with col_data:
    st.markdown("### 📋 Live Inventory")
    if len(st.session_state.inventory) > 0:
        df = pd.DataFrame(st.session_state.inventory)
        cols = ['Player', 'Year', 'Set', 'Card_Number', 'Estimated_Raw_Value', 'Front_Image']
        visible_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[visible_cols], use_container_width=True, height=600, hide_index=True)
    else:
        st.info("Waiting for scans...")
