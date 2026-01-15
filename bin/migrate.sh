#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${GREEN}Running database migrations...${NC}"

# Check if database container is running
if ! docker compose ps db 2>/dev/null | grep -q "Up"; then
    echo -e "${YELLOW}Starting database container...${NC}"
    docker compose up -d db
    echo -e "${YELLOW}Waiting for database to be ready...${NC}"
    sleep 5
fi

# Run schema.sql against the database
echo -e "${GREEN}Applying schema.sql...${NC}"
docker compose exec -T db psql -U postgres -d footnote < "$PROJECT_ROOT/database/schema.sql"

echo -e "${GREEN}Migrations complete!${NC}"
