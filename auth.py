import streamlit as st
import hashlib
import os
from database import get_user, create_user, update_login

def generate_salt():
    """Generate random salt"""
    return os.urandom(32).hex()

def verify_password(password, stored_hash, salt):
    """Verify password"""
    return hashlib.sha256((password + salt).encode()).hexdigest() == stored_hash

def login_user(db_path, username, password):
    """Login user"""
    user = get_user(db_path, username)
    if not user:
        return False, "Username does not exist"
    
    if not verify_password(password, user['password_hash'], user['salt']):
        return False, "Incorrect password"
    
    update_login(db_path, user['user_id'])
    
    # Set session state
    st.session_state.authenticated = True
    st.session_state.user_id = user['user_id']
    st.session_state.username = user['username']
    st.session_state.is_admin = bool(user['is_admin'])
    
    return True, "Login successful"

def register_user(db_path, username, fullname, password):
    """Register new user"""
    user = get_user(db_path, username)
    if user:
        return False, "Username already exists"
    
    salt = generate_salt()
    user_id = create_user(db_path, username, fullname, password, salt)
    
    return bool(user_id), "Registration successful"

def logout_user():
    """Logout user"""
    for key in ['authenticated', 'user_id', 'username', 'is_admin']:
        if key in st.session_state:
            del st.session_state[key]