import streamlit as st
import sys
import os
import json

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.core.crud import get_user_profile, save_user_profile
from src.core.resume_parser import parse_resume_from_bytes

st.set_page_config(page_title="Profile & Resume", page_icon="📝")

st.title("📝 Profile & Resume")
st.markdown("Upload your resume and configure the personal details the agent will use for applications.")

# Load existing profile
profile = get_user_profile()

# Parse existing custom_qa JSON into a dictionary
custom_qa_dict = {}
if profile.get("custom_qa"):
    try:
        custom_qa_dict = json.loads(profile.get("custom_qa"))
    except:
        pass

with st.form("profile_form"):
    st.subheader("1. Personal Details")
    col1, col2, col3 = st.columns(3)
    with col1:
        full_name = st.text_input("Full Name", value=profile.get("full_name", ""))
        pronouns = st.text_input("Pronouns (e.g. He/Him)", value=custom_qa_dict.get("Pronouns", ""))
    with col2:
        email = st.text_input("Email", value=profile.get("email", ""))
        phone = st.text_input("Phone", value=profile.get("phone", ""))
    with col3:
        location = st.text_input("Location (City, State)", value=profile.get("location", ""))
        country = st.text_input("Country", value=custom_qa_dict.get("Country", "India"))
        
    st.subheader("2. Online Presence")
    col4, col5 = st.columns(2)
    with col4:
        portfolio_url = st.text_input("LinkedIn Profile URL", value=profile.get("portfolio_url", ""))
        personal_website = st.text_input("Personal Website", value=custom_qa_dict.get("Personal Website", ""))
    with col5:
        github_url = st.text_input("GitHub URL", value=profile.get("github_url", ""))
        twitter_url = st.text_input("Twitter / X URL", value=custom_qa_dict.get("Twitter URL", ""))
        
    st.subheader("3. Career & Compensation")
    col6, col7, col8 = st.columns(3)
    with col6:
        years_experience = st.number_input("Total Years of Experience", min_value=0, max_value=50, value=profile.get("years_experience", 0))
        current_title = st.text_input("Current Job Title", value=custom_qa_dict.get("Current Job Title", ""))
        current_company = st.text_input("Current Company", value=custom_qa_dict.get("Current Company", ""))
    with col7:
        current_ctc = st.text_input("Current CTC (INR)", value=custom_qa_dict.get("Current CTC", ""))
        expected_ctc = st.text_input("Expected CTC (INR)", value=custom_qa_dict.get("Expected CTC", ""))
        notice_period = st.text_input("Notice Period (Days)", value=custom_qa_dict.get("Notice Period", ""))
    with col8:
        relocate = st.selectbox("Willing to Relocate?", ["Yes", "No"], index=0 if custom_qa_dict.get("Willing to Relocate", "Yes") == "Yes" else 1)
        work_pref = st.selectbox("Work Preference", ["Remote", "Hybrid", "On-site", "Any"], index=["Remote", "Hybrid", "On-site", "Any"].index(custom_qa_dict.get("Work Preference", "Any")))
        start_date = st.text_input("Available Start Date", value=custom_qa_dict.get("Available Start Date", "Immediate"))


    st.subheader("4. Education")
    
    edu_tab1, edu_tab2, edu_tab3 = st.tabs(["🎓 Graduation (BTech / Degree)", "📗 12th Grade (Intermediate)", "📘 10th Grade (Matriculation)"])
    
    with edu_tab1:
        col9a, col9b = st.columns(2)
        with col9a:
            degree = st.selectbox("Degree", ["High School", "Associate Degree", "Bachelor's Degree", "Master's Degree", "Ph.D."], index=["High School", "Associate Degree", "Bachelor's Degree", "Master's Degree", "Ph.D."].index(custom_qa_dict.get("Highest Degree", "Bachelor's Degree")))
            university = st.text_input("University / College Name", value=custom_qa_dict.get("University", ""))
        with col9b:
            major = st.text_input("Major / Field of Study", value=custom_qa_dict.get("Major", ""))
            gpa = st.text_input("CGPA / GPA (e.g. 8.5)", value=custom_qa_dict.get("GPA", ""))

    with edu_tab2:
        col10a, col10b = st.columns(2)
        with col10a:
            school_12 = st.text_input("School / College Name (12th)", value=custom_qa_dict.get("12th School", ""), key="school_12")
            board_12  = st.text_input("Board (e.g. CBSE, ICSE, State)", value=custom_qa_dict.get("12th Board", ""), key="board_12")
        with col10b:
            marks_12   = st.text_input("Marks / Percentage / CGPA", value=custom_qa_dict.get("12th Marks", ""), key="marks_12")
            passout_12 = st.text_input("Year of Passing", value=custom_qa_dict.get("12th Passout Year", ""), key="passout_12")

    with edu_tab3:
        col11a, col11b = st.columns(2)
        with col11a:
            school_10 = st.text_input("School Name (10th)", value=custom_qa_dict.get("10th School", ""), key="school_10")
            board_10  = st.text_input("Board (e.g. CBSE, ICSE, State)", value=custom_qa_dict.get("10th Board", ""), key="board_10")
        with col11b:
            marks_10   = st.text_input("Marks / Percentage / CGPA", value=custom_qa_dict.get("10th Marks", ""), key="marks_10")
            passout_10 = st.text_input("Year of Passing", value=custom_qa_dict.get("10th Passout Year", ""), key="passout_10")

    st.subheader("5. Key Skills (For 'Years of experience in X' questions)")
    col11, col12 = st.columns(2)
    with col11:
        skill_1 = st.text_input("Top Skill 1 (e.g. Python)", value=custom_qa_dict.get("Top Skill 1", ""))
        skill_2 = st.text_input("Top Skill 2 (e.g. React)", value=custom_qa_dict.get("Top Skill 2", ""))
    with col12:
        skill_1_years = st.text_input("Years in Skill 1", value=custom_qa_dict.get("Years in Skill 1", ""))
        skill_2_years = st.text_input("Years in Skill 2", value=custom_qa_dict.get("Years in Skill 2", ""))

    st.subheader("6. Work Authorization")
    work_auth_options = ["US Citizen", "Green Card", "H1B", "OPT/CPT", "Requires Sponsorship", "Not Applicable", "Indian Citizen"]
    current_auth = profile.get("work_authorization", "Indian Citizen")
    if current_auth not in work_auth_options:
        current_auth = "Indian Citizen"
        
    col13, col14, col15 = st.columns(3)
    with col13:
        work_authorization = st.selectbox("Citizenship Status", options=work_auth_options, index=work_auth_options.index(current_auth))
    with col14:
        sponsorship = st.selectbox("Require Visa Sponsorship?", ["No", "Yes"], index=0 if custom_qa_dict.get("Requires Sponsorship", "No") == "No" else 1)
    with col15:
        clearance = st.selectbox("Security Clearance?", ["No", "Yes"], index=0 if custom_qa_dict.get("Security Clearance", "No") == "No" else 1)

    st.subheader("7. Equal Employment (EEO)")
    col16, col17 = st.columns(2)
    with col16:
        gender = st.selectbox("Gender", ["Prefer not to say", "Male", "Female", "Non-binary"], index=["Prefer not to say", "Male", "Female", "Non-binary"].index(custom_qa_dict.get("Gender", "Prefer not to say")))
        veteran = st.selectbox("Veteran Status", ["Prefer not to say", "I am not a protected veteran", "I identify as one or more of the classifications of a protected veteran"], index=0)
    with col17:
        disability = st.selectbox("Disability Status", ["Prefer not to say", "No, I don't have a disability", "Yes, I have a disability"], index=0)
        race = st.selectbox("Race/Ethnicity", ["Prefer not to say", "Asian", "White", "Black or African American", "Hispanic or Latino", "Other"], index=0)

    st.subheader("8. Additional Custom QA")
    other_qa_text = custom_qa_dict.get("Other QA", "")
    other_qa = st.text_area("Format: Question: Answer (One per line)", value=other_qa_text, height=100)

    st.subheader("9. Personal Statement")
    st.markdown("*Used for 'Tell us about yourself' or 'Cover letter' fields in application forms.*")
    personal_statement = st.text_area("Your elevator pitch (2-3 sentences)", value=custom_qa_dict.get("Personal Statement", ""), height=80, key="personal_statement")

    st.subheader("10. Certifications")
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        cert_1_name  = st.text_input("Certification 1 Name", value=custom_qa_dict.get("Cert 1 Name", ""), key="cert_1_name")
        cert_1_body  = st.text_input("Issuing Body (e.g. Google, AWS)", value=custom_qa_dict.get("Cert 1 Body", ""), key="cert_1_body")
        cert_1_year  = st.text_input("Year Earned", value=custom_qa_dict.get("Cert 1 Year", ""), key="cert_1_year")
    with col_c2:
        cert_2_name  = st.text_input("Certification 2 Name", value=custom_qa_dict.get("Cert 2 Name", ""), key="cert_2_name")
        cert_2_body  = st.text_input("Issuing Body", value=custom_qa_dict.get("Cert 2 Body", ""), key="cert_2_body")
        cert_2_year  = st.text_input("Year Earned", value=custom_qa_dict.get("Cert 2 Year", ""), key="cert_2_year")
    with col_c3:
        cert_3_name  = st.text_input("Certification 3 Name", value=custom_qa_dict.get("Cert 3 Name", ""), key="cert_3_name")
        cert_3_body  = st.text_input("Issuing Body", value=custom_qa_dict.get("Cert 3 Body", ""), key="cert_3_body")
        cert_3_year  = st.text_input("Year Earned", value=custom_qa_dict.get("Cert 3 Year", ""), key="cert_3_year")

    st.subheader("11. Languages")
    col_l1, col_l2 = st.columns(2)
    lang_prof_opts = ["Native", "Fluent", "Conversational", "Basic"]
    with col_l1:
        lang_1      = st.text_input("Language 1 (e.g. Hindi)", value=custom_qa_dict.get("Language 1", ""), key="lang_1")
        lang_1_prof = st.selectbox("Proficiency", lang_prof_opts, index=lang_prof_opts.index(custom_qa_dict.get("Language 1 Proficiency", "Native")), key="lang_1_prof")
    with col_l2:
        lang_2      = st.text_input("Language 2 (e.g. English)", value=custom_qa_dict.get("Language 2", ""), key="lang_2")
        lang_2_prof = st.selectbox("Proficiency", lang_prof_opts, index=lang_prof_opts.index(custom_qa_dict.get("Language 2 Proficiency", "Fluent")), key="lang_2_prof")

    st.subheader("12. Projects")
    proj_tab1, proj_tab2 = st.tabs(["Project 1", "Project 2"])
    with proj_tab1:
        col_p1a, col_p1b = st.columns(2)
        with col_p1a:
            proj_1_name  = st.text_input("Project Name", value=custom_qa_dict.get("Project 1 Name", ""), key="proj_1_name")
            proj_1_stack = st.text_input("Tech Stack (e.g. Python, React, AWS)", value=custom_qa_dict.get("Project 1 Stack", ""), key="proj_1_stack")
        with col_p1b:
            proj_1_url   = st.text_input("GitHub / Live URL", value=custom_qa_dict.get("Project 1 URL", ""), key="proj_1_url")
            proj_1_desc  = st.text_input("Brief Description", value=custom_qa_dict.get("Project 1 Desc", ""), key="proj_1_desc")
    with proj_tab2:
        col_p2a, col_p2b = st.columns(2)
        with col_p2a:
            proj_2_name  = st.text_input("Project Name", value=custom_qa_dict.get("Project 2 Name", ""), key="proj_2_name")
            proj_2_stack = st.text_input("Tech Stack", value=custom_qa_dict.get("Project 2 Stack", ""), key="proj_2_stack")
        with col_p2b:
            proj_2_url   = st.text_input("GitHub / Live URL", value=custom_qa_dict.get("Project 2 URL", ""), key="proj_2_url")
            proj_2_desc  = st.text_input("Brief Description", value=custom_qa_dict.get("Project 2 Desc", ""), key="proj_2_desc")

    st.subheader("13. References")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        ref_1_name    = st.text_input("Reference 1 Name", value=custom_qa_dict.get("Ref 1 Name", ""), key="ref_1_name")
        ref_1_title   = st.text_input("Designation", value=custom_qa_dict.get("Ref 1 Title", ""), key="ref_1_title")
        ref_1_company = st.text_input("Company", value=custom_qa_dict.get("Ref 1 Company", ""), key="ref_1_company")
        ref_1_email   = st.text_input("Email", value=custom_qa_dict.get("Ref 1 Email", ""), key="ref_1_email")
    with col_r2:
        ref_2_name    = st.text_input("Reference 2 Name", value=custom_qa_dict.get("Ref 2 Name", ""), key="ref_2_name")
        ref_2_title   = st.text_input("Designation", value=custom_qa_dict.get("Ref 2 Title", ""), key="ref_2_title")
        ref_2_company = st.text_input("Company", value=custom_qa_dict.get("Ref 2 Company", ""), key="ref_2_company")
        ref_2_email   = st.text_input("Email", value=custom_qa_dict.get("Ref 2 Email", ""), key="ref_2_email")

    st.subheader("14. Emergency Contact")
    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        emergency_name     = st.text_input("Emergency Contact Name", value=custom_qa_dict.get("Emergency Contact Name", ""), key="emergency_name")
    with col_e2:
        emergency_relation = st.text_input("Relationship (e.g. Parent)", value=custom_qa_dict.get("Emergency Contact Relation", ""), key="emergency_relation")
    with col_e3:
        emergency_phone    = st.text_input("Phone Number", value=custom_qa_dict.get("Emergency Contact Phone", ""), key="emergency_phone")

    st.subheader("15. Resume Upload")
    uploaded_resume = st.file_uploader("Upload your Resume (PDF)", type=["pdf"])

    submit = st.form_submit_button("Save Profile")
    
    if submit:
        resume_text = profile.get("resume_text", "")
        resume_parsed_data = profile.get("resume_parsed_data", "")
        
        # If new resume uploaded, parse it
        if uploaded_resume is not None:
            with st.spinner("Parsing resume..."):
                parsed = parse_resume_from_bytes(uploaded_resume)
                resume_text = parsed["raw_text"]
                resume_parsed_data = parsed["structured_data"]
                st.success("Resume parsed successfully!")
                
        # Package everything back into custom_qa JSON
        new_custom_qa = {
            "Pronouns": pronouns,
            "Country": country,
            "Personal Website": personal_website,
            "Twitter URL": twitter_url,
            "Current Job Title": current_title,
            "Current Company": current_company,
            "Current CTC": current_ctc,
            "Expected CTC": expected_ctc,
            "Notice Period": notice_period,
            "Willing to Relocate": relocate,
            "Work Preference": work_pref,
            "Available Start Date": start_date,
            "Highest Degree": degree,
            "University": university,
            "Major": major,
            "GPA": gpa,
            "12th School": school_12,
            "12th Board": board_12,
            "12th Marks": marks_12,
            "12th Passout Year": passout_12,
            "10th School": school_10,
            "10th Board": board_10,
            "10th Marks": marks_10,
            "10th Passout Year": passout_10,
            f"Years of experience in {skill_1}": skill_1_years if skill_1 else "",
            f"Years of experience in {skill_2}": skill_2_years if skill_2 else "",
            "Requires Sponsorship": sponsorship,
            "Security Clearance": clearance,
            "Gender": gender,
            "Veteran Status": veteran,
            "Disability Status": disability,
            "Race/Ethnicity": race,
            "Other QA": other_qa.strip(),
            "Personal Statement": personal_statement,
            "Cert 1 Name": cert_1_name,
            "Cert 1 Body": cert_1_body,
            "Cert 1 Year": cert_1_year,
            "Cert 2 Name": cert_2_name,
            "Cert 2 Body": cert_2_body,
            "Cert 2 Year": cert_2_year,
            "Cert 3 Name": cert_3_name,
            "Cert 3 Body": cert_3_body,
            "Cert 3 Year": cert_3_year,
            "Language 1": lang_1,
            "Language 1 Proficiency": lang_1_prof,
            "Language 2": lang_2,
            "Language 2 Proficiency": lang_2_prof,
            "Project 1 Name": proj_1_name,
            "Project 1 Stack": proj_1_stack,
            "Project 1 URL": proj_1_url,
            "Project 1 Desc": proj_1_desc,
            "Project 2 Name": proj_2_name,
            "Project 2 Stack": proj_2_stack,
            "Project 2 URL": proj_2_url,
            "Project 2 Desc": proj_2_desc,
            "Ref 1 Name": ref_1_name,
            "Ref 1 Title": ref_1_title,
            "Ref 1 Company": ref_1_company,
            "Ref 1 Email": ref_1_email,
            "Ref 2 Name": ref_2_name,
            "Ref 2 Title": ref_2_title,
            "Ref 2 Company": ref_2_company,
            "Ref 2 Email": ref_2_email,
            "Emergency Contact Name": emergency_name,
            "Emergency Contact Relation": emergency_relation,
            "Emergency Contact Phone": emergency_phone,
        }
        
        # Remove empty keys so we don't confuse Groq with blanks
        new_custom_qa = {k: v for k, v in new_custom_qa.items() if v and v != "Prefer not to say"}
        
        qa_json = json.dumps(new_custom_qa)

        # Save to DB
        save_user_profile({
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "location": location,
            "portfolio_url": portfolio_url,
            "github_url": github_url,
            "years_experience": years_experience,
            "work_authorization": work_authorization,
            "custom_qa": qa_json,
            "resume_text": resume_text,
            "resume_parsed_data": resume_parsed_data
        })
        st.success("Profile saved successfully!")

# Show current resume status outside the form
if profile.get("resume_text"):
    st.info("A resume is currently saved in your profile.")
    with st.expander("View Parsed Resume Text"):
        st.text(profile.get("resume_text"))
