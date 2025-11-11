#!/bin/bash
# Run tests for mrp_mts_else_mto module

# Usage:
#   ./run_tests.sh [database_name]
#
# If no database name is provided, uses 'test_mrp_mts_else_mto'

DB_NAME="${1:-test_mrp_mts_else_mto}"
MODULE="mrp_mts_else_mto"

echo "Running tests for module: $MODULE"
echo "Database: $DB_NAME"
echo ""

# Navigate to Odoo root
cd "$(dirname "$0")/../../../.."

# Run tests
./odoo-bin \
    -d "$DB_NAME" \
    -i "$MODULE" \
    --test-enable \
    --test-tags="$MODULE" \
    --stop-after-init \
    --log-level=test

echo ""
echo "Tests complete!"
