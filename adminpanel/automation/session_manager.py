# adminpanel/automation/session_manager.py
"""
Session manager for Instagram automation
Handles session loading, validation, and rotation
"""
import json
import os
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class AutomationSessionManager:
    """Manages Instagram sessions for automation purposes"""
    
    def __init__(self, sessions_file: str = "sessions.json"):
        self.sessions_file = sessions_file
        self.sessions: List[Dict[str, Any]] = []
        self.current_session_index = 0
        self.session_activity = {}  # Track daily activity per session
        self.load_sessions()
    
    def load_sessions(self) -> None:
        """Load sessions from JSON file"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    self.sessions = json.load(f)
                logger.info(f"Loaded {len(self.sessions)} sessions")
            else:
                self.sessions = []
                logger.warning(f"Sessions file {self.sessions_file} not found")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = []
    
    def save_sessions(self) -> None:
        """Save sessions back to JSON file"""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, indent=2, ensure_ascii=False)
            logger.info("Sessions saved successfully")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active and valid sessions"""
        active_sessions = []
        for session in self.sessions:
            if (session.get('status') == 'active' and 
                not session.get('blocked', False) and
                session.get('sessionid') and 
                session.get('ds_user_id')):
                active_sessions.append(session)
        return active_sessions
    
    def get_next_session(self) -> Optional[Dict[str, Any]]:
        """Get the next session for automation use"""
        active_sessions = self.get_active_sessions()
        if not active_sessions:
            logger.warning("No active sessions available")
            return None
        
        # Round-robin selection
        session = active_sessions[self.current_session_index % len(active_sessions)]
        self.current_session_index += 1
        
        # Update last used timestamp
        session['last_used'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return session
    
    def update_session_activity(self, session_id: str, activity_type: str) -> None:
        """Track activity for a session"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{session_id}_{today}"
        
        if key not in self.session_activity:
            self.session_activity[key] = {
                'likes': 0,
                'follows': 0,
                'unfollows': 0,
                'comments': 0,
                'stories': 0,
                'profile_visits': 0
            }
        
        if activity_type in self.session_activity[key]:
            self.session_activity[key][activity_type] += 1
    
    def get_session_activity(self, session_id: str) -> Dict[str, int]:
        """Get today's activity for a session"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{session_id}_{today}"
        return self.session_activity.get(key, {
            'likes': 0,
            'follows': 0,
            'unfollows': 0,
            'comments': 0,
            'stories': 0,
            'profile_visits': 0
        })
    
    def can_perform_activity(self, session_id: str, activity_type: str) -> bool:
        """Check if session can perform activity based on daily limits"""
        from .config import (DAILY_LIKES_LIMIT, DAILY_FOLLOWS_LIMIT, 
                            DAILY_UNFOLLOWS_LIMIT, DAILY_COMMENTS_LIMIT, 
                            DAILY_STORIES_LIMIT)
        
        activity = self.get_session_activity(session_id)
        limits = {
            'likes': DAILY_LIKES_LIMIT,
            'follows': DAILY_FOLLOWS_LIMIT,
            'unfollows': DAILY_UNFOLLOWS_LIMIT,
            'comments': DAILY_COMMENTS_LIMIT,
            'stories': DAILY_STORIES_LIMIT,
            'profile_visits': 100  # High limit for profile visits
        }
        
        return activity.get(activity_type, 0) < limits.get(activity_type, 0)
    
    def mark_session_failed(self, session_id: str) -> None:
        """Mark session as failed/problematic"""
        for session in self.sessions:
            if session.get('sessionid') == session_id:
                session['fail_count'] = session.get('fail_count', 0) + 1
                if session['fail_count'] >= 3:
                    session['status'] = 'invalid'
                logger.warning(f"Session {session.get('user', 'unknown')} marked as failed")
                break
        self.save_sessions()
    
    def mark_session_success(self, session_id: str) -> None:
        """Mark session as successful"""
        for session in self.sessions:
            if session.get('sessionid') == session_id:
                session['success_count'] = session.get('success_count', 0) + 1
                session['status'] = 'active'
                session['last_used'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.save_sessions()
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get overall session statistics"""
        total = len(self.sessions)
        active = len([s for s in self.sessions if s.get('status') == 'active'])
        blocked = len([s for s in self.sessions if s.get('blocked', False)])
        invalid = len([s for s in self.sessions if s.get('status') == 'invalid'])
        
        return {
            'total': total,
            'active': active,
            'blocked': blocked,
            'invalid': invalid,
            'pending': total - active - blocked - invalid
        }
    
    def cleanup_old_activity(self, days: int = 7) -> None:
        """Clean up old activity tracking data"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        keys_to_remove = []
        for key in self.session_activity:
            if key.split('_')[-1] < cutoff_str:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.session_activity[key]
        
        logger.info(f"Cleaned up {len(keys_to_remove)} old activity records")