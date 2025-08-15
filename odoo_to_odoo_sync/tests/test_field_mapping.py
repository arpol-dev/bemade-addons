#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite for Advanced Field Mapping in Odoo Sync Module

This module tests all 4 mapping types:
- direct: basic field-to-field mapping
- function: transformation via Python methods
- computed: Python expression evaluation
- relation: cross-model lookups
"""

import json
from unittest.mock import patch, MagicMock
from odoo.tests import common
from odoo.exceptions import ValidationError


class TestFieldMapping(common.TransactionCase):
    """Test cases for advanced field mapping functionality."""
    
    def setUp(self):
        """Set up test environment."""
        super(TestFieldMapping, self).setUp()
        
        # Get required models
        self.SyncModel = self.env['odoo.sync.model']
        self.SyncField = self.env['odoo.sync.model.field']
        self.SyncManager = self.env['odoo.sync.manager']
        self.Partner = self.env['res.partner']
        self.Country = self.env['res.country']
        
        # Create test data
        self.test_country = self.Country.create({
            'name': 'United States',
            'code': 'US'
        })
        
        # Create test partner
        self.test_partner = self.Partner.create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'phone': '+1234567890'
        })
        
        # Create sync model
        self.sync_model = self.SyncModel.create({
            'name': 'Test Partner Sync',
            'model_id': self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'target_model': 'res.partner',
            'active': True
        })
    
    def test_direct_mapping(self):
        """Test direct field mapping."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'direct',
            'source_field': 'name',
            'target_field': 'display_name',
            'active': True
        })
        
        # Test direct mapping
        result = self.SyncManager._apply_field_mapping(
            field_mapping, 
            self.test_partner, 
            'Test Partner'
        )
        self.assertEqual(result, 'Test Partner', "Direct mapping should return value as-is")
    
    def test_function_mapping(self):
        """Test function-based field mapping."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'function',
            'mapping_function': 'upper',
            'active': True
        })
        
        # Test function mapping
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'test value'
        )
        self.assertEqual(result, 'TEST VALUE', "Function mapping should apply upper()")
    
    def test_computed_mapping(self):
        """Test computed field mapping with expressions."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'computed',
            'mapping_expression': 'record.name.upper()',
            'active': True
        })
        
        # Test computed mapping
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'test partner'
        )
        self.assertEqual(result, 'TEST PARTNER', "Computed mapping should apply expression")
    
    def test_relation_mapping(self):
        """Test relation mapping with cross-model lookups."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'country_id')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'relation_domain': '[("active", "=", True)]',
            'active': True
        })
        
        # Test relation mapping
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'US'
        )
        self.assertEqual(result, self.test_country.id, 
                        "Relation mapping should return country ID")
    
    def test_relation_mapping_no_match(self):
        """Test relation mapping when no match found."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'country_id')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'active': True
        })
        
        # Test with non-existent country code
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'XX'
        )
        self.assertIsNone(result, "Should return None for no match")
    
    def test_invalid_mapping_type(self):
        """Test handling of invalid mapping type."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'invalid_type',
            'active': True
        })
        
        # Should handle invalid type gracefully
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'test value'
        )
        self.assertEqual(result, 'test value', 
                        "Invalid mapping type should return original value")
    
    def test_function_mapping_error(self):
        """Test error handling in function mapping."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'function',
            'mapping_function': 'non_existent_method',
            'active': True
        })
        
        # Should handle function errors gracefully
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'test value'
        )
        self.assertEqual(result, 'test value', 
                        "Function errors should return original value")
    
    def test_computed_mapping_error(self):
        """Test error handling in computed mapping."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'computed',
            'mapping_expression': 'invalid python syntax [',
            'active': True
        })
        
        # Should handle expression errors gracefully
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'test value'
        )
        self.assertEqual(result, 'test value', 
                        "Expression errors should return original value")
    
    def test_required_field_validation(self):
        """Test required field handling."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'required': True,
            'active': True
        })
        
        # Should raise exception for required field with no match
        with self.assertRaises(Exception):
            self.SyncManager._apply_field_mapping(
                field_mapping,
                self.test_partner,
                'XX'  # Non-existent country
            )
    
    def test_complex_computed_mapping(self):
        """Test complex computed field expressions."""
        # Update partner with more fields
        self.test_partner.write({
            'firstname': 'John',
            'lastname': 'Doe'
        })
        
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'name')
            ], limit=1).id,
            'mapping_type': 'computed',
            'mapping_expression': 'record.firstname + " " + record.lastname',
            'active': True
        })
        
        # Test complex expression
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'placeholder'
        )
        self.assertEqual(result, 'John Doe', 
                        "Complex computed mapping should work")
    
    def test_json_domain_parsing(self):
        """Test JSON domain parsing in relation mapping."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'country_id')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'relation_domain': json.dumps([('active', '=', True)]),
            'active': True
        })
        
        # Test with valid JSON domain
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'US'
        )
        self.assertEqual(result, self.test_country.id, 
                        "JSON domain parsing should work")
    
    def test_invalid_json_domain(self):
        """Test handling of invalid JSON domain."""
        field_mapping = self.SyncField.create({
            'model_sync_id': self.sync_model.id,
            'field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'res.partner'),
                ('name', '=', 'country_id')
            ], limit=1).id,
            'mapping_type': 'relation',
            'relation_model': 'res.country',
            'relation_field': 'code',
            'relation_domain': 'invalid json {',
            'active': True
        })
        
        # Should handle invalid JSON gracefully
        result = self.SyncManager._apply_field_mapping(
            field_mapping,
            self.test_partner,
            'US'
        )
        self.assertEqual(result, self.test_country.id, 
                        "Invalid JSON domain should not break mapping")


class TestFieldMappingIntegration(common.TransactionCase):
    """Integration tests for field mapping with sync process."""
    
    def setUp(self):
        super(TestFieldMappingIntegration, self).setUp()
        # Setup for integration tests
        self.sync_manager = self.env['odoo.sync.manager'].create({
            'name': 'Test Sync Manager'
        })
    
    def test_prepare_sync_data_with_mappings(self):
        """Test _prepare_sync_data with field mappings."""
        # This would test the full sync data preparation
        # Implementation depends on sync queue structure
        pass
    
    def test_end_to_end_sync_with_mappings(self):
        """Test complete sync process with all mapping types."""
        # This would test the full sync flow
        # Implementation depends on sync instance setup
        pass


if __name__ == '__main__':
    # Run tests
    import unittest
    unittest.main()
