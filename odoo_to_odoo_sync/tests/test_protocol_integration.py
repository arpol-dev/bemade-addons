# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Integration tests for all synchronization protocols."""

import unittest
from unittest.mock import patch, MagicMock
from odoo.tests import common
from odoo.exceptions import UserError


class TestProtocolIntegration(common.TransactionCase):
    """Test integration of all synchronization protocols."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create test instances for each protocol
        self.xmlrpc_instance = self.env['odoo.sync.instance'].create({
            'name': 'Test XML-RPC Instance',
            'url': 'https://test1.example.com',
            'database': 'test_db1',
            'username': 'test_user1',
            'api_key': 'test_api_key_1',
            'connection_type': 'xmlrpc',
        })
        
        self.jsonrpc_instance = self.env['odoo.sync.instance'].create({
            'name': 'Test JSON-RPC Instance',
            'url': 'https://test2.example.com',
            'database': 'test_db2',
            'username': 'test_user2',
            'api_key': 'test_api_key_2',
            'connection_type': 'jsonrpc',
        })
        
        self.odoorpc_instance = self.env['odoo.sync.instance'].create({
            'name': 'Test OdooRPC Instance',
            'url': 'https://test3.example.com',
            'database': 'test_db3',
            'username': 'test_user3',
            'api_key': 'test_api_key_3',
            'connection_type': 'odoorpc',
        })

    def test_protocol_selection(self):
        """Test that all protocols are available for selection."""
        connection_types = dict(self.env['odoo.sync.instance']._fields['connection_type'].selection)
        
        expected_protocols = ['xmlrpc', 'jsonrpc', 'odoorpc']
        for protocol in expected_protocols:
            self.assertIn(protocol, connection_types)

    def test_connection_method_dispatch(self):
        """Test that connection methods dispatch correctly."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test that appropriate connection method exists
                method_name = f'_get_{instance.connection_type}_connection'
                self.assertTrue(hasattr(instance, method_name))
                
                test_method_name = f'_test_{instance.connection_type}_connection'
                self.assertTrue(hasattr(instance, test_method_name))

    def test_api_key_encryption_across_protocols(self):
        """Test API key encryption works consistently across all protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test encryption/decryption
                original_key = instance.api_key
                encrypted_key = instance.encrypted_api_key
                
                self.assertIsNotNone(encrypted_key)
                self.assertNotEqual(original_key, encrypted_key)
                
                decrypted_key = instance._decrypt_sensitive_data()
                self.assertEqual(decrypted_key, original_key)

    def test_error_handling_consistency(self):
        """Test error handling is consistent across protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test that error handling follows same pattern
                self.assertTrue(hasattr(instance, 'state'))
                self.assertTrue(hasattr(instance, 'error_message'))
                self.assertTrue(hasattr(instance, 'last_connection'))

    def test_authentication_method_consistency(self):
        """Test authentication methods are consistent across protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # All should use API key for authentication
                self.assertTrue(instance.use_api_key)
                
                # Test that username and API key are used
                self.assertIsNotNone(instance.username)
                self.assertIsNotNone(instance.api_key)

    def test_connection_timeout_configuration(self):
        """Test connection timeout configuration works for all protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test timeout configuration
                self.assertTrue(hasattr(instance, 'connection_timeout'))
                self.assertIsInstance(instance.connection_timeout, int)
                self.assertGreater(instance.connection_timeout, 0)

    def test_url_protocol_handling(self):
        """Test URL protocol handling for different connection types."""
        test_cases = [
            ('xmlrpc', 'http://test.com'),
            ('xmlrpc', 'https://test.com'),
            ('jsonrpc', 'http://test.com'),
            ('jsonrpc', 'https://test.com'),
            ('odoorpc', 'http://test.com'),
            ('odoorpc', 'https://test.com'),
        ]
        
        for protocol, url in test_cases:
            with self.subTest(protocol=protocol, url=url):
                instance = self.env['odoo.sync.instance'].create({
                    'name': f'Test {protocol.upper()}',
                    'url': url,
                    'database': 'test_db',
                    'username': 'test_user',
                    'api_key': 'test_api_key',
                    'connection_type': protocol,
                })
                
                # Test URL is stored correctly
                self.assertEqual(instance.url, url)

    def test_state_management_consistency(self):
        """Test state management is consistent across protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test state transitions
                self.assertIn(instance.state, ['draft', 'testing', 'connected', 'error'])

    def test_error_message_format_consistency(self):
        """Test error message format is consistent across protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test error message is properly formatted
                if instance.error_message:
                    self.assertIsInstance(instance.error_message, str)
                    self.assertGreater(len(instance.error_message), 0)

    def test_connection_testing_workflow(self):
        """Test connection testing workflow for all protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test test_connection method exists
                self.assertTrue(hasattr(instance, 'test_connection'))
                
                # Test method signature
                self.assertTrue(callable(getattr(instance, 'test_connection')))

    def test_field_mapping_consistency(self):
        """Test field mapping consistency across protocols."""
        instances = [self.xmlrpc_instance, self.jsonrpc_instance, self.odoorpc_instance]
        
        for instance in instances:
            with self.subTest(protocol=instance.connection_type):
                # Test common fields exist
                expected_fields = [
                    'name', 'url', 'database', 'username', 'api_key',
                    'connection_type', 'state', 'last_connection', 'error_message'
                ]
                
                for field in expected_fields:
                    self.assertTrue(hasattr(instance, field))
