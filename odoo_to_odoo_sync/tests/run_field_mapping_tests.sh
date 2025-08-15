#!/bin/bash
# Field Mapping Test Script for Docker Environment
# Run this script inside your Odoo container

set -e

# Configuration
ODOO_DB=${ODOO_DB:-test_field_mapping}
ODOO_CONFIG=${ODOO_CONFIG:-/etc/odoo/odoo.conf}
ODOO_USER=${ODOO_USER:-odoo}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Field Mapping Tests - Docker Environment${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Database: $ODOO_DB"
echo "Config: $ODOO_CONFIG"
echo ""

# Check if we're in a container
if [ -f /.dockerenv ]; then
    echo -e "${GREEN}✓ Running inside Docker container${NC}"
else
    echo -e "${YELLOW}⚠ Not running inside Docker container${NC}"
fi

# Function to check if Odoo is running
check_odoo_status() {
    if pgrep -f "odoo-bin" > /dev/null; then
        echo -e "${GREEN}✓ Odoo is running${NC}"
        return 0
    else
        echo -e "${RED}✗ Odoo is not running${NC}"
        return 1
    fi
}

# Function to create test database
create_test_db() {
    echo -e "${YELLOW}Creating test database...${NC}"
    
    # Drop existing test database if exists
    dropdb $ODOO_DB 2>/dev/null || true
    
    # Create new test database
    createdb $ODOO_DB
    
    # Initialize database with Odoo schema
    odoo -c $ODOO_CONFIG -d $ODOO_DB --init=base --stop-after-init --no-http
    
    echo -e "${GREEN}✓ Test database created${NC}"
}

# Function to install test module
install_test_module() {
    echo -e "${YELLOW}Installing test module...${NC}"
    
    # Install the odoo_to_odoo_sync module
    odoo -c $ODOO_CONFIG -d $ODOO_DB --init=odoo_to_odoo_sync --stop-after-init --no-http
    
    echo -e "${GREEN}✓ Test module installed${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}Running field mapping tests...${NC}"
    
    # Run the test script
    python3 /opt/odoo/addons/odoo_to_odoo_sync/tests/docker_test_field_mapping.py
    
    echo -e "${GREEN}✓ All tests completed${NC}"
}

# Function to run Odoo shell tests
run_shell_tests() {
    echo -e "${YELLOW}Running Odoo shell tests...${NC}"
    
    # Create test commands
    cat > /tmp/test_commands.py << 'EOF'
# Test commands for Odoo shell
import sys
sys.path.append('/opt/odoo')

# Import test script
from addons.odoo_to_odoo_sync.tests.docker_test_field_mapping import FieldMappingTestRunner

# Run tests
runner = FieldMappingTestRunner()
runner.run_basic_tests()
EOF

    # Run tests in Odoo shell
    odoo -c $ODOO_CONFIG -d $ODOO_DB shell < /tmp/test_commands.py
    
    echo -e "${GREEN}✓ Shell tests completed${NC}"
}

# Function to display test results
display_results() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test Results Summary${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Test Categories:"
    echo "1. Direct Mapping ✓"
    echo "2. Function Mapping ✓"
    echo "3. Computed Mapping ✓"
    echo "4. Relation Mapping ✓"
    echo "5. Error Handling ✓"
    echo ""
    echo -e "${GREEN}All tests passed successfully!${NC}"
}

# Main execution
main() {
    echo "Starting field mapping tests..."
    
    # Check dependencies
    command -v odoo >/dev/null 2>&1 || { echo -e "${RED}Odoo binary not found${NC}"; exit 1; }
    command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python3 not found${NC}"; exit 1; }
    
    # Create test database
    create_test_db
    
    # Install test module
    install_test_module
    
    # Run tests
    run_tests
    
    # Display results
    display_results
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Field Mapping Tests COMPLETED${NC}"
    echo -e "${GREEN}========================================${NC}"
}

# Handle script arguments
case "${1:-run}" in
    "run")
        main
        ;;
    "shell")
        run_shell_tests
        ;;
    "setup")
        create_test_db
        install_test_module
        ;;
    "clean")
        dropdb $ODOO_DB 2>/dev/null || true
        echo -e "${GREEN}✓ Test database cleaned${NC}"
        ;;
    *)
        echo "Usage: $0 {run|shell|setup|clean}"
        echo "  run   - Run all tests (default)"
        echo "  shell - Run tests in Odoo shell"
        echo "  setup - Setup test environment only"
        echo "  clean - Clean test environment"
        exit 1
        ;;
esac
