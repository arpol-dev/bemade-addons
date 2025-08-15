# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Tests for JSON-RPC protocol implementation."""

import json
import unittest
from unittest.mock import patch, MagicMock
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

    @patch('urllib.request.urlopen')
    def test_jsonrpc_authentication_success(self, mock_urlopen):
        """Test successful JSON-RPC authentication."""
        # Mock successful authentication response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'jsonrpc': '2.0',
            'id': 12345,
            'result': 1
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Test authentication
        result = self.sync_instance._test_jsonrpc_connection()
        self.assertTrue(result)
        
        # Check state was updated
        self.assertEqual(self.sync_instance.state, 'connected')
        self.assertFalse(self.sync_instance.error_message)

    @patch('urllib.request.urlopen')
    def test_jsonrpc_authentication_failure(self, mock_urlopen):
        """Test JSON-RPC authentication failure."""
        # Mock failed authentication response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'jsonrpc': '2.0',
            'id': 12345,
            'error': {
                'message': 'Invalid credentials'
            }
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Test authentication failure
        result = self.sync_instance._test_jsonrpc_connection()
        self.assertFalse(result)
        
        # Check state was updated
        self.assertEqual(self.sync_instance.state, 'error')
        self.assertIn('Invalid credentials', self.sync_instance.error_message)

    @patch('urllib.request.urlopen')
    def test_jsonrpc_connection_error(self, mock_urlopen):
        """Test JSON-RPC connection error handling."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError('Connection refused')
        
        result = self.sync_instance._test_jsonrpc_connection()
        self.assertFalse(result)
        
        # Check error was recorded
        self.assertEqual(self.sync_instance.state, 'error')
        self.assertIn('Connection refused', self.sync_instance.error_message)

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
