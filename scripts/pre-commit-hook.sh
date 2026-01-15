#!/bin/bash
#
# Git Pre-Commit Hook
# Prevents committing sensitive files (credentials, keys, etc.)
#
# Installation:
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# This will automatically run before every git commit

set -e

# Color output
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Files that should NEVER be committed
PROTECTED_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    ".env.staging"
    "backend/.env"
    "backend/.env.local"
    "frontend/.env"
    "frontend/.env.local"
    "*.key"
    "*.pem"
    "credentials.json"
    "secrets.json"
)

# Patterns that indicate credentials
CREDENTIAL_PATTERNS=(
    "ANTHROPIC_API_KEY=sk-"
    "GOOGLE_CLIENT_SECRET=GOCSPX-"
    "FIREWORKS_API_KEY=fw_"
    "MISTRAL_API_KEY="
    "DATABASE_URL=postgresql"
    "AWS_SECRET_ACCESS_KEY="
    "PRIVATE_KEY=-----BEGIN"
)

echo "Running pre-commit checks..."
echo ""

# Check staged files against protected list
STAGED_FILES=$(git diff --cached --name-only)

echo "Checking for protected files..."
for protected_file in "${PROTECTED_FILES[@]}"; do
    # Handle glob patterns
    for staged_file in $STAGED_FILES; do
        # Simple glob matching (not perfect, but good enough)
        if [ "$staged_file" = "$protected_file" ] || [[ "$staged_file" == "$protected_file" ]]; then
            echo -e "${RED}ERROR: Attempting to commit protected file: $staged_file${NC}"
            echo "  This file contains credentials and should not be in git."
            echo "  Use .env.example instead, or add to .gitignore"
            ((ERRORS++))
        fi
    done
done

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}Pre-commit check FAILED${NC}"
    echo "To proceed, remove the protected files from staging:"
    echo "  git reset HEAD <file>"
    exit 1
fi

# Check staged content for credential patterns
echo "Checking staged content for credentials..."
STAGED_CONTENT=$(git diff --cached)

for pattern in "${CREDENTIAL_PATTERNS[@]}"; do
    if echo "$STAGED_CONTENT" | grep -q "$pattern"; then
        echo -e "${RED}ERROR: Potential credentials detected in staged changes${NC}"
        echo "  Pattern: $pattern"
        echo ""
        echo "Review your changes with: git diff --cached"
        echo "Remove sensitive content and re-stage: git reset HEAD <file>"
        ((ERRORS++))
    fi
done

if [ $ERRORS -gt 0 ]; then
    exit 1
fi

# Check .env files are in .gitignore
echo "Checking .gitignore..."
if [ -f ".gitignore" ]; then
    if ! grep -q "^\.env" .gitignore; then
        echo -e "${YELLOW}WARNING: .env patterns not in .gitignore${NC}"
        echo "  Add these lines to .gitignore:"
        echo "    .env"
        echo "    .env.local"
        echo "    .env.*.local"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}WARNING: No .gitignore found${NC}"
    ((WARNINGS++))
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}Pre-commit check passed with warnings${NC}"
    else
        echo "✓ Pre-commit check passed"
    fi
    exit 0
else
    echo -e "${RED}Pre-commit check FAILED${NC}"
    exit 1
fi
