#!/usr/bin/env python3
"""
Simple Dependency Management Test Runner
This script runs basic validation tests through Odoo shell
"""

import subprocess
import sys
import time

def run_odoo_shell_command(command):
    """Run a command in Odoo shell"""
    full_command = f'''
docker compose exec -T odoo1 odoo shell -d odoo1 -c /etc/odoo/odoo.conf --no-http --shell-interface python << 'EOF'
{command}
EOF
'''
    
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True, cwd="/home/mathis/CascadeProjects/bemade-projects/pneumac/traefik-test")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_dependency_models():
    """Test if dependency models exist"""
    test_code = '''
import psycopg2
from odoo import api, SUPERUSER_ID

# Test database connection
try:
    conn = psycopg2.connect(
        host='db1',
        database='odoo1',
        user='odoo',
        password='odoo'
    )
    cursor = conn.cursor()
    
    # Check if models exist
    cursor.execute("SELECT model FROM ir_model WHERE model LIKE 'odoo.sync%'")
    models = [row[0] for row in cursor.fetchall()]
    
    expected_models = [
        'odoo.sync.model',
        'odoo.sync.dependency', 
        'odoo.sync.dependency.resolver'
    ]
    
    found_models = [m for m in expected_models if m in models]
    missing_models = [m for m in expected_models if m not in models]
    
    print(f"Found models: {found_models}")
    print(f"Missing models: {missing_models}")
    
    if len(missing_models) == 0:
        print("✅ All dependency models available")
        conn.close()
        exit(0)
    else:
        print(f"❌ Missing {len(missing_models)} models")
        conn.close()
        exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
'''
    return run_odoo_shell_command(test_code)

def test_dependency_functionality():
    """Test basic dependency functionality"""
    test_code = '''
import psycopg2
from odoo import api, SUPERUSER_ID

conn = psycopg2.connect(
    host='db1',
    database='odoo1',
    user='odoo',
    password='odoo'
)
cursor = conn.cursor()

# Create test data
try:
    # Create test models
    cursor.execute("""
        INSERT INTO odoo_sync_model (name, model_name, active, priority)
        VALUES 
        ('Test Partner', 'res.partner', true, 10),
        ('Test User', 'res.users', true, 20)
        RETURNING id
    """)
    model_ids = [row[0] for row in cursor.fetchall()]
    conn.commit()
    
    # Create dependency
    cursor.execute("""
        INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type, field_name)
        SELECT 
            (SELECT id FROM odoo_sync_model WHERE model_name = 'res.users'),
            (SELECT id FROM odoo_sync_model WHERE model_name = 'res.partner'),
            'many2one',
            'partner_id'
    """)
    conn.commit()
    
    # Verify
    cursor.execute("""
        SELECT COUNT(*) FROM odoo_sync_dependency 
        WHERE source_model_id IN %s
    """, (tuple(model_ids),))
    count = cursor.fetchone()[0]
    
    if count > 0:
        print("✅ Dependency creation working")
        
        # Cleanup
        cursor.execute("DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s", (tuple(model_ids),))
        cursor.execute("DELETE FROM odoo_sync_model WHERE id IN %s", (tuple(model_ids),))
        conn.commit()
        conn.close()
        exit(0)
    else:
        print("❌ Dependency creation failed")
        conn.close()
        exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    conn.close()
    exit(1)
'''
    return run_odoo_shell_command(test_code)

def main():
    print("=== Dependency Management Test Suite ===")
    
    tests = [
        ("Model Availability", test_dependency_models),
        ("Dependency Functionality", test_dependency_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        success, stdout, stderr = test_func()
        
        if success:
            print(f"✅ {test_name} PASSED")
            results.append(True)
        else:
            print(f"❌ {test_name} FAILED")
            if stdout:
                print(f"Stdout: {stdout}")
            if stderr:
                print(f"Stderr: {stderr}")
            results.append(False)
    
    print(f"\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All dependency management tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
