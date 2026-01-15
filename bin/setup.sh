#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Footnote First Time Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker Desktop from https://docker.com"
    exit 1
fi

# Check Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker is installed and running.${NC}"

# Create .env files from examples
echo -e "${GREEN}Setting up environment files...${NC}"

if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
    cp "$PROJECT_ROOT/backend/.env.example" "$PROJECT_ROOT/backend/.env"
    echo -e "  Created ${YELLOW}backend/.env${NC}"
else
    echo -e "  ${YELLOW}backend/.env${NC} already exists, skipping"
fi

if [ ! -f "$PROJECT_ROOT/frontend/.env" ]; then
    cp "$PROJECT_ROOT/frontend/.env.example" "$PROJECT_ROOT/frontend/.env"
    echo -e "  Created ${YELLOW}frontend/.env${NC}"
else
    echo -e "  ${YELLOW}frontend/.env${NC} already exists, skipping"
fi

# Build Docker images
echo ""
echo -e "${GREEN}Building Docker images...${NC}"
docker compose build

# Start database and run migrations
echo ""
echo -e "${GREEN}Starting database...${NC}"
docker compose up -d db

echo -e "${YELLOW}Waiting for database to be healthy...${NC}"
until docker compose exec -T db pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done
echo -e "${GREEN}Database is ready!${NC}"

# Run migrations
echo ""
echo -e "${GREEN}Running database migrations...${NC}"
"$SCRIPT_DIR/migrate.sh"

# Stop database (dev.sh will start everything)
docker compose down

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Update ${YELLOW}backend/.env${NC} with your API keys:"
echo -e "     - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
echo -e "     - TOGETHER_API_KEY"
echo -e "     - ANTHROPIC_API_KEY"
echo -e "     - MISTRAL_API_KEY (optional)"
echo ""
echo -e "  2. Start the development environment:"
echo -e "     ${GREEN}./bin/dev.sh${NC}"
echo ""
echo -e "  3. Open in browser:"
echo -e "     Frontend: ${BLUE}http://localhost:3000${NC}"
echo -e "     Backend:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "${BLUE}========================================${NC}"
