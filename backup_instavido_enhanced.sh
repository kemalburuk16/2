#!/bin/bash
# backup_instavido.sh - Enhanced backup script for InstaVido with automation
# This script backs up the entire InstaVido system including automation data

set -e

BACKUP_DIR="/tmp/instavido_backup_$(date +%Y%m%d_%H%M%S)"
INSTAVIDO_DIR="/home/runner/work/2/2"  # Adjust this path as needed

echo "🔄 Starting InstaVido backup with automation system..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Copy main application files
echo "📁 Backing up main application..."
cp -r "$INSTAVIDO_DIR/app.py" "$BACKUP_DIR/"
cp -r "$INSTAVIDO_DIR/requirements.txt" "$BACKUP_DIR/"
cp -r "$INSTAVIDO_DIR/gunicorn.conf.py" "$BACKUP_DIR/"

# Copy session data
echo "💾 Backing up session data..."
[ -f "$INSTAVIDO_DIR/sessions.json" ] && cp "$INSTAVIDO_DIR/sessions.json" "$BACKUP_DIR/"
[ -f "$INSTAVIDO_DIR/session_index.txt" ] && cp "$INSTAVIDO_DIR/session_index.txt" "$BACKUP_DIR/"
[ -f "$INSTAVIDO_DIR/blocked_cookies.json" ] && cp "$INSTAVIDO_DIR/blocked_cookies.json" "$BACKUP_DIR/"

# Copy admin panel including automation
echo "⚙️ Backing up admin panel with automation..."
cp -r "$INSTAVIDO_DIR/adminpanel" "$BACKUP_DIR/"

# Copy templates and static files
echo "🎨 Backing up templates and static files..."
cp -r "$INSTAVIDO_DIR/templates" "$BACKUP_DIR/"
cp -r "$INSTAVIDO_DIR/static" "$BACKUP_DIR/"

# Copy configuration
echo "🔧 Backing up configuration..."
[ -d "$INSTAVIDO_DIR/config" ] && cp -r "$INSTAVIDO_DIR/config" "$BACKUP_DIR/"

# Copy any other important files
echo "📄 Backing up other files..."
[ -f "$INSTAVIDO_DIR/ads_manager.py" ] && cp "$INSTAVIDO_DIR/ads_manager.py" "$BACKUP_DIR/"
[ -f "$INSTAVIDO_DIR/session_pool.py" ] && cp "$INSTAVIDO_DIR/session_pool.py" "$BACKUP_DIR/"
[ -f "$INSTAVIDO_DIR/session_manager.py" ] && cp "$INSTAVIDO_DIR/session_manager.py" "$BACKUP_DIR/"
[ -f "$INSTAVIDO_DIR/session_logger.py" ] && cp "$INSTAVIDO_DIR/session_logger.py" "$BACKUP_DIR/"

# Create logs directory for automation logs
mkdir -p "$BACKUP_DIR/logs"

# Create a backup info file
echo "📝 Creating backup information..."
cat > "$BACKUP_DIR/BACKUP_INFO.txt" << EOF
InstaVido + Instagram Session Automation Backup
================================================
Backup Date: $(date)
Backup Directory: $BACKUP_DIR
Source Directory: $INSTAVIDO_DIR

Contents:
- Main Flask application (app.py)
- Production configuration (gunicorn.conf.py)
- Dependencies (requirements.txt)
- Session management files (sessions.json, session_index.txt, blocked_cookies.json)
- Complete admin panel including automation system
- Templates and static files
- Configuration files

Automation Features Included:
- Instagram bot with human-like behavior simulation
- Session management and rotation
- Activity scheduling and automation
- Admin panel for automation control
- Activity logging and monitoring

To restore:
1. Extract files to your InstaVido directory
2. Install dependencies: pip install -r requirements.txt
3. Configure environment variables if needed
4. Run with: gunicorn -c gunicorn.conf.py app:app

For automation features:
- Chrome/Chromium browser required for Selenium
- Configure automation settings in adminpanel/automation/config.py
- Access automation dashboard at /admin/automation

EOF

# Create archive
echo "📦 Creating backup archive..."
cd "$(dirname "$BACKUP_DIR")"
tar -czf "${BACKUP_DIR}.tar.gz" "$(basename "$BACKUP_DIR")"

# Cleanup temporary directory
rm -rf "$BACKUP_DIR"

echo "✅ Backup completed successfully!"
echo "📦 Backup file: ${BACKUP_DIR}.tar.gz"
echo "💾 Backup size: $(du -h "${BACKUP_DIR}.tar.gz" | cut -f1)"

# Show backup contents
echo ""
echo "📋 Backup contents:"
tar -tzf "${BACKUP_DIR}.tar.gz" | head -20
if [ $(tar -tzf "${BACKUP_DIR}.tar.gz" | wc -l) -gt 20 ]; then
    echo "... and $(( $(tar -tzf "${BACKUP_DIR}.tar.gz" | wc -l) - 20 )) more files"
fi

echo ""
echo "🚀 To deploy this backup:"
echo "   1. Transfer ${BACKUP_DIR}.tar.gz to your server"
echo "   2. Extract: tar -xzf ${BACKUP_DIR}.tar.gz"
echo "   3. Install dependencies: pip install -r requirements.txt"
echo "   4. Configure environment variables"
echo "   5. Run: gunicorn -c gunicorn.conf.py app:app"
echo ""
echo "🤖 Automation system ready! Access at /admin/automation"