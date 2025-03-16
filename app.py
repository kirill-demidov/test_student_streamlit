import os
import gspread
import sqlite3
import pandas as pd
import streamlit as st
import subprocess
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

# ✅ Load environment variables from .env file
load_dotenv()

# ✅ Read Google Credentials Path
google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if google_creds_path and os.path.exists(google_creds_path):
    try:
        # Authenticate with Google Sheets using the JSON file
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            google_creds_path,
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)

    except Exception as e:
        st.error(f"❌ Error loading credentials file: {e}")
        st.stop()
else:
    st.error("❌ GOOGLE_APPLICATION_CREDENTIALS environment variable is missing or file not found!")
    st.stop()

# ✅ Optimize Google Sheets API Calls with Caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_google_sheet():
    return client.open_by_key("1qKjn9TCi3myboBmBZkwM-36ENLigcN1NOt-l4d1ku2Y")

sheet = get_google_sheet()

@st.cache_data(ttl=300)  # Cache sheet data for 5 minutes
def get_sheet_data(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    all_rows = worksheet.col_values(1)

    # ✅ Ignore the first row (header)
    return all_rows[1:] if len(all_rows) > 1 else []

students = get_sheet_data("שמות תלמידים")
test_ids = get_sheet_data("מספרים אקראיים")
periods = get_sheet_data("עונות")

# ✅ Setup SQLite database
DB_FILE = "assignments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student TEXT NOT NULL,
            test_id TEXT NOT NULL,
            period TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ✅ Function to clear all שיבוצים (truncate table)
def clear_all_assignments():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM assignments")
    conn.commit()
    conn.close()

# ✅ Exit Button Function
def exit_app():
    st.write("האפליקציה נסגרה. ניתן לסגור את הדפדפן.")
    st.stop()

# ✅ Initialize session state for page switching
if "selected_student" not in st.session_state:
    st.session_state.selected_student = None

if "page" not in st.session_state:
    st.session_state.page = "שיבוץ"

# ✅ Sidebar Navigation
st.sidebar.header("ניווט")
if st.sidebar.button("📌 שיבוץ"):
    st.session_state.page = "שיבוץ"
    st.rerun()

if st.sidebar.button("📊 דוחות"):
    st.session_state.page = "דוחות"
    st.rerun()

if st.sidebar.button("✏️ עריכת שיבוץ"):
    st.session_state.page = "עריכת שיבוץ"
    st.rerun()

# ✅ Delete All שיבוצים with Confirmation
if st.sidebar.button("🚮 מחק את כל השיבוצים"):
    st.session_state.confirm_delete = True  # Show confirmation

if "confirm_delete" in st.session_state and st.session_state.confirm_delete:
    st.sidebar.warning("❗ האם אתה בטוח שברצונך למחוק את כל השיבוצים?")
    if st.sidebar.button("⚠️ אישור מחיקה"):
        clear_all_assignments()
        del st.session_state.confirm_delete  # Remove confirmation state
        st.rerun()
    if st.sidebar.button("❌ ביטול"):
        del st.session_state.confirm_delete  # Cancel confirmation
        st.rerun()

if st.sidebar.button("🚪 יציאה מהאפליקציה"):
    exit_app()

# ✅ Page 1: Assign students to tests ("שיבוץ")
if st.session_state.page == "שיבוץ":
    st.title("שיבוץ תלמידים למבחנים")

    student_selected = st.selectbox("בחר תלמיד", students)
    test_selected = st.selectbox("בחר מבחן", test_ids)
    period_selected = st.selectbox("בחר תקופה", periods)

    if st.button("שמור שיבוץ"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO assignments (student, test_id, period) VALUES (?, ?, ?)", 
                  (student_selected, test_selected, period_selected))
        conn.commit()
        conn.close()
        st.success(f"התלמיד {student_selected} שובץ למבחן {test_selected} בתקופה {period_selected}")

# ✅ Page 2: Reports ("דוחות")
elif st.session_state.page == "דוחות":
    st.title("📊 דוחות מערכת")

    conn = sqlite3.connect(DB_FILE)
    df_assignments = pd.read_sql_query("SELECT id, student, test_id, period FROM assignments", conn)

    # ✅ Show message if no data exists
    if df_assignments.empty:
        st.warning("⚠️ אין שיבוצים להצגה.")
    else:
        st.subheader("📋 דוח שיבוצים")
        st.dataframe(df_assignments)

    conn.close()

# ✅ Page 3: Edit Assignments ("עריכת שיבוץ")
elif st.session_state.page == "עריכת שיבוץ":
    st.title("✏️ עריכת שיבוץ תלמידים")

    conn = sqlite3.connect(DB_FILE)
    df_assignments = pd.read_sql_query("SELECT id, student, test_id, period FROM assignments", conn)

    if df_assignments.empty:
        st.warning("⚠️ אין שיבוצים לעריכה.")
    else:
        for index, row in df_assignments.iterrows():
            col1, col2, col3, col4 = st.columns([3, 3, 3, 1])
            with col1:
                student = st.selectbox("תלמיד", students, index=students.index(row["student"]) if row["student"] in students else 0, key=f"student_{row['id']}")
            with col2:
                test = st.selectbox("מבחן", test_ids, index=test_ids.index(row["test_id"]) if row["test_id"] in test_ids else 0, key=f"test_{row['id']}")
            with col3:
                period = st.selectbox("תקופה", periods, index=periods.index(row["period"]) if row["period"] in periods else 0, key=f"period_{row['id']}")
            with col4:
                if st.button("🔄 עדכן", key=f"update_{row['id']}"):
                    cursor = conn.cursor()
                    cursor.execute("UPDATE assignments SET student=?, test_id=?, period=? WHERE id=?", 
                                   (student, test, period, row["id"]))
                    conn.commit()
                    st.success(f"שיבוץ עודכן בהצלחה עבור {student}")
                    st.rerun()

    conn.close()