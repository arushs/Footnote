#!/bin/bash
#
# Credential Validation Script
# Validates that credentials are properly configured for the target environment
#
# Usage:
#   ./scripts/validate-credentials.sh [local|docker|production]
#
# Examples:
#   ./scripts/validate-credentials.sh local      # For local development
#   ./scripts/validate-credentials.sh docker     # Before docker-compose up
#   ./scripts/validate-credentials.sh production # For production deployment

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT="${1:-local}"
ERRORS=0
WARNINGS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Credential Validation Tool${NC}"
echo -e "${BLUE}Environment: ${BLUE}${ENVIRONMENT}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ ERROR: .env file not found${NC}"
    echo "  Please create .env from .env.example:"
    echo "  cp .env.example .env"
    exit 1
fi

# Function to extract value from .env
get_env_value() {
    local key=$1
    grep "^${key}=" .env 2>/dev/null | cut -d'=' -f2- || echo ""
}

# Function to check if variable is set and non-empty
check_required_var() {
    local key=$1
    local value=$(get_env_value "$key")

    if [ -z "$value" ] || [ "$value" = "your-${key,,}-here" ]; then
        echo -e "${RED}✗ MISSING: $key${NC}"
        ((ERRORS++))
        return 1
    else
        echo -e "${GREEN}✓ SET: $key${NC}"
        return 0
    fi
}

# Function to check variable value format
check_var_format() {
    local key=$1
    local value=$(get_env_value "$key")
    local pattern=$2

    if [ -z "$value" ]; then
        return 0  # Already caught by required check
    fi

    if [[ $value =~ $pattern ]]; then
        echo -e "${GREEN}✓ VALID FORMAT: $key${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ WARNING: $key has unexpected format${NC}"
        echo "  Expected pattern: $pattern"
        echo "  Got: $value"
        ((WARNINGS++))
        return 0
    fi
}

# Check database URL validity for environment
check_database_url() {
    local db_url=$(get_env_value "DATABASE_URL")

    if [ -z "$db_url" ]; then
        echo -e "${RED}✗ DATABASE_URL not set${NC}"
        ((ERRORS++))
        return 1
    fi

    # Extract hostname
    local hostname=$(echo "$db_url" | sed -E 's|.*://[^@]*@([^:]+).*|\1|')
    local port=$(echo "$db_url" | sed -E 's|.*:([0-9]+).*|\1|' || echo "5432")

    case "$ENVIRONMENT" in
        local)
            if [[ "$hostname" == "localhost" ]] || [[ "$hostname" == "127.0.0.1" ]]; then
                echo -e "${GREEN}✓ LOCAL: Using localhost for database${NC}"
                return 0
            else
                echo -e "${YELLOW}⚠ WARNING: Using '$hostname' instead of 'localhost' for local development${NC}"
                echo "  DATABASE_URL=$db_url"
                ((WARNINGS++))
                return 0
            fi
            ;;
        docker)
            if [[ "$hostname" == "db" ]]; then
                echo -e "${GREEN}✓ DOCKER: Using 'db' service name for database${NC}"
                return 0
            elif [[ "$hostname" == "localhost" ]] || [[ "$hostname" == "127.0.0.1" ]]; then
                echo -e "${RED}✗ DOCKER: DATABASE_URL uses 'localhost' instead of 'db'${NC}"
                echo "  This will cause connection failures inside containers!"
                echo "  DATABASE_URL should be: postgresql+asyncpg://postgres:postgres@db:5432/talk_to_folder"
                ((ERRORS++))
                return 1
            else
                echo -e "${GREEN}✓ DOCKER: Using custom hostname: $hostname${NC}"
                return 0
            fi
            ;;
        production)
            if [[ "$hostname" == "localhost" ]] || [[ "$hostname" == "127.0.0.1" ]] || [[ "$hostname" == "db" ]]; then
                echo -e "${RED}✗ PRODUCTION: Using development hostname '$hostname'${NC}"
                echo "  Use a proper database endpoint (RDS, managed database, etc.)"
                ((ERRORS++))
                return 1
            else
                echo -e "${GREEN}✓ PRODUCTION: Using external database: $hostname${NC}"
                return 0
            fi
            ;;
    esac
}

# Validate environment-specific requirements
echo "Checking Environment-Specific Configuration..."
echo ""
check_database_url
echo ""

echo "Checking Required Credentials..."
echo ""
check_required_var "GOOGLE_CLIENT_ID"
check_required_var "GOOGLE_CLIENT_SECRET"
check_required_var "ANTHROPIC_API_KEY"
check_required_var "FIREWORKS_API_KEY"
check_required_var "MISTRAL_API_KEY"
check_required_var "SECRET_KEY"
echo ""

echo "Checking Credential Formats..."
echo ""
check_var_format "GOOGLE_CLIENT_ID" ".*\.apps\.googleusercontent\.com$|^your-"
check_var_format "GOOGLE_CLIENT_SECRET" "^GOCSPX-|^your-"
check_var_format "ANTHROPIC_API_KEY" "^sk-ant-|^your-"
check_var_format "FIREWORKS_API_KEY" "^fw_|^your-"
check_var_format "MISTRAL_API_KEY" "^[a-zA-Z0-9_]+$|^your-"
echo ""

# Summary
echo "=========================================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All validations passed!${NC}"
    echo ""
    echo "Your credentials are configured correctly for: ${BLUE}$ENVIRONMENT${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation passed with $WARNINGS warning(s)${NC}"
    echo ""
    echo "You can proceed, but review the warnings above."
    exit 0
else
    echo -e "${RED}✗ Validation FAILED with $ERRORS error(s)${NC}"
    echo ""
    echo "Please fix the errors above before proceeding."
    echo ""
    echo "Common fixes:"
    echo "  1. Copy template: cp .env.example .env"
    echo "  2. Edit .env and fill in real credentials"
    echo "  3. For DOCKER: ensure DATABASE_URL uses 'db' hostname"
    echo "  4. For LOCAL: ensure DATABASE_URL uses 'localhost' hostname"
    echo ""
    echo "Need help? See CREDENTIAL_MANAGEMENT.md"
    exit 1
fi
