#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker-compatible test script for Advanced Field Mapping
Run this inside your Odoo container for testing
"""

import sys
import os

# Add Odoo path to Python path
sys.path.insert(0, '/opt/odoo')

# Import Odoo environment
import odoo
from odoo import api, models, fields
from odoo.tests import common

# Configure database connection
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])

class FieldMappingTestRunner:
    """Test runner for field mapping functionality."""
    
    def __init__(self, db_name='test_field_mapping'):
        self.db_name = db_name
        self.registry = None
        self.env = None
        
    def setup_environment(self):
        """Setup test environment."""
        print("Setting up test environment...")
        
        # Initialize registry
        with odoo.api.Environment.manage():
            registry = odoo.modules.registry.Registry(self.db_name)
            with registry.cursor() as cr:
                self.env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                return True
    
    def run_basic_tests(self):
        """Run basic field mapping tests."""
        print("=" * 60)
        print("RUNNING FIELD MAPPING TESTS")
        print("=" * 60)
        
        try:
            with odoo.api.Environment.manage():
                registry = odoo.modules.registry.Registry(self.db_name)
                with registry.cursor() as cr:
                    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                    
                    # Install required modules
                    print("Installing required modules...")
                    module = env['ir.module.module'].search([
                        ('name', '=', 'odoo_to_odoo_sync')
                    ], limit=1)
                    if module and module.state != 'installed':
                        module.button_immediate_install()
                        print("Module installed successfully")
                    
                    # Run tests
                    self.test_direct_mapping(env)
                    self.test_function_mapping(env)
                    self.test_computed_mapping(env)
                    self.test_relation_mapping(env)
                    self.test_error_handling(env)
                    
                    print("\n" + "=" * 60)
                    print("ALL TESTS COMPLETED SUCCESSFULLY!")
                    print("=" * 60)
                    
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def test_direct_mapping(self, env):
        """Test direct field mapping."""
        print("\n1. Testing Direct Mapping...")
        
        # Create test data
        Partner = env['res.partner']
        test_partner = Partner.create({
            'name': 'Test Direct Mapping',
            'email': 'direct@test.com'
        })
        
        # Create sync model and field
        SyncModel = env['odoo.sync.model']
        SyncField = env['odoo.sync.model.field']
        
        sync_model = SyncModel.create({
            'name': 'Test Direct Sync',
            'model_id': env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
        
        field_mapping = SyncField.create({
            'model_sync_id': sync_model.id,
            'field_id': env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'direct',
            'source_field': 'name',
            'target_field': 'name',
            'active': True
        })
        
        # Test the mapping
        SyncManager = env['odoo.sync.manager']
        result = SyncManager._apply_field_mapping(
            field_mapping,
            test_partner,
            'Test Direct Mapping'
        )
        
        assert result == 'Test Direct Mapping', f"Expected 'Test Direct Mapping', got {result}"
        print("   ✓ Direct mapping test passed")
    
    def test_function_mapping(self, env):
        """Test function-based field mapping."""
        print("\n2. Testing Function Mapping...")
        
        # Create test data
        Partner = env['res.partner']
        test_partner = Partner.create({
            'name': 'Test Function Mapping',
            'email': 'function@test.com'
        })
        
        SyncModel = env['odoo.sync.model']
        SyncField = env['odoo.sync.model.field']
        
        sync_model = SyncModel.create({
            'name': 'Test Function Sync',
            'model_id': env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
        
        field_mapping = SyncField.create({
            'model_sync_id': sync_model.id,
            'field_id': env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'function',
            'mapping_function': 'upper',
            'active': True
        })
        
        # Test the mapping
        SyncManager = env['odoo.sync.manager']
        result = SyncManager._apply_field_mapping(
            field_mapping,
            test_partner,
            'test function'
        )
        
        assert result == 'TEST FUNCTION', f"Expected 'TEST FUNCTION', got {result}"
        print("   ✓ Function mapping test passed")
    
    def test_computed_mapping(self, env):
        """Test computed field mapping."""
        print("\n3. Testing Computed Mapping...")
        
        # Create test data
        Partner = env['res.partner']
        test_partner = Partner.create({
            'name': 'Test Computed Mapping',
            'email': 'computed@test.com'
        })
        
        SyncModel = env['odoo.sync.model']
        SyncField = env['odoo.sync.model.field']
        
        sync_model = SyncModel.create({
            'name': 'Test Computed Sync',
            'model_id': env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
        
        field_mapping = SyncField.create({
            'model_sync_id': sync_model.id,
            'field_id': env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'computed',
            'mapping_expression': 'record.name.upper()',
            'active': True
        })
        
        # Test the mapping
        SyncManager = env['odoo.sync.manager']
        result = SyncManager._apply_field_mapping(
            field_mapping,
            test_partner,
            'test computed'
        )
        
        assert result == 'TEST COMPUTED MAPPING', f"Expected 'TEST COMPUTED MAPPING', got {result}"
        print("   ✓ Computed mapping test passed")
    
    def test_relation_mapping(self, env):
        """Test relation mapping."""
        print("\n4. Testing Relation Mapping...")
        
        # Create test data
        Country = env['res.country']
        test_country = Country.search([('code', '=', 'US')], limit=1)
        if not test_country:
            test_country = Country.create({
                'name': 'United States',
                'code': 'US'
            })
        
        Partner = env['res.partner']
        test_partner = Partner.create({
            'name': 'Test Relation Mapping',
            'email': 'relation@test.com'
        })
        
        SyncModel = env['odoo.sync.model']
        SyncField = env['odoo.sync.model.field']
        
        sync_model = SyncModel.create({
            'name': 'Test Relation Sync',
            'model_id': env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
        
        field_mapping = SyncField.create({
            'model_sync_id': sync_model.id,
            'field_id': env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'country_id')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'relation_domain': json.dumps([('active', '=', True)]),
            'active': True
        })
        
        # Test the mapping
        SyncManager = env['odoo.sync.manager']
        result = SyncManager._apply_field_mapping(
            field_mapping,
            test_partner,
            'US'
        )
        
        assert result == test_country.id, f"Expected {test_country.id}, got {result}"
        print("   ✓ Relation mapping test passed")
    
    def test_error_handling(self, env):
        """Test error handling in mappings."""
        print("\n5. Testing Error Handling...")
        
        Partner = env['res.partner']
        test_partner = Partner.create({
            'name': 'Test Error Handling',
            'email': 'error@test.com'
        })
        
        SyncModel = env['odoo.sync.model']
        SyncField = env['odoo.sync.model.field']
        
        sync_model = SyncModel.create({
            'name': 'Test Error Sync',
            'model_id': env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
        
        # Test invalid function
        field_mapping = SyncField.create({
            'model_sync_id': sync_model.id,
            'field_id': env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'function',
            'mapping_function': 'non_existent_method',
            'active': True
        })
        
        SyncManager = env['odoo.sync.manager']
        result = SyncManager._apply_field_mapping(
            field_mapping,
            test_partner,
            'test value'
        )
        
        # Should return original value on error
        assert result == 'test value', f"Expected 'test value', got {result}"
        print("   ✓ Error handling test passed")


def main():
    """Main test execution."""
    # Database name - adjust as needed
    db_name = os.environ.get('ODOO_DB', 'test_field_mapping')
    
    print(f"Testing field mapping with database: {db_name}")
    
    runner = FieldMappingTestRunner(db_name)
    
    if runner.setup_environment():
        runner.run_basic_tests()
    else:
        print("Failed to setup test environment")
        sys.exit(1)


if __name__ == '__main__':
    main()
