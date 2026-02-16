#!/bin/bash
# rsync deployment helper script
# Usage: ./rsync-deploy.sh [server]

# Configuration
LOCAL_DIR="."
REMOTE_USER="software"
REMOTE_HOST="${1:-your-server.access-ci.org}"  # Pass server as argument or edit default
REMOTE_DIR="/soft/django-cms-01/PROD/Operations_PortalCMS_Django"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Deploying to: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}${NC}"
echo ""

# Dry run first
echo -e "${YELLOW}Running dry-run to show what will be transferred...${NC}"
rsync -avzn \
  --exclude='.git/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='.env' \
  --exclude='media/' \
  --exclude='staticfiles/' \
  --exclude='.DS_Store' \
  --exclude='*.log' \
  --exclude='*.pid' \
  --exclude='*.sock' \
  --exclude='var/' \
  --exclude='uv_tree.txt' \
  --delete \
  "$LOCAL_DIR/" \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

echo ""
read -p "Proceed with actual deployment? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
  echo -e "${GREEN}Deploying...${NC}"
  rsync -avz \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='.env' \
    --exclude='media/' \
    --exclude='staticfiles/' \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    --exclude='*.pid' \
    --exclude='*.sock' \
    --exclude='var/' \
    --exclude='uv_tree.txt' \
    --delete \
    "$LOCAL_DIR/" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
  
  echo ""
  echo -e "${GREEN}✓ Deployment complete!${NC}"
  echo ""
  echo "Next steps:"
  echo "  ssh ${REMOTE_USER}@${REMOTE_HOST}"
  echo "  cd ${REMOTE_DIR}"
  echo "  ./deploy.sh"
else
  echo "Deployment cancelled."
fi
