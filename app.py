import streamlit as st
import os

from auth import login_user, register_user, logout_user
from mos_eval import show_mos_evaluation
from pairwise import show_ab_evaluation
from dashboard import show_results
from config import DB_URL 
# Setup page config

# DEBUG_MODE = True  #  False if not debug

# if DEBUG_MODE and "authenticated" not in st.session_state:
#     st.session_state.authenticated = True
#     st.session_state.user_id = 1  
#     st.session_state.username = "admin"
#     st.session_state.is_admin = True
#     st.session_state.page = "home"
st.set_page_config(page_title="TTS Evaluation", page_icon="🔊", layout="wide")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.is_admin = False
    st.session_state.page = "login"

# Page functions
def show_login():
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if not username or not password:
                st.error("Please enter all required information")
            else:
                success, message = login_user(DB_URL, username, password)
                if success:
                    st.success(message)
                    st.session_state.page = "home"
                    st.rerun()
                else:
                    st.error(message)
    
    if st.button("Register an account"):
        st.session_state.page = "register"
        st.rerun()

def show_register():
    st.title("Register Account")
    with st.form("register_form"):
        username = st.text_input("Username")
        fullname = st.text_input("Full Name")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register")
        
        if submitted:
            if not username or not fullname or not password:
                st.error("Please enter all required information")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif password != confirm:
                st.error("Password confirmation doesn't match")
            else:
                success, message = register_user(DB_URL, username, fullname, password)
                if success:
                    st.success(message)
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error(message)
    
    if st.button("Already have an account? Login"):
        st.session_state.page = "login"
        st.rerun()

def show_home():
    st.title("Speech Quality Evaluation")
    st.write("""
    Welcome to the Text-to-Speech (TTS) Evaluation System!
    
    This system allows you to:
    - Evaluate speech quality using MOS (Mean Opinion Score)
    - Compare different TTS models through A/B tests
    - View aggregated evaluation results
    
    Please select a function from the left sidebar.
    """)

# Sidebar navigation
def show_sidebar():
    with st.sidebar:
        st.title("TTS Evaluation")
        
        if st.session_state.authenticated:
            st.write(f"Hello, **{st.session_state.username}**!")
            
            if st.session_state.is_admin:
                pages = ["Home", "MOS Evaluation", "A/B Evaluation", "Results"]
            else:
                pages = ["Home", "MOS Evaluation", "A/B Evaluation"]

            choice = st.selectbox("Menu", pages)
            
            if st.button("Logout"):
                logout_user()
                st.rerun()
            
            return choice
        else:
            return st.session_state.page

# Main app
def main():
    page = show_sidebar()
    
    if not st.session_state.authenticated:
        if page == "login":
            show_login()
        elif page == "register":
            show_register()
        else:
            show_login()
    else:
        if page == "Home":
            show_home()
        elif page == "MOS Evaluation":
            show_mos_evaluation()
        elif page == "A/B Evaluation":
            show_ab_evaluation()
        elif page == "Results":
            show_results()
        else:
            show_home()

if __name__ == "__main__":
    main()