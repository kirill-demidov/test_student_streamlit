import os
import json
import base64
import gspread
import sqlite3
import pandas as pd
import streamlit as st
import sys
from oauth2client.service_account import ServiceAccountCredentials

# Hebrew UI Setup
st.set_page_config(page_title="מערכת ניהול מבחנים", layout="wide")

# Load Google Sheets credentials from environment variables
google_creds_base64 = os.getenv("GOOGLE_CREDENTIALS_JSON")

if google_creds_base64:
    google_creds_json = base64.b64decode(google_creds_base64).decode("utf-8")
    google_creds = json.loads(google_creds_json)
    client = gspread.service_account_from_dict(google_creds)
else:
    st.error("GOOGLE_CREDENTIALS_JSON לא מוגדר!")
    st.stop()

# Connect to Google Sheets
SHEET_ID = "1qKjn9TCi3myboBmBZkwM-36ENLigcN1NOt-l4d1ku2Y"
sheet = client.open_by_key(SHEET_ID)

# Setup SQLite database
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

# ✅ Exit Button Function
def exit_app():
    st.write("האפליקציה נסגרה. ניתן לסגור את הדפדפן.")
    sys.exit()

# ✅ Initialize session state for page switching
if "selected_student" not in st.session_state:
    st.session_state.selected_student = None

if "page" not in st.session_state:
    st.session_state.page = "חיבורים"

# ✅ Sidebar Navigation
st.sidebar.header("ניווט")
if st.sidebar.button("📌 חיבורים"):
    st.session_state.page = "חיבורים"
    st.rerun()

if st.sidebar.button("📊 דוחות"):
    st.session_state.page = "דוחות"
    st.rerun()

if st.sidebar.button("🚪 יציאה מהאפליקציה"):
    exit_app()

# ✅ Page 1: Assign students to tests
if st.session_state.page == "חיבורים":
    st.title("חיבור תלמידים למבחנים")

    # Load data from Google Sheets
    students = sheet.worksheet("שמות תלמידים").col_values(1)
    test_ids = sheet.worksheet("מספרים אקראיים").col_values(1)
    periods = sheet.worksheet("עונות").col_values(1)

    # Pre-fill student name if coming from "דוחות"
    student_selected = st.selectbox("בחר תלמיד", students, 
                                    index=students.index(st.session_state.selected_student) 
                                    if st.session_state.selected_student in students else 0)

    test_selected = st.selectbox("בחר מבחן", test_ids)
    period_selected = st.selectbox("בחר תקופה", periods)

    if st.button("שמור חיבור"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO assignments (student, test_id, period) VALUES (?, ?, ?)", 
                  (student_selected, test_selected, period_selected))
        conn.commit()
        conn.close()
        st.session_state.selected_student = None  # Clear selected student after assignment
        st.success(f"התלמיד {student_selected} חובר למבחן {test_selected} בתקופה {period_selected}")

# ✅ Page 2: Reports and Export to Excel
elif st.session_state.page == "דוחות":
    st.title("דוחות מערכת")

    conn = sqlite3.connect(DB_FILE)
    df_assignments = pd.read_sql_query("SELECT * FROM assignments", conn)

    # ✅ Final report (connected students)
    st.subheader("דוח חיבורים")
    if not df_assignments.empty:
        st.dataframe(df_assignments)

        # Export final report to Excel
        def export_final_report():
            df_assignments.to_excel("final_report.xlsx", index=False, engine="openpyxl")
            return "final_report.xlsx"

        if st.button("הורד דוח חיבורים"):
            excel_path = export_final_report()
            with open(excel_path, "rb") as file:
                st.download_button(label="הורדת קובץ אקסל", data=file, file_name="דוח_חיבורים.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("אין חיבורים רשומים.")

    # ✅ Report for students not connected to tests (Displayed as List with Connection Button)
    st.subheader("תלמידים לא מחוברים")
    students = sheet.worksheet("שמות תלמידים").col_values(1)
    connected_students = df_assignments["student"].tolist() if not df_assignments.empty else []
    unconnected_students = [s for s in students if s not in connected_students]

    if unconnected_students:
        st.write("**רשימת התלמידים שאינם מחוברים למבחנים:**")

        for student in unconnected_students:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(student)
            with col2:
                if st.button(f"חבר {student}", key=f"connect_{student}"):
                    st.session_state.selected_student = student
                    st.session_state.page = "חיבורים"
                    st.rerun()  # ✅ Switch to "חיבורים" and pre-fill student name

        # Export unconnected students report to Excel
        def export_unconnected_report():
            df_unconnected = pd.DataFrame({"תלמידים לא מחוברים": unconnected_students})
            df_unconnected.to_excel("unconnected_students.xlsx", index=False, engine="openpyxl")
            return "unconnected_students.xlsx"

        if st.button("הורד רשימת תלמידים לא מחוברים"):
            excel_path = export_unconnected_report()
            with open(excel_path, "rb") as file:
                st.download_button(label="הורדת קובץ אקסל", data=file, file_name="תלמידים_לא_מחוברים.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.success("כל התלמידים מחוברים למבחנים!")

    conn.close()