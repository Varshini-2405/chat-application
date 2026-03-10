import streamlit as st
import sqlite3
import datetime
import hashlib
import base64
from streamlit_autorefresh import st_autorefresh

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('raven_chat_v3.db', check_same_thread=False)
    c = conn.cursor()
    # Updated messages: type can be 'text', 'image', 'video', 'audio', 'file'
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (sender TEXT, receiver_type TEXT, receiver_id TEXT, content TEXT, 
                  file_data BLOB, file_name TEXT, file_type TEXT, timestamp DATETIME)''')
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Groups table: stores only group metadata
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (group_id TEXT PRIMARY KEY, group_name TEXT, creator TEXT)''')
    # Group members table
    c.execute('''CREATE TABLE IF NOT EXISTS group_members 
                 (group_id TEXT, username TEXT, PRIMARY KEY (group_id, username))''')
    conn.commit()
    return conn

conn = init_db()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- APP CONFIG ---
st.set_page_config(page_title="Raven Messenger Pro", page_icon="🐦‍⬛", layout="wide")
st_autorefresh(interval=3000, key="ravensync_pro")

# --- CSS (Dark Mode & Media Styling) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0c0d10; color: #e1e1e1; }
    
    section[data-testid="stSidebar"] {
        background-color: #16171d !important;
        border-right: 1px solid #2d2e3a;
    }

    .bubble { padding: 12px 18px; border-radius: 12px; margin-bottom: 8px; max-width: 80%; }
    .out { background: #7c4dff; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .in { background: #2d2e3a; color: #e1e1e1; margin-right: auto; border-bottom-left-radius: 2px; }
    
    .raven-logo { font-size: 2rem; font-weight: 800; color: #7c4dff; margin-bottom: 15px; }
    .sidebar-header { font-size: 0.75rem; color: #8e8e93; font-weight: 700; margin-top: 25px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
    
    .media-container img, .media-container video { border-radius: 10px; max-width: 100%; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'username' not in st.session_state:
    st.session_state.username = None

# Unique key for file uploader to prevent duplicates
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# Ensure active_chat is a dictionary
if 'active_chat' not in st.session_state or isinstance(st.session_state.active_chat, str):
    st.session_state.active_chat = {"type": "Global", "id": "Global", "name": "Global Group"}

# --- AUTHENTICATION ---
if st.session_state.username is None:
    st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center;' class='raven-logo'>RAVEN PRO</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        l_user = st.text_input("Username", key="l_user")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login", use_container_width=True):
            res = conn.execute("SELECT password FROM users WHERE username = ?", (l_user,)).fetchone()
            if res and res[0] == hash_password(l_pass):
                st.session_state.username = l_user
                st.rerun()
            else: st.error("Invalid Credentials")
    with tab2:
        r_user = st.text_input("Choose Username", key="r_user")
        r_pass = st.text_input("Choose Password", type="password", key="r_pass")
        if st.button("Register", use_container_width=True):
            if r_user and r_pass:
                try:
                    conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (r_user, hash_password(r_pass)))
                    conn.commit()
                    st.success("Account created!")
                except: st.error("Username taken!")
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("<h2 class='raven-logo' style='font-size:1.5rem;'>Raven</h2>", unsafe_allow_html=True)
        st.caption(f"Status: **{st.session_state.username}** (Online)")

        # Create Private Group
        with st.expander("➕ Create Private Group"):
            g_name = st.text_input("Group Name")
            c = conn.cursor()
            c.execute("SELECT username FROM users WHERE username != ?", (st.session_state.username,))
            available_users = [row[0] for row in c.fetchall()]
            members = st.multiselect("Add Members", available_users)
            if st.button("Create"):
                if g_name and members:
                    g_id = hashlib.md5(f"{g_name}{st.session_state.username}{datetime.datetime.now()}".encode()).hexdigest()[:8]
                    conn.execute("INSERT INTO groups (group_id, group_name, creator) VALUES (?, ?, ?)", (g_id, g_name, st.session_state.username))
                    conn.execute("INSERT INTO group_members (group_id, username) VALUES (?, ?)", (g_id, st.session_state.username))
                    for m in members:
                        conn.execute("INSERT INTO group_members (group_id, username) VALUES (?, ?)", (g_id, m))
                    conn.commit()
                    st.success(f"Group '{g_name}' created!")
                    st.rerun()

        st.markdown("<div class='sidebar-header'>MY GROUPS</div>", unsafe_allow_html=True)
        # Fetch groups I am a member of
        c = conn.cursor()
        c.execute("""SELECT g.group_id, g.group_name FROM groups g 
                     JOIN group_members m ON g.group_id = m.group_id 
                     WHERE m.username = ?""", (st.session_state.username,))
        my_groups = c.fetchall()
        for gid, gname in my_groups:
            if st.button(f"👥 {gname}", key=f"g_{gid}", use_container_width=True, 
                         type="primary" if st.session_state.active_chat["id"] == gid else "secondary"):
                st.session_state.active_chat = {"type": "Group", "id": gid, "name": gname}
                st.rerun()

        st.markdown("<div class='sidebar-header'>DIRECT MESSAGES</div>", unsafe_allow_html=True)
        # Fetch users with chat history
        c.execute("""SELECT DISTINCT sender FROM messages WHERE receiver_id = ? AND receiver_type = 'Direct'
                     UNION 
                     SELECT DISTINCT receiver_id FROM messages WHERE sender = ? AND receiver_type = 'Direct'""",
                  (st.session_state.username, st.session_state.username))
        recent_dms = [row[0] for row in c.fetchall()]
        for dm in recent_dms:
            if st.button(f"👤 {dm}", key=f"dm_{dm}", use_container_width=True,
                         type="primary" if st.session_state.active_chat["id"] == dm else "secondary"):
                st.session_state.active_chat = {"type": "Direct", "id": dm, "name": dm}
                st.rerun()
        
        # New Chat Search
        search = st.text_input("🔍 Find User", key="search")
        if st.button("Message User", use_container_width=True):
            if conn.execute("SELECT username FROM users WHERE username = ?", (search,)).fetchone():
                st.session_state.active_chat = {"type": "Direct", "id": search, "name": search}
                st.rerun()
            else: st.error("User not found.")

        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.username = None
            st.rerun()

    # --- MAIN CHAT WINDOW ---
    active = st.session_state.active_chat
    st.markdown(f"""
        <div style="background: #16171d; padding: 15px 25px; border-radius: 12px; margin-bottom: 20px; border-bottom: 2px solid #7c4dff;">
            <h3 style="margin:0;">{active.get('name', 'Select a Chat')}</h3>
        </div>
    """, unsafe_allow_html=True)

    # Load Messages
    c = conn.cursor()
    if active["type"] == "Group":
        c.execute("SELECT sender, content, file_data, file_name, file_type, timestamp FROM messages WHERE receiver_id = ? AND receiver_type = 'Group' ORDER BY timestamp ASC", (active["id"],))
    elif active["type"] == "Direct":
        c.execute("""SELECT sender, content, file_data, file_name, file_type, timestamp FROM messages 
                     WHERE receiver_type = 'Direct' AND 
                     ((sender = ? AND receiver_id = ?) OR (sender = ? AND receiver_id = ?)) 
                     ORDER BY timestamp ASC""", 
                  (st.session_state.username, active["id"], active["id"], st.session_state.username))
    messages = c.fetchall()

    for m in messages:
        sender, txt, f_data, f_name, f_type, ts = m
        is_me = sender == st.session_state.username
        st.markdown(f"""<div style="display: flex; flex-direction: column;"><div style="font-size:0.7rem; color:#8e8e93; align-self: {'flex-end' if is_me else 'flex-start'};">{sender if not is_me else 'You'}</div><div class="bubble {'out' if is_me else 'in'}">""", unsafe_allow_html=True)
        
        if txt: st.markdown(txt)
        if f_data:
            if "image" in f_type: st.image(f_data)
            elif "video" in f_type: st.video(f_data)
            elif "audio" in f_type: st.audio(f_data)
            else: st.download_button(f"📄 {f_name}", f_data, file_name=f_name)
            
        st.markdown(f"""<div style="font-size:0.6rem; opacity:0.5; text-align:right;">{ts}</div></div></div>""", unsafe_allow_html=True)

    # --- INPUT ---
    with st.container():
        cols = st.columns([0.8, 0.2])
        with cols[0]:
            msg_input = st.chat_input(f"Write to {active.get('name', '...')} (Emojis supported!)")
        with cols[1]:
            # Use dynamic key so it resets after sending
            uploaded_file = st.file_uploader("📎", label_visibility="collapsed", key=f"uploader_{st.session_state.uploader_key}")

        if msg_input or uploaded_file:
            content = msg_input if msg_input else ""
            f_blob = None
            f_name = None
            f_type = ""
            
            if uploaded_file:
                f_blob = uploaded_file.read()
                f_name = uploaded_file.name
                f_type = uploaded_file.type
                st.session_state.uploader_key += 1 # Reset the uploader by changing its key
                
            now = datetime.datetime.now().strftime("%I:%M %p")
            conn.execute("INSERT INTO messages (sender, receiver_type, receiver_id, content, file_data, file_name, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (st.session_state.username, active["type"], active["id"], content, f_blob, f_name, f_type, now))
            conn.commit()
            st.rerun()
