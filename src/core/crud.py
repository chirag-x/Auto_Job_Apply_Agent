from .db import get_db_connection

def get_all_llm_configs():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llm_config ORDER BY priority ASC")
        return [dict(row) for row in cursor.fetchall()]

def save_llm_config(provider, api_key, base_url, model_name, priority, is_active=True, config_id=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if config_id:
            cursor.execute('''
                UPDATE llm_config 
                SET provider = ?, api_key = ?, base_url = ?, model_name = ?, priority = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (provider, api_key, base_url, model_name, priority, is_active, config_id))
        else:
            cursor.execute('''
                INSERT INTO llm_config (provider, api_key, base_url, model_name, priority, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (provider, api_key, base_url, model_name, priority, is_active))
        conn.commit()

def delete_llm_config(config_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM llm_config WHERE id = ?", (config_id,))
        conn.commit()

def get_user_profile():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profile ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else {}

def save_user_profile(data):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM user_profile LIMIT 1")
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE user_profile 
                SET full_name = ?, email = ?, phone = ?, location = ?, portfolio_url = ?, 
                    github_url = ?, years_experience = ?, work_authorization = ?, 
                    custom_qa = ?, resume_text = ?, resume_parsed_data = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('full_name'), data.get('email'), data.get('phone'), data.get('location'), 
                data.get('portfolio_url'), data.get('github_url'), data.get('years_experience'), 
                data.get('work_authorization'), data.get('custom_qa'), data.get('resume_text'), 
                data.get('resume_parsed_data'), existing['id']
            ))
        else:
            cursor.execute('''
                INSERT INTO user_profile (
                    full_name, email, phone, location, portfolio_url, github_url, 
                    years_experience, work_authorization, custom_qa, resume_text, resume_parsed_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('full_name'), data.get('email'), data.get('phone'), data.get('location'), 
                data.get('portfolio_url'), data.get('github_url'), data.get('years_experience'), 
                data.get('work_authorization'), data.get('custom_qa'), data.get('resume_text'), 
                data.get('resume_parsed_data')
            ))
        conn.commit()

