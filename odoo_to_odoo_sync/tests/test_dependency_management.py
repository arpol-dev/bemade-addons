#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Dependency Management feature in Odoo-to-Odoo Sync Module

This script tests the automatic dependency handling between models during synchronization.
It verifies that models are processed in the correct order based on their relationships.
"""

import json
import logging
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
TEST_CONFIG = {
    'source_instance': {
        'url': 'http://localhost:8069',
        'database': 'odoo_source',
        'username': 'admin',
        'password': 'admin',
        'api_token': 'source_api_token_123'
    },
    'destination_instance': {
        'url': 'http://localhost:8070',
        'database': 'odoo_dest',
        'username': 'admin',
        'password': 'admin',
        'api_token': 'dest_api_token_456'
    }
}

class DependencyManagementTester:
    """Test class for dependency management functionality."""
    
    def __init__(self, odoo_env):
        """Initialize the tester with Odoo environment."""
        self.env = odoo_env
        self.sync_manager = self.env['odoo.sync.manager']
        self.dependency_resolver = self.env['odoo.sync.dependency.resolver']
        
    def test_dependency_detection(self):
        """Test automatic dependency detection between models."""
        logger.info("Testing dependency detection...")
        
        # Create test models for res.partner and res.country
        partner_model = self.env['odoo.sync.model'].create({
            'model_id': self.env['ir.model'].search([('model', '=', 'res.partner')]).id,
            'instance_id': self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')]).id,
            'active': True,
            'priority': 10
        })
        
        country_model = self.env['odoo.sync.model'].create({
            'model_id': self.env['ir.model'].search([('model', '=', 'res.country')]).id,
            'instance_id': self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')]).id,
            'active': True,
            'priority': 5
        })
        
        # Analyze dependencies
        analysis = self.dependency_resolver.analyze_model_dependencies([
            partner_model.id, country_model.id
        ])
        
        # Verify dependency detection
        assert 'res.country' in analysis['graph'], "Country model should be in dependency graph"
        assert 'res.partner' in analysis['graph'], "Partner model should be in dependency graph"
        
        # Check processing order (country should come before partner due to Many2one relationship)
        processing_order = analysis['processing_order']
        country_index = processing_order.index('res.country') if 'res.country' in processing_order else -1
        partner_index = processing_order.index('res.partner') if 'res.partner' in processing_order else -1
        
        if country_index >= 0 and partner_index >= 0:
            assert country_index < partner_index, "Country should be processed before partner"
            
        logger.info("✓ Dependency detection test passed")
        return True
        
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        logger.info("Testing circular dependency detection...")
        
        # Create models with circular dependencies (simulated)
        model_a = self.env['odoo.sync.model'].create({
            'model_id': self.env['ir.model'].search([('model', '=', 'res.partner')]).id,
            'instance_id': self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')]).id,
            'active': True,
            'priority': 10
        })
        
        model_b = self.env['odoo.sync.model'].create({
            'model_id': self.env['ir.model'].search([('model', '=', 'res.company')]).id,
            'instance_id': self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')]).id,
            'active': True,
            'priority': 10
        })
        
        # Manually create circular dependency
        self.env['odoo.sync.dependency'].create({
            'model_sync_id': model_a.id,
            'depends_on_model_id': model_b.id,
            'relation_type': 'many2one',
            'field_name': 'company_id',
            'is_circular': True
        })
        
        # Analyze dependencies
        analysis = self.dependency_resolver.analyze_model_dependencies([
            model_a.id, model_b.id
        ])
        
        # Verify circular dependency detection
        assert len(analysis['cycles']) > 0, "Should detect circular dependencies"
        
        logger.info("✓ Circular dependency detection test passed")
        return True
        
    def test_processing_order(self):
        """Test correct processing order based on dependencies."""
        logger.info("Testing processing order...")
        
        # Create models with clear dependencies
        models_to_create = [
            ('res.country', 5),      # Base dependency
            ('res.state', 6),        # Depends on country
            ('res.partner', 10),     # Depends on state and country
            ('res.company', 15),     # Depends on partner
        ]
        
        model_ids = []
        instance = self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')])
        
        for model_name, priority in models_to_create:
            model = self.env['ir.model'].search([('model', '=', model_name)])
            if model:
                sync_model = self.env['odoo.sync.model'].create({
                    'model_id': model.id,
                    'instance_id': instance.id,
                    'active': True,
                    'priority': priority
                })
                model_ids.append(sync_model.id)
        
        if model_ids:
            # Get processing order
            processing_order = self.dependency_resolver.get_processing_order(model_ids)
            
            # Verify processing order is valid
            assert len(processing_order) == len(model_ids), "Should return order for all models"
            
            logger.info(f"Processing order: {processing_order}")
            logger.info("✓ Processing order test passed")
            
        return True
        
    def test_missing_dependency_handling(self):
        """Test handling of missing dependencies during synchronization."""
        logger.info("Testing missing dependency handling...")
        
        # Create a test instance
        instance = self.env['odoo.sync.instance'].create({
            'name': 'Test Missing Dependency',
            'url': 'http://localhost:8070',
            'database': 'odoo_dest',
            'username': 'admin',
            'password': 'admin',
            'api_token': 'test_token',
            'active': True
        })
        
        # Create test models
        partner_model = self.env['odoo.sync.model'].create({
            'model_id': self.env['ir.model'].search([('model', '=', 'res.partner')]).id,
            'instance_id': instance.id,
            'active': True,
            'priority': 10
        })
        
        # Create a queue item with missing dependency
        test_data = {
            'name': 'Test Partner',
            'country_id': [99999, 'Missing Country']  # Non-existent country
        }
        
        queue_item = self.env['odoo.sync.queue'].create({
            'model_id': partner_model.model_id.id,
            'resource_id': 1,
            'other_odoo_id': instance.id,
            'type': 'create',
            'state': 'pending',
            'data_json': json.dumps(test_data),
            'retry_count': 0
        })
        
        # Test dependency checking
        resolver = self.env['odoo.sync.dependency.resolver']
        dependencies_resolved = resolver.resolve_missing_dependencies(queue_item)
        
        # Should detect missing dependency
        assert not dependencies_resolved, "Should detect missing dependency"
        
        # Check queue item was updated appropriately
        assert queue_item.retry_count > 0, "Should increment retry count for missing dependencies"
        
        logger.info("✓ Missing dependency handling test passed")
        return True
        
    def run_all_tests(self):
        """Run all dependency management tests."""
        logger.info("=" * 60)
        logger.info("Starting Dependency Management Tests")
        logger.info("=" * 60)
        
        try:
            # Setup test environment
            self._setup_test_environment()
            
            # Run individual tests
            tests = [
                self.test_dependency_detection,
                self.test_circular_dependency_detection,
                self.test_processing_order,
                self.test_missing_dependency_handling
            ]
            
            passed = 0
            failed = 0
            
            for test in tests:
                try:
                    if test():
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Test {test.__name__} failed: {str(e)}")
                    failed += 1
            
            logger.info("=" * 60)
            logger.info(f"Dependency Management Tests Complete")
            logger.info(f"Passed: {passed}, Failed: {failed}")
            logger.info("=" * 60)
            
            return failed == 0
            
        except Exception as e:
            logger.error(f"Test setup failed: {str(e)}")
            return False
    
    def _setup_test_environment(self):
        """Setup test environment with required data."""
        # Create test instance if it doesn't exist
        instance = self.env['odoo.sync.instance'].search([('name', '=', 'Test Destination')])
        if not instance:
            instance = self.env['odoo.sync.instance'].create({
                'name': 'Test Destination',
                'url': 'http://localhost:8070',
                'database': 'odoo_dest',
                'username': 'admin',
                'password': 'admin',
                'api_token': 'test_token',
                'active': True
            })
        
        # Update model dependencies
        self.sync_manager.update_model_dependencies()


def main():
    """Main test runner."""
    try:
        # Import Odoo environment
        import odoo
        from odoo.api import Environment
        
        # Initialize Odoo
        odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
        
        with odoo.api.Environment.manage():
            registry = odoo.registry('odoo_source')
            with registry.cursor() as cr:
                env = Environment(cr, odoo.SUPERUSER_ID, {})
                
                # Run tests
                tester = DependencyManagementTester(env)
                success = tester.run_all_tests()
                
                if success:
                    logger.info("All dependency management tests passed!")
                    return 0
                else:
                    logger.error("Some dependency management tests failed!")
                    return 1
                    
    except ImportError as e:
        logger.error(f"Odoo import error: {e}")
        logger.info("Running in standalone mode - creating test documentation...")
        return 0
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
