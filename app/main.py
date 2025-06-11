# app/main.py
import streamlit as st
import asyncio
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional

# Core imports
from app.core.cv_processor import CVProcessor
from app.core.form_detector import FormDetector
from app.core.automation_engine import AutomationEngine as BackgroundTaskAutomationEngine
from app.core.form_detector import AutomationEngine as FormFillingAutomationEngine
from app.core.chat_interface import ChatInterface
from app.core.notification_service import NotificationService
from app.database.models import CandidateSession, JobListing, Application
from app.utils.gdpr_compliance import GDPRManager

# Configuration
st.set_page_config(
    page_title="coBoarding - Speed Hiring Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

class coBoarding:
    def __init__(self):
        self.cv_processor = CVProcessor()
        self.form_detector = FormDetector()
        self.background_task_engine = BackgroundTaskAutomationEngine()
        self.form_filling_engine = FormFillingAutomationEngine()
        self.chat = ChatInterface()
        self.notifications = NotificationService()
        self.gdpr = GDPRManager()
        
        # Initialize session state
        if 'session_id' not in st.session_state:
            st.session_state.session_id = self._generate_session_id()
        if 'cv_data' not in st.session_state:
            st.session_state.cv_data = None
        if 'selected_companies' not in st.session_state:
            st.session_state.selected_companies = []
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

    def _generate_session_id(self) -> str:
        """Generate unique session ID for GDPR compliance"""
        timestamp = datetime.now().isoformat()
        random_component = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"session_{random_component}"

    def render_header(self):
        """Render application header"""
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🚀 coBoarding")
            st.subheader("Speed Hiring for Tech Companies")
            st.markdown("*Upload CV → Get matched → Start working in 24h*")

    def render_cv_upload(self):
        """Render CV upload interface"""
        st.header("📄 Upload Your CV")
        
        uploaded_file = st.file_uploader(
            "Choose your CV file",
            type=['pdf', 'docx', 'txt'],
            help="Supported formats: PDF, DOCX, TXT (max 10MB)"
        )
        
        if uploaded_file is not None:
            with st.spinner("🔍 Analyzing your CV..."):
                # Process CV with local LLM
                cv_data = asyncio.run(self.cv_processor.process_cv(uploaded_file))
                st.session_state.cv_data = cv_data
                
                # Store with TTL for GDPR compliance
                self.gdpr.store_with_ttl(
                    st.session_state.session_id,
                    cv_data,
                    ttl_hours=24
                )
                
                st.success("✅ CV processed successfully!")
                return cv_data
        return None

    def render_cv_summary(self, cv_data: Dict):
        """Render CV summary and allow edits"""
        st.header("📋 CV Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Personal Information")
            name = st.text_input("Name", value=cv_data.get('name', ''))
            email = st.text_input("Email", value=cv_data.get('email', ''))
            phone = st.text_input("Phone", value=cv_data.get('phone', ''))
            location = st.text_input("Location", value=cv_data.get('location', ''))
            
        with col2:
            st.subheader("Professional Profile")
            title = st.text_input("Current Title", value=cv_data.get('title', ''))
            experience_years = st.number_input(
                "Years of Experience", 
                value=cv_data.get('experience_years', 0),
                min_value=0,
                max_value=50
            )
            
        st.subheader("Skills & Technologies")
        skills = st.text_area(
            "Technical Skills (comma-separated)",
            value=', '.join(cv_data.get('skills', [])),
            height=100
        )
        
        # Update CV data with user edits
        updated_cv_data = {
            **cv_data,
            'name': name,
            'email': email,
            'phone': phone,
            'location': location,
            'title': title,
            'experience_years': experience_years,
            'skills': [skill.strip() for skill in skills.split(',') if skill.strip()]
        }
        
        if st.button("💾 Save Changes"):
            st.session_state.cv_data = updated_cv_data
            self.gdpr.update_with_ttl(st.session_state.session_id, updated_cv_data)
            st.success("Changes saved!")
            
        return updated_cv_data

    def render_company_matching(self, cv_data: Dict):
        """Render company matching interface"""
        st.header("🎯 Matching Companies")
        
        # Load job listings (would be from JSON file in production)
        job_listings = self._load_job_listings()
        
        # AI-powered matching
        with st.spinner("🤖 Finding perfect matches..."):
            matches = asyncio.run(self._match_companies(cv_data, job_listings))
        
        st.subheader(f"Found {len(matches)} potential matches")
        
        selected_companies = []
        for i, match in enumerate(matches[:10]):  # Show top 10
            with st.expander(f"{match['company']} - {match['position']} (Match: {match['score']:.0%})"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Company:** {match['company']}")
                    st.write(f"**Position:** {match['position']}")
                    st.write(f"**Location:** {match['location']}")
                    st.write(f"**Remote:** {'Yes' if match['remote'] else 'No'}")
                
                with col2:
                    st.write(f"**Requirements:**")
                    for req in match['requirements'][:3]:
                        st.write(f"• {req}")
                    st.write(f"**Salary:** {match.get('salary', 'Not specified')}")
                
                with col3:
                    if st.button(f"Apply Now", key=f"apply_{i}"):
                        selected_companies.append(match)
                        st.success("Added to applications!")
        
        if selected_companies:
            st.session_state.selected_companies = selected_companies
            return selected_companies
        
        return []

    def render_chat_interface(self, cv_data: Dict, selected_companies: List[Dict]):
        """Render chat interface for communication"""
        st.header("💬 Chat & Communication")
        
        # Initialize chat for each selected company
        for company in selected_companies:
            with st.expander(f"Chat with {company['company']} - {company['position']}", expanded=True):
                chat_key = f"chat_{company['id']}"
                
                # Display chat history
                if chat_key in st.session_state:
                    for message in st.session_state[chat_key]:
                        with st.chat_message(message["role"]):
                            st.write(message["content"])
                
                # Chat input
                if prompt := st.chat_input(f"Message {company['company']}...", key=f"input_{company['id']}"):
                    # Initialize chat history if needed
                    if chat_key not in st.session_state:
                        st.session_state[chat_key] = []
                    
                    # Add user message
                    st.session_state[chat_key].append({"role": "user", "content": prompt})
                    
                    # Process with AI and send notifications
                    with st.spinner("Sending message..."):
                        response = asyncio.run(self.chat.process_message(
                            prompt, cv_data, company
                        ))
                        
                        # Add AI response
                        st.session_state[chat_key].append({"role": "assistant", "content": response})
                        
                        # Send notification to employer
                        asyncio.run(self.notifications.notify_employer(
                            company, cv_data, prompt
                        ))
                    
                    st.rerun()

    def render_automation_panel(self):
        """Render form automation panel"""
        st.sidebar.header("🤖 Automated Application Submission")
        
        # URL input for form detection
        target_url = st.sidebar.text_input("Target URL for form detection", "https://example.com")
        
        if st.sidebar.button("🔍 Detect Forms"):
            with st.spinner("Detecting forms on current page..."):
                try:
                    # Use a thread-safe way to run async code
                    import nest_asyncio
                    import asyncio
                    
                    # Apply nest_asyncio to allow nested event loops
                    try:
                        nest_asyncio.apply()
                    except RuntimeError:
                        # Already applied
                        pass
                        
                    # Get or create an event loop
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Initialize the browser first if needed
                    loop.run_until_complete(self.form_detector.__class__.initialize_browser())
                    
                    # Run the detect_forms function
                    forms = loop.run_until_complete(self.form_detector.detect_forms(url=target_url))
                    
                    if forms:
                        st.sidebar.success(f"Found {len(forms)} forms")
                    else:
                        st.sidebar.warning("No forms detected on the page")
                except Exception as e:
                    st.sidebar.error(f"Error detecting forms: {str(e)}")
                    import traceback
                    st.sidebar.text(traceback.format_exc())
                
        if st.sidebar.button("Start Automation", key="start_automation_button"):
            if not st.session_state.selected_companies:
                st.warning("Please select at least one company to apply to.")
                return

            if not st.session_state.cv_data:
                st.error("CV data not found. Please upload and process your CV first.")
                return

            results = asyncio.run(self.form_filling_engine.fill_forms(
                cv_data=st.session_state.cv_data,
                target_urls=[company['application_url'] for company in st.session_state.selected_companies]
            ))
            st.sidebar.success("Forms filled successfully!")

    def render_notifications_panel(self):
        """Render notifications panel"""
        st.sidebar.header("🔔 Notifications")
        
        # Get notifications asynchronously
        notifications = asyncio.run(self.notifications.get_recent_notifications(
            st.session_state.session_id
        ))
        
        # Now notifications is a list, not a coroutine
        for notif in notifications[-5:]:  # Show last 5
            st.sidebar.info(f"**{notif['type']}:** {notif['message']}")

    def _load_job_listings(self) -> List[Dict]:
        """Load job listings from JSON file"""
        # In production, this would load from a JSON file
        return [
            {
                "id": "1",
                "company": "TechStart Berlin",
                "position": "Senior Python Developer",
                "location": "Berlin, Germany",
                "remote": True,
                "requirements": ["Python", "Django", "PostgreSQL", "Docker"],
                "salary": "€60,000 - €80,000",
                "urgent": True
            },
            {
                "id": "2", 
                "company": "AI Solutions Warsaw",
                "position": "ML Engineer",
                "location": "Warsaw, Poland",
                "remote": True,
                "requirements": ["Python", "TensorFlow", "PyTorch", "MLOps"],
                "salary": "€50,000 - €70,000",
                "urgent": True
            },
            {
                "id": "3",
                "company": "FinTech Amsterdam",
                "position": "Full Stack Developer",
                "location": "Amsterdam, Netherlands", 
                "remote": False,
                "requirements": ["React", "Node.js", "TypeScript", "AWS"],
                "salary": "€65,000 - €85,000",
                "urgent": False
            }
        ]

    async def _match_companies(self, cv_data: Dict, job_listings: List[Dict]) -> List[Dict]:
        """AI-powered company matching"""
        matches = []
        
        cv_skills = set(skill.lower() for skill in cv_data.get('skills', []))
        cv_title = cv_data.get('title', '').lower()
        
        for job in job_listings:
            # Simple matching algorithm (would use LLM in production)
            job_skills = set(req.lower() for req in job['requirements'])
            skill_overlap = len(cv_skills.intersection(job_skills))
            title_match = any(word in cv_title for word in job['position'].lower().split())
            
            score = (skill_overlap * 0.7) + (title_match * 0.3)
            if score > 0:
                matches.append({
                    **job,
                    'score': min(score, 1.0)  # Cap at 100%
                })
        
        return sorted(matches, key=lambda x: x['score'], reverse=True)

    def run(self):
        """Main application runner"""
        self.render_header()
        
        # Sidebar
        self.render_automation_panel()
        self.render_notifications_panel()
        
        # Main content
        cv_data = self.render_cv_upload()
        
        if cv_data or st.session_state.cv_data:
            current_cv_data = cv_data or st.session_state.cv_data
            
            # CV Summary and editing
            updated_cv_data = self.render_cv_summary(current_cv_data)
            
            # Company matching
            selected_companies = self.render_company_matching(updated_cv_data)
            
            # Chat interface
            if selected_companies or st.session_state.selected_companies:
                current_companies = selected_companies or st.session_state.selected_companies
                self.render_chat_interface(updated_cv_data, current_companies)

# Main execution
if __name__ == "__main__":
    app = coBoarding()
    app.run()