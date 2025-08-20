# adminpanel/automation_views.py
"""
Admin views for Instagram automation system
"""
import os
import logging
from datetime import datetime
from flask import render_template, request, jsonify, redirect, url_for
from adminpanel import admin_bp
from adminpanel.views import login_required

from .automation.session_manager import AutomationSessionManager
from .automation.activity_scheduler import ActivityScheduler
from .automation.config import (AUTOMATION_ENABLED, DAILY_LIKES_LIMIT, 
                               DAILY_FOLLOWS_LIMIT, DAILY_COMMENTS_LIMIT)

logger = logging.getLogger(__name__)

# Initialize automation components
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")

session_manager = AutomationSessionManager(SESSIONS_FILE)
scheduler = ActivityScheduler(session_manager)

# Start scheduler if automation is enabled
if AUTOMATION_ENABLED:
    scheduler.start()

@admin_bp.route('/automation')
@login_required
def automation_dashboard():
    """Main automation dashboard"""
    try:
        # Get session statistics
        session_stats = session_manager.get_session_stats()
        
        # Get scheduler status
        scheduler_status = scheduler.get_scheduler_status()
        
        # Get recent activity summary
        activity_summary = scheduler.get_activity_summary(days=7)
        
        # Get active sessions
        active_sessions = session_manager.get_active_sessions()
        
        return render_template('admin/automation_dashboard.html',
                             session_stats=session_stats,
                             scheduler_status=scheduler_status,
                             activity_summary=activity_summary,
                             active_sessions=active_sessions[:10],  # Show first 10
                             limits={
                                 'likes': DAILY_LIKES_LIMIT,
                                 'follows': DAILY_FOLLOWS_LIMIT,
                                 'comments': DAILY_COMMENTS_LIMIT
                             })
    except Exception as e:
        logger.error(f"Error loading automation dashboard: {e}")
        return render_template('admin/automation_dashboard.html',
                             error=f"Dashboard error: {str(e)}")

@admin_bp.route('/automation/sessions')
@login_required
def automation_sessions():
    """Session management page"""
    try:
        # Reload sessions
        session_manager.load_sessions()
        
        all_sessions = session_manager.sessions
        active_sessions = session_manager.get_active_sessions()
        
        # Get activity data for each session
        session_activities = {}
        for session in all_sessions:
            session_id = session.get('sessionid')
            if session_id:
                activity = session_manager.get_session_activity(session_id)
                session_activities[session_id] = activity
        
        return render_template('admin/session_manager.html',
                             all_sessions=all_sessions,
                             active_sessions=active_sessions,
                             session_activities=session_activities)
    except Exception as e:
        logger.error(f"Error loading session manager: {e}")
        return render_template('admin/session_manager.html',
                             error=f"Session manager error: {str(e)}")

@admin_bp.route('/automation/logs')
@login_required
def automation_logs():
    """Activity logs page"""
    try:
        # Get activity logs
        logs = scheduler.get_activity_logs(limit=200)
        
        # Reverse to show newest first
        logs.reverse()
        
        return render_template('admin/activity_logs.html',
                             logs=logs)
    except Exception as e:
        logger.error(f"Error loading activity logs: {e}")
        return render_template('admin/activity_logs.html',
                             error=f"Logs error: {str(e)}")

@admin_bp.route('/automation/api/status')
@login_required
def api_automation_status():
    """API endpoint for automation status"""
    try:
        status = scheduler.get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/toggle', methods=['POST'])
@login_required
def api_toggle_automation():
    """API endpoint to toggle automation on/off"""
    try:
        enabled = request.json.get('enabled', False)
        scheduler.toggle_automation(enabled)
        
        return jsonify({
            "success": True,
            "enabled": enabled,
            "message": f"Automation {'enabled' if enabled else 'disabled'}"
        })
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/run-activity', methods=['POST'])
@login_required
def api_run_manual_activity():
    """API endpoint to run manual activity"""
    try:
        session_user = request.json.get('session_user')
        
        result = scheduler.run_manual_activity(session_user)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running manual activity: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/session-activity/<session_id>')
@login_required
def api_session_activity(session_id):
    """API endpoint to get session activity"""
    try:
        activity = session_manager.get_session_activity(session_id)
        can_activities = {}
        
        # Check what activities this session can perform
        activities = ['likes', 'follows', 'unfollows', 'comments', 'stories']
        for activity_type in activities:
            can_activities[activity_type] = session_manager.can_perform_activity(
                session_id, activity_type
            )
        
        return jsonify({
            "activity": activity,
            "can_perform": can_activities
        })
    except Exception as e:
        logger.error(f"Error getting session activity: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/refresh-sessions', methods=['POST'])
@login_required
def api_refresh_sessions():
    """API endpoint to refresh session data"""
    try:
        session_manager.load_sessions()
        stats = session_manager.get_session_stats()
        
        return jsonify({
            "success": True,
            "message": "Sessions refreshed successfully",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error refreshing sessions: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/logs')
@login_required
def api_activity_logs():
    """API endpoint for activity logs"""
    try:
        limit = int(request.args.get('limit', 50))
        logs = scheduler.get_activity_logs(limit=limit)
        
        # Reverse to show newest first
        logs.reverse()
        
        return jsonify(logs)
    except Exception as e:
        logger.error(f"Error getting activity logs: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/automation/api/summary')
@login_required
def api_activity_summary():
    """API endpoint for activity summary"""
    try:
        days = int(request.args.get('days', 7))
        summary = scheduler.get_activity_summary(days=days)
        
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error getting activity summary: {e}")
        return jsonify({"error": str(e)}), 500

# Cleanup on app shutdown
import atexit

def cleanup_automation():
    """Clean up automation resources"""
    try:
        scheduler.stop()
        logger.info("Automation cleanup completed")
    except Exception as e:
        logger.error(f"Error during automation cleanup: {e}")

atexit.register(cleanup_automation)