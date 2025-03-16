import os
import gspread
import sqlite3
import pandas as pd
import streamlit as st
import logging
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

# ✅ Logging Configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ Load environment variables
load_dotenv()

# ✅ Read Google Credentials Path
google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not google_creds_path or not os.path.exists(google_creds_path):
    st.error("❌ GOOGLE_APPLICATION_CREDENTIALS environment variable is missing or file not found!")
    st.stop()

# ✅ Authenticate with Google Sheets
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        google_creds_path,
        scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"❌ Error loading credentials file: {e}")
    st.stop()

# ✅ Hardcoded Years
YEARS = ["תשפ״ה", "תשפ״ד", "תשפ״ג", "תשפ״ב"]

# ✅ Fetch Data from Google Sheets
@st.cache_data(ttl=300)
def get_google_sheet():
    return client.open_by_key("1qKjn9TCi3myboBmBZkwM-36ENLigcN1NOt-l4d1ku2Y")

sheet = get_google_sheet()

@st.cache_data(ttl=300)
def get_sheet_data(sheet_name):
    try:
        worksheet = sheet.worksheet(sheet_name)
        all_rows = worksheet.get_all_values()
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        return df
    except Exception as e:
        st.error(f"❌ Error loading sheet {sheet_name}: {e}")
        return pd.DataFrame()

students_df = get_sheet_data("שמות תלמידים")
test_ids = get_sheet_data("מספרים אקראיים")["מספרים אקראיים"].dropna().tolist() if not get_sheet_data("מספרים אקראיים").empty else []
periods = get_sheet_data("עונות")["עונות"].dropna().tolist() if not get_sheet_data("עונות").empty else []

classes = students_df["כיתה"].dropna().unique().tolist() if not students_df.empty else []

# ✅ Setup SQLite database
DB_FILE = "assignments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # ✅ Create table with edited_by column
    c.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT NOT NULL,
            period TEXT NOT NULL,
            test_id TEXT NOT NULL,
            class TEXT NOT NULL,
            student TEXT NOT NULL,
            edited_by TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()

init_db()

# ✅ Fetch assignments
def get_assignments():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM assignments", conn)
    conn.close()
    return df

# ✅ Clear all assignments
def clear_all_assignments():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM assignments")
    conn.commit()
    conn.close()
    st.cache_data.clear()  # ✅ Clear cache after deletion

# ✅ Exit app
def exit_app():
    st.write("האפליקציה נסגרה. ניתן לסגור את הדפדפן.")
    st.stop()

# ✅ Navigation Bar
st.sidebar.title("🔹 ניווט")
selected_page = st.sidebar.radio("בחר דף", ["שיבוץ", "דוחות", "עריכת שיבוץ"])

# ✅ User identification
username = st.sidebar.text_input("🔑 שם משתמש לזיהוי", "")

# ✅ Truncate all שיבוצים with confirmation
if st.sidebar.button("🚮 מחק את כל השיבוצים"):
    st.session_state.confirm_delete = True

if "confirm_delete" in st.session_state and st.session_state.confirm_delete:
    st.sidebar.warning("❗ האם אתה בטוח שברצונך למחוק את כל השיבוצים?")
    if st.sidebar.button("⚠️ אישור מחיקה"):
        clear_all_assignments()
        st.cache_data.clear()
        st.session_state.page = "דוחות"
        st.rerun()
    if st.sidebar.button("❌ ביטול"):
        del st.session_state.confirm_delete
        st.rerun()

if st.sidebar.button("🚪 יציאה מהאפליקציה"):
    exit_app()

# ✅ Page 1: Assign students to tests ("שיבוץ")
if selected_page == "שיבוץ":
    st.title("שיבוץ תלמידים למבחנים")

    selected_year = st.selectbox("בחר שנה", YEARS)
    selected_period = st.selectbox("בחר תקופה", periods)
    selected_test = st.selectbox("בחר מבחן", test_ids)
    selected_class = st.selectbox("בחר כיתה", classes)

    filtered_students = students_df[students_df["כיתה"] == selected_class]
    student_list = filtered_students["שם תלמיד"].tolist()
    student_selected = st.multiselect("בחר תלמיד", student_list, default=student_list)

    if st.button("שמור שיבוץ"):
        if not username.strip():
            st.warning("⚠️ יש להזין שם משתמש לזיהוי לפני שמירת השיבוץ.")
        elif not student_selected:
            st.warning("⚠️ יש לבחור לפחות תלמיד אחד לשיבוץ.")
        else:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            for student in student_selected:
                c.execute("INSERT INTO assignments (year, period, test_id, class, student, edited_by) VALUES (?, ?, ?, ?, ?, ?)", 
                          (selected_year, selected_period, selected_test, selected_class, student, username))
            conn.commit()
            conn.close()
            
            st.cache_data.clear()
            st.rerun()

# ✅ Page 2: Reports ("דוחות")
elif selected_page == "דוחות":
    st.title("📊 דוחות מערכת")

    df_assignments = get_assignments()

    if df_assignments.empty:
        st.warning("⚠️ אין שיבוצים להצגה. נא להוסיף שיבוצים במסך 'שיבוץ'.")
    else:
        st.subheader("📋 דוח שיבוצים")
        st.dataframe(df_assignments)

        def export_csv():
            csv_path = "final_report.csv"
            df_assignments.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path

        if st.button("📥 הורד דוח CSV"):
            csv_path = export_csv()
            with open(csv_path, "rb") as file:
                st.download_button(label="⬇️ הורדת קובץ CSV", data=file, file_name="דוח_שיבוצים.csv", mime="text/csv")

# ✅ Page 3: Edit Assignments ("עריכת שיבוץ")
elif selected_page == "עריכת שיבוץ":
    st.title("✏️ עריכת שיבוץ")

    df_assignments = get_assignments()

    if df_assignments.empty:
        st.warning("⚠️ אין שיבוצים להצגה.")
    else:
        st.dataframe(df_assignments)
        selected_student = st.selectbox("בחר תלמיד לעריכה", df_assignments['student'])
        selected_row = df_assignments[df_assignments['student'] == selected_student].iloc[0]

        new_year = st.text_input("שנה", selected_row['year'])
        new_period = st.text_input("תקופה", selected_row['period'])
        new_test_id = st.text_input("מזהה מבחן", selected_row['test_id'])
        new_class = st.text_input("כיתה", selected_row['class'])
        new_student = st.text_input("תלמיד", selected_row['student'])

        if st.button("🔄 עדכן"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                UPDATE assignments SET year=?, period=?, test_id=?, class=?, student=? WHERE id=?
            """, (new_year, new_period, new_test_id, new_class, new_student, selected_row['id']))
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.rerun()