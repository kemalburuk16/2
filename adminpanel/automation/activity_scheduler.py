# adminpanel/automation/activity_scheduler.py
"""
Activity scheduler for Instagram automation
Manages when and how often activities are performed
"""
import threading
import time
import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .session_manager import AutomationSessionManager
from .instagram_bot import InstagramBot
from .config import ACTIVITY_INTERVAL, SESSION_REFRESH_INTERVAL

logger = logging.getLogger(__name__)

class ActivityScheduler:
    """Schedules and manages automation activities"""
    
    def __init__(self, session_manager: AutomationSessionManager):
        self.session_manager = session_manager
        self.is_running = False
        self.scheduler_thread = None
        self.activity_logs = []
        self.last_activity_time = None
        self.enabled = True
        
    def start(self) -> None:
        """Start the activity scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        
        # Schedule activities
        schedule.every(2).hours.do(self._run_session_activities)
        schedule.every(6).hours.do(self._refresh_sessions)
        schedule.every().day.at("03:00").do(self._cleanup_old_data)
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        logger.info("Activity scheduler started")
    
    def stop(self) -> None:
        """Stop the activity scheduler"""
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Activity scheduler stopped")
    
    def _run_scheduler(self) -> None:
        """Main scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _run_session_activities(self) -> None:
        """Run activities for available sessions"""
        if not self.enabled:
            logger.info("Automation is disabled, skipping activities")
            return
        
        logger.info("Starting scheduled session activities")
        
        active_sessions = self.session_manager.get_active_sessions()
        if not active_sessions:
            logger.warning("No active sessions available for activities")
            return
        
        # Limit concurrent activities
        max_sessions = min(3, len(active_sessions))
        selected_sessions = active_sessions[:max_sessions]
        
        activity_results = []
        
        for session in selected_sessions:
            try:
                logger.info(f"Running activity for session: {session.get('user', 'unknown')}")
                
                bot = InstagramBot(self.session_manager)
                result = bot.perform_session_activity(session)
                activity_results.append(result)
                
                # Log activity
                self._log_activity({
                    "timestamp": datetime.now().isoformat(),
                    "session_user": session.get('user'),
                    "result": result,
                    "type": "scheduled_activity"
                })
                
                # Delay between sessions
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error running activity for session {session.get('user')}: {e}")
                self._log_activity({
                    "timestamp": datetime.now().isoformat(),
                    "session_user": session.get('user'),
                    "error": str(e),
                    "type": "scheduled_activity_error"
                })
        
        self.last_activity_time = datetime.now()
        logger.info(f"Completed activities for {len(selected_sessions)} sessions")
    
    def _refresh_sessions(self) -> None:
        """Refresh session data and validate"""
        logger.info("Refreshing session data")
        
        try:
            # Reload sessions from file
            self.session_manager.load_sessions()
            
            # Clean up old activity data
            self.session_manager.cleanup_old_activity()
            
            # Log refresh
            self._log_activity({
                "timestamp": datetime.now().isoformat(),
                "type": "session_refresh",
                "sessions_count": len(self.session_manager.sessions)
            })
            
            logger.info("Session refresh completed")
            
        except Exception as e:
            logger.error(f"Error refreshing sessions: {e}")
    
    def _cleanup_old_data(self) -> None:
        """Clean up old logs and data"""
        logger.info("Cleaning up old data")
        
        try:
            # Keep only last 1000 activity logs
            if len(self.activity_logs) > 1000:
                self.activity_logs = self.activity_logs[-1000:]
            
            # Clean up old session activity data
            self.session_manager.cleanup_old_activity(days=7)
            
            logger.info("Data cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def run_manual_activity(self, session_user: Optional[str] = None) -> Dict[str, Any]:
        """Run manual activity for a specific session or random session"""
        try:
            if session_user:
                # Find specific session
                session = None
                for s in self.session_manager.get_active_sessions():
                    if s.get('user') == session_user:
                        session = s
                        break
                
                if not session:
                    return {"success": False, "error": f"Session {session_user} not found or inactive"}
            else:
                # Get random active session
                session = self.session_manager.get_next_session()
                if not session:
                    return {"success": False, "error": "No active sessions available"}
            
            logger.info(f"Running manual activity for session: {session.get('user')}")
            
            bot = InstagramBot(self.session_manager)
            result = bot.perform_session_activity(session)
            
            # Log activity
            self._log_activity({
                "timestamp": datetime.now().isoformat(),
                "session_user": session.get('user'),
                "result": result,
                "type": "manual_activity"
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error running manual activity: {e}")
            return {"success": False, "error": str(e)}
    
    def get_activity_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent activity logs"""
        return self.activity_logs[-limit:] if self.activity_logs else []
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        active_sessions = self.session_manager.get_active_sessions()
        
        return {
            "is_running": self.is_running,
            "enabled": self.enabled,
            "last_activity": self.last_activity_time.isoformat() if self.last_activity_time else None,
            "next_scheduled": self._get_next_scheduled_time(),
            "active_sessions_count": len(active_sessions),
            "total_logs": len(self.activity_logs),
            "session_stats": self.session_manager.get_session_stats()
        }
    
    def toggle_automation(self, enabled: bool) -> None:
        """Enable or disable automation"""
        self.enabled = enabled
        logger.info(f"Automation {'enabled' if enabled else 'disabled'}")
        
        self._log_activity({
            "timestamp": datetime.now().isoformat(),
            "type": "automation_toggle",
            "enabled": enabled
        })
    
    def _log_activity(self, activity: Dict[str, Any]) -> None:
        """Log an activity"""
        self.activity_logs.append(activity)
        
        # Keep only recent logs in memory
        if len(self.activity_logs) > 500:
            self.activity_logs = self.activity_logs[-400:]
    
    def _get_next_scheduled_time(self) -> Optional[str]:
        """Get next scheduled activity time"""
        try:
            jobs = schedule.jobs
            if jobs:
                next_run = min(job.next_run for job in jobs)
                return next_run.isoformat()
        except:
            pass
        return None
    
    def get_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get activity summary for specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_logs = [
            log for log in self.activity_logs
            if datetime.fromisoformat(log.get('timestamp', '1970-01-01')) > cutoff_date
        ]
        
        summary = {
            "total_activities": 0,
            "successful_activities": 0,
            "failed_activities": 0,
            "sessions_used": set(),
            "activity_types": {},
            "errors": []
        }
        
        for log in recent_logs:
            if log.get('type') in ['scheduled_activity', 'manual_activity']:
                summary["total_activities"] += 1
                
                if log.get('result', {}).get('success'):
                    summary["successful_activities"] += 1
                else:
                    summary["failed_activities"] += 1
                    if log.get('result', {}).get('error'):
                        summary["errors"].append(log['result']['error'])
                
                session_user = log.get('session_user')
                if session_user:
                    summary["sessions_used"].add(session_user)
            
            activity_type = log.get('type', 'unknown')
            summary["activity_types"][activity_type] = summary["activity_types"].get(activity_type, 0) + 1
        
        summary["sessions_used"] = len(summary["sessions_used"])
        
        return summary