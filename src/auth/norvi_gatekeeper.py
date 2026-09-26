import os
import json
import time
import uuid
import platform
import urllib.request
import urllib.error
import streamlit as st

API_BASE_URL = os.getenv("NORVI_API_URL", "http://localhost:4321")
LEASE_FILE = os.path.join(os.path.expanduser("~"), ".norvi_rolvio_lease")

def get_hardware_id():
    mac = uuid.getnode()
    return f"{platform.node()}-{mac}"

def load_lease():
    if not os.path.exists(LEASE_FILE):
        return None
    try:
        with open(LEASE_FILE, 'r') as f:
            data = json.load(f)
            # Check expiry
            if data.get("expires_at"):
                exp = data["expires_at"]
                if time.time() > exp:
                    return None
            return data
    except Exception:
        return None

def save_lease(token, expires_at):
    try:
        with open(LEASE_FILE, 'w') as f:
            json.dump({"token": token, "expires_at": expires_at}, f)
    except Exception as e:
        print(f"Failed to save lease: {e}")

def require_license(product_slug):
    lease = load_lease()
    if lease:
        return True
        
    
    # HIDE SIDEBAR SO THEY CANNOT CLICK OTHER PAGES
    st.markdown("""
        <style>
            [data-testid="collapsedControl"] { display: none !important; }
            [data-testid="stSidebar"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='text-align: center;'>Agent Activation Required</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Please log in to your NORVI account and enter your activation key.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("activation_form"):
            email = st.text_input("NORVI Email")
            password = st.text_input("Password", type="password")
            key = st.text_input("Activation Key (NORVI-XXXX-...)")
            submit = st.form_submit_button("Activate & Launch", use_container_width=True)
            
            if submit:
                if not email or not password or not key:
                    st.error("All fields are required.")
                else:
                    try:
                        # Step 1: Login
                        req1 = urllib.request.Request(
                            f"{API_BASE_URL}/api/agent-auth/login",
                            data=json.dumps({"email": email, "password": password}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}
                        )
                        try:
                            with urllib.request.urlopen(req1) as response:
                                res1 = json.loads(response.read().decode())
                        except urllib.error.HTTPError as e:
                            err_data = json.loads(e.read().decode())
                            raise Exception(err_data.get("error", "Login failed."))
                            
                        access_token = res1.get("access_token")
                        if not access_token:
                            raise Exception("No access token returned.")
                            
                        # Step 2: Activate
                        hwid = get_hardware_id()
                        req2 = urllib.request.Request(
                            f"{API_BASE_URL}/api/agent-auth/activate",
                            data=json.dumps({
                                "licenseKey": key,
                                "deviceId": hwid,
                                "productSlug": product_slug
                            }).encode("utf-8"),
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {access_token}"
                            }
                        )
                        
                        try:
                            with urllib.request.urlopen(req2) as response:
                                res2 = json.loads(response.read().decode())
                        except urllib.error.HTTPError as e:
                            err_data = json.loads(e.read().decode())
                            raise Exception(err_data.get("error", "Activation failed."))
                            
                        lease_token = res2.get("lease")
                        
                        # Decode JWT
                        parts = lease_token.split('.')
                        if len(parts) >= 2:
                            import base64
                            payload = parts[1]
                            payload += '=' * (-len(payload) % 4)
                            decoded = json.loads(base64.b64decode(payload).decode())
                            exp = decoded.get("exp", time.time() + (7*24*60*60))
                        else:
                            exp = time.time() + (7*24*60*60)
                            
                        save_lease(lease_token, exp)
                        st.success("Agent activated successfully! Reloading...")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(str(e))
                        
    st.stop()
