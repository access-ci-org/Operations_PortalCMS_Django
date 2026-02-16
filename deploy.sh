#!/bin/bash
# Deployment script for Operations Portal CMS
# Run this script on the remote server as the 'software' user

set -e  # Exit on any error

# Configuration
APP_HOME="/soft/django-cms-01"
APP_NAME="portalcms"
APP_DIR="$APP_HOME/PROD/Operations_PortalCMS_Django"
CONF_FILE="$APP_HOME/conf/$APP_NAME.conf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if running as software user
if [ "$USER" != "software" ]; then
    print_error "This script must be run as the 'software' user"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONF_FILE" ]; then
    print_error "Configuration file not found: $CONF_FILE"
    print_info "Please create the configuration file before running this script"
    exit 1
fi

echo "======================================"
echo "Operations Portal CMS Deployment"
echo "======================================"
echo ""

# Step 1: Update code (if git repo)
if [ -d "$APP_DIR/.git" ]; then
    print_info "Updating code from git..."
    cd "$APP_DIR"
    git pull
    print_success "Code updated"
else
    print_info "Not a git repository, skipping git pull"
fi

# Step 2: Install/update dependencies
print_info "Installing dependencies with uv..."
cd "$APP_DIR"
uv sync
print_success "Dependencies installed"

# Step 3: Set environment
export APP_CONFIG="$CONF_FILE"
print_info "Using config: $APP_CONFIG"

# Step 4: Run migrations
print_info "Running database migrations..."
uv run python manage.py migrate --noinput
print_success "Migrations completed"

# Step 5: Collect static files
print_info "Collecting static files..."
uv run python manage.py collectstatic --noinput
print_success "Static files collected"

# Step 6: Restart service
print_info "Restarting service..."
sudo systemctl restart "$APP_NAME"
sleep 2

# Step 7: Check service status
if sudo systemctl is-active --quiet "$APP_NAME"; then
    print_success "Service is running"
else
    print_error "Service failed to start"
    print_info "Checking logs..."
    sudo journalctl -u "$APP_NAME" -n 20 --no-pager
    exit 1
fi

echo ""
echo "======================================"
print_success "Deployment completed successfully!"
echo "======================================"
echo ""
print_info "To view logs:"
echo "  sudo journalctl -u $APP_NAME -f"
echo ""
print_info "To check status:"
echo "  sudo systemctl status $APP_NAME"
echo ""
