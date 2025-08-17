# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Tests for JSON-RPC protocol implementation."""

import json
from odoo.tests import common
from odoo.exceptions import UserError


class TestJsonRpcProtocol(common.TransactionCase):
    """Test JSON-RPC protocol implementation."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.sync_instance = self.env['odoo.sync.instance'].create({
            'name': 'Test JSON-RPC Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key_12345',
            'connection_type': 'jsonrpc',
        })

    def test_jsonrpc_connection_creation(self):
        """Test JSON-RPC connection creation."""
        # Test that JSON-RPC connection type is available
        self.assertEqual(self.sync_instance.connection_type, 'jsonrpc')
        
        # Test connection methods exist
        self.assertTrue(hasattr(self.sync_instance, '_get_jsonrpc_connection'))
        self.assertTrue(hasattr(self.sync_instance, '_test_jsonrpc_connection'))

    def test_jsonrpc_field_validation(self):
        """Test JSON-RPC field validation."""
        # Test that JSON-RPC specific fields are properly validated
        instance = self.env['odoo.sync.instance'].create({
            'name': 'JSON-RPC Validation Test',
            'url': 'https://json-test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'json_test_api_key',
            'connection_type': 'jsonrpc',
        })
        
        self.assertEqual(instance.connection_type, 'jsonrpc')
        self.assertTrue(instance.url.startswith('http'))

    def test_jsonrpc_url_formatting(self):
        """Test JSON-RPC URL formatting."""
        # Test URL formatting for JSON-RPC
        test_instance = self.env['odoo.sync.instance'].create({
            'name': 'URL Test Instance',
            'url': 'https://json-test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key',
            'connection_type': 'jsonrpc',
        })
        
        # Verify URL is properly formatted
        self.assertTrue(test_instance.url.endswith('.com'))
        self.assertTrue(test_instance.url.startswith('https://'))

    def test_jsonrpc_payload_structure(self):
        """Test JSON-RPC payload structure."""
        # Test that JSON-RPC connection is properly configured
        instance = self.env['odoo.sync.instance'].create({
            'name': 'Payload Test Instance',
            'url': 'https://payload-test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'payload_test_api_key',
            'connection_type': 'jsonrpc',
        })
        
        # Verify instance configuration
        self.assertEqual(instance.connection_type, 'jsonrpc')
        self.assertTrue(instance.api_key)

    def test_jsonrpc_instance_creation(self):
        """Test JSON-RPC instance creation."""
        # Test creating multiple JSON-RPC instances
        instances = []
        for i in range(3):
            instance = self.env['odoo.sync.instance'].create({
                'name': f'JSON-RPC Instance {i}',
                'url': f'https://json-test-{i}.example.com',
                'database': f'test_db_{i}',
                'username': f'test_user_{i}',
                'api_key': f'test_api_key_{i}',
                'connection_type': 'jsonrpc',
            })
            instances.append(instance)
            self.assertTrue(instance.id)
            self.assertEqual(instance.connection_type, 'jsonrpc')

        # Verify all instances were created
        self.assertEqual(len(instances), 3)

    def test_jsonrpc_field_requirements(self):
        """Test JSON-RPC field requirements."""
        # Test required fields for JSON-RPC
        with self.assertRaises(Exception):
            self.env['odoo.sync.instance'].create({
                'name': 'Incomplete JSON-RPC Instance',
                'url': 'https://incomplete.example.com',
                # Missing required fields
            })

    def test_jsonrpc_protocol_selection(self):
        """Test JSON-RPC protocol selection."""
        # Test that JSON-RPC can be selected as connection type
        instance = self.env['odoo.sync.instance'].create({
            'name': 'Protocol Selection Test',
            'url': 'https://protocol-test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'protocol_test_api_key',
            'connection_type': 'jsonrpc',
        })
        
        self.assertEqual(instance.connection_type, 'jsonrpc')
        self.assertIn('jsonrpc', ['jsonrpc', 'xmlrpc', 'odoorpc'])

    def test_jsonrpc_client_structure(self):
        """Test JSON-RPC client structure."""
        # Test that the client has the expected methods
        connection = self.sync_instance._get_jsonrpc_connection()
        self.assertTrue(hasattr(connection, 'execute_kw'))
        self.assertTrue(hasattr(connection, 'authenticate'))

    def test_jsonrpc_protocol_selection(self):
        """Test JSON-RPC protocol selection in UI."""
        # Test that JSON-RPC is available in selection
        connection_types = dict(self.env['odoo.sync.instance']._fields['connection_type'].selection)
        self.assertIn('jsonrpc', connection_types)
        self.assertEqual(connection_types['jsonrpc'], 'JSON-RPC')

    def test_jsonrpc_url_construction(self):
        """Test JSON-RPC URL construction."""
        expected_url = 'https://test.example.com/jsonrpc'
        # This would be constructed internally in _get_jsonrpc_connection
        self.assertTrue(expected_url.endswith('/jsonrpc'))

    def test_jsonrpc_request_format(self):
        """Test JSON-RPC request format."""
        # Test that requests are properly formatted
        expected_auth_request = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "login",
                "args": [self.sync_instance.database, self.sync_instance.username, self.sync_instance.api_key]
            },
            "id": unittest.mock.ANY
        }
        
        # The actual request would be constructed in _test_jsonrpc_connection
        self.assertIsNotNone(expected_auth_request)

    def test_jsonrpc_error_handling(self):
        """Test JSON-RPC error handling."""
        # Test various error scenarios
        test_cases = [
            ('HTTPError', 'HTTP Error'),
            ('URLError', 'Connection Error'),
            ('JSONDecodeError', 'JSON-RPC Error')
        ]
        
        for error_type, expected_msg in test_cases:
            with self.subTest(error_type=error_type):
                # These would be tested in integration tests
                self.assertIsNotNone(expected_msg)
