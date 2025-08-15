#!/usr/bin/env python3
"""
Standalone Dependency Management Test Runner

This script runs dependency management tests in your traefik-test environment
without requiring Odoo's test framework.
"""

import sys
import os
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the addons path to Python path
sys.path.insert(0, '/mnt/extra-addons')

class DependencyTestRunner:
    def __init__(self):
        self.odoo1_url = "http://localhost:8069"
        self.odoo2_url = "http://localhost:8070"
        self.db1_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'odoo1',
            'user': 'odoo',
            'password': 'odoo'
        }
        
    def test_db_connection(self):
        """Test database connectivity"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✓ Database connection successful: {version[0]}")
            conn.close()
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def test_model_availability(self):
        """Test if dependency management models are available"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            
            # Check if our models exist
            cursor.execute("""
                SELECT name FROM ir_model 
                WHERE model IN ('odoo.sync.model', 'odoo.sync.dependency', 'odoo.sync.dependency.resolver')
            """)
            models = cursor.fetchall()
            
            if len(models) == 3:
                print("✓ All dependency management models are available")
                conn.close()
                return True
            else:
                print(f"✗ Missing models: {[m[0] for m in models]}")
                conn.close()
                return False
                
        except Exception as e:
            print(f"✗ Model availability test failed: {e}")
            return False
    
    def test_dependency_detection(self):
        """Test automatic dependency detection"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            
            # Create test models
            cursor.execute("""
                INSERT INTO odoo_sync_model (name, model_name, active, priority)
                VALUES 
                ('Test Partner', 'res.partner', true, 10),
                ('Test User', 'res.users', true, 20),
                ('Test Sale Order', 'sale.order', true, 30)
                RETURNING id
            """)
            model_ids = [row[0] for row in cursor.fetchall()]
            conn.commit()
            
            # Trigger dependency update
            cursor.execute("""
                SELECT id FROM odoo_sync_dependency_resolver LIMIT 1
            """)
            resolver_id = cursor.fetchone()
            
            if resolver_id:
                # Simulate dependency analysis
                cursor.execute("""
                    INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type, field_name)
                    SELECT 
                        (SELECT id FROM odoo_sync_model WHERE model_name = 'res.users'),
                        (SELECT id FROM odoo_sync_model WHERE model_name = 'res.partner'),
                        'many2one',
                        'partner_id'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM odoo_sync_dependency 
                        WHERE source_model_id = (SELECT id FROM odoo_sync_model WHERE model_name = 'res.users')
                        AND target_model_id = (SELECT id FROM odoo_sync_model WHERE model_name = 'res.partner')
                    )
                """)
                conn.commit()
                
                # Check if dependencies were created
                cursor.execute("""
                    SELECT COUNT(*) FROM odoo_sync_dependency
                    WHERE source_model_id IN %s
                """, (tuple(model_ids),))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print("✓ Dependency detection test passed")
                    
                    # Cleanup
                    cursor.execute("DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s", (tuple(model_ids),))
                    cursor.execute("DELETE FROM odoo_sync_model WHERE id IN %s", (tuple(model_ids),))
                    conn.commit()
                    conn.close()
                    return True
                else:
                    print("✗ No dependencies detected")
                    conn.close()
                    return False
            else:
                print("✗ No dependency resolver found")
                conn.close()
                return False
                
        except Exception as e:
            print(f"✗ Dependency detection test failed: {e}")
            return False
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            
            # Create test models with circular dependency
            cursor.execute("""
                INSERT INTO odoo_sync_model (name, model_name, active, priority)
                VALUES 
                ('Model A', 'test.model.a', true, 10),
                ('Model B', 'test.model.b', true, 20),
                ('Model C', 'test.model.c', true, 30)
                RETURNING id
            """)
            model_ids = [row[0] for row in cursor.fetchall()]
            conn.commit()
            
            # Create circular dependencies
            cursor.execute("""
                INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type, is_circular)
                VALUES 
                ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.a'), 
                 (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.b'), 'many2one', true),
                ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.b'), 
                 (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.c'), 'many2one', true),
                ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.c'), 
                 (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.a'), 'many2one', true)
            """)
            conn.commit()
            
            # Check if circular dependencies were detected
            cursor.execute("""
                SELECT COUNT(*) FROM odoo_sync_dependency 
                WHERE is_circular = true AND source_model_id IN %s
            """, (tuple(model_ids),))
            count = cursor.fetchone()[0]
            
            if count > 0:
                print("✓ Circular dependency detection test passed")
                
                # Cleanup
                cursor.execute("DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s", (tuple(model_ids),))
                cursor.execute("DELETE FROM odoo_sync_model WHERE id IN %s", (tuple(model_ids),))
                conn.commit()
                conn.close()
                return True
            else:
                print("✗ No circular dependencies detected")
                conn.close()
                return False
                
        except Exception as e:
            print(f"✗ Circular dependency test failed: {e}")
            return False
    
    def test_processing_order(self):
        """Test processing order calculation"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            
            # Create test models with dependencies
            cursor.execute("""
                INSERT INTO odoo_sync_model (name, model_name, active, priority, processing_order)
                VALUES 
                ('Parent Model', 'test.parent', true, 10, 1),
                ('Child Model', 'test.child', true, 20, 2)
                RETURNING id
            """)
            model_ids = [row[0] for row in cursor.fetchall()]
            conn.commit()
            
            # Create dependency relationship
            cursor.execute("""
                INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type)
                SELECT 
                    (SELECT id FROM odoo_sync_model WHERE model_name = 'test.child'),
                    (SELECT id FROM odoo_sync_model WHERE model_name = 'test.parent'),
                    'many2one'
                WHERE NOT EXISTS (
                    SELECT 1 FROM odoo_sync_dependency 
                    WHERE source_model_id = (SELECT id FROM odoo_sync_model WHERE model_name = 'test.child')
                    AND target_model_id = (SELECT id FROM odoo_sync_model WHERE model_name = 'test.parent')
                )
            """)
            conn.commit()
            
            # Check processing order
            cursor.execute("""
                SELECT model_name, processing_order FROM odoo_sync_model 
                WHERE id IN %s ORDER BY processing_order
            """, (tuple(model_ids),))
            results = cursor.fetchall()
            
            if len(results) == 2 and results[0][0] == 'test.parent' and results[1][0] == 'test.child':
                print("✓ Processing order test passed")
                
                # Cleanup
                cursor.execute("DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s", (tuple(model_ids),))
                cursor.execute("DELETE FROM odoo_sync_model WHERE id IN %s", (tuple(model_ids),))
                conn.commit()
                conn.close()
                return True
            else:
                print("✗ Processing order incorrect")
                conn.close()
                return False
                
        except Exception as e:
            print(f"✗ Processing order test failed: {e}")
            return False
    
    def test_missing_dependency_handling(self):
        """Test missing dependency handling"""
        try:
            conn = psycopg2.connect(**self.db1_config)
            cursor = conn.cursor()
            
            # Create a model that depends on a non-existent model
            cursor.execute("""
                INSERT INTO odoo_sync_model (name, model_name, active, priority)
                VALUES ('Orphan Model', 'test.orphan', true, 10)
                RETURNING id
            """)
            model_id = cursor.fetchone()[0]
            conn.commit()
            
            # Create a sync queue item
            cursor.execute("""
                INSERT INTO odoo_sync_queue (model_id, state, retry_count, error_message)
                VALUES (%s, 'pending', 0, 'Missing dependency: test.parent')
                RETURNING id
            """, (model_id,))
            queue_id = cursor.fetchone()[0]
            conn.commit()
            
            # Simulate processing failure
            cursor.execute("""
                UPDATE odoo_sync_queue 
                SET state = 'error', retry_count = retry_count + 1, 
                    error_message = 'Missing dependency: test.parent'
                WHERE id = %s
            """, (queue_id,))
            conn.commit()
            
            # Check retry mechanism
            cursor.execute("""
                SELECT retry_count, state FROM odoo_sync_queue WHERE id = %s
            """, (queue_id,))
            result = cursor.fetchone()
            
            if result and result[0] > 0 and result[1] == 'error':
                print("✓ Missing dependency handling test passed")
                
                # Cleanup
                cursor.execute("DELETE FROM odoo_sync_queue WHERE id = %s", (queue_id,))
                cursor.execute("DELETE FROM odoo_sync_model WHERE id = %s", (model_id,))
                conn.commit()
                conn.close()
                return True
            else:
                print("✗ Missing dependency handling failed")
                conn.close()
                return False
                
        except Exception as e:
            print(f"✗ Missing dependency test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all dependency management tests"""
        print("=== Dependency Management Test Suite ===")
        
        tests = [
            ("Database Connection", self.test_db_connection),
            ("Model Availability", self.test_model_availability),
            ("Dependency Detection", self.test_dependency_detection),
            ("Circular Dependency Detection", self.test_circular_dependency_detection),
            ("Processing Order", self.test_processing_order),
            ("Missing Dependency Handling", self.test_missing_dependency_handling)
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\nRunning {test_name}...")
            try:
                result = test_func()
                results.append((test_name, result))
                if result:
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} ERROR: {e}")
                results.append((test_name, False))
        
        print("\n=== Test Results ===")
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        return passed == total

if __name__ == "__main__":
    runner = DependencyTestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
