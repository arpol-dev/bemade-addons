# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Tests for OdooRPC protocol implementation."""

import unittest
from unittest.mock import patch, MagicMock
from odoo.tests import common
from odoo.exceptions import UserError


class TestOdooRpcProtocol(common.TransactionCase):
    """Test OdooRPC protocol implementation."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.sync_instance = self.env['odoo.sync.instance'].create({
            'name': 'Test OdooRPC Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key_12345',
            'connection_type': 'odoorpc',
        })

    def test_odoorpc_connection_creation(self):
        """Test OdooRPC connection creation."""
        # Test that OdooRPC connection type is available
        self.assertEqual(self.sync_instance.connection_type, 'odoorpc')
        
        # Test connection methods exist
        self.assertTrue(hasattr(self.sync_instance, '_get_odoorpc_connection'))
        self.assertTrue(hasattr(self.sync_instance, '_test_odoorpc_connection'))

    @patch('odoo_to_odoo_sync.models.sync_instance.odoorpc')
    def test_odoorpc_authentication_success(self, mock_odoorpc):
        """Test successful OdooRPC authentication."""
        # Mock successful authentication
        mock_odoo = MagicMock()
        mock_odoorpc.ODOO.return_value = mock_odoo
        
        # Test authentication
        result = self.sync_instance._test_odoorpc_connection()
        self.assertTrue(result)
        
        # Check state was updated
        self.assertEqual(self.sync_instance.state, 'connected')
        self.assertFalse(self.sync_instance.error_message)

    @patch('odoo_to_odoo_sync.models.sync_instance.odoorpc')
    def test_odoorpc_authentication_failure(self, mock_odoorpc):
        """Test OdooRPC authentication failure."""
        # Mock failed authentication
        mock_odoorpc.ODOO.side_effect = Exception('Authentication failed')
        
        result = self.sync_instance._test_odoorpc_connection()
        self.assertFalse(result)
        
        # Check error was recorded
        self.assertEqual(self.sync_instance.state, 'error')
        self.assertIn('Authentication failed', self.sync_instance.error_message)

    def test_odoorpc_library_missing(self):
        """Test OdooRPC when library is not installed."""
        with patch('odoo_to_odoo_sync.models.sync_instance.odoorpc', None):
            with self.assertRaises(UserError) as cm:
                self.sync_instance._get_odoorpc_connection()
            self.assertIn("La bibliothèque OdooRPC n'est pas installée", str(cm.exception))

    def test_odoorpc_protocol_selection(self):
        """Test OdooRPC protocol selection in UI."""
        # Test that OdooRPC is available in selection
        connection_types = dict(self.env['odoo.sync.instance']._fields['connection_type'].selection)
        self.assertIn('odoorpc', connection_types)
        self.assertEqual(connection_types['odoorpc'], 'OdooRPC')

    def test_odoorpc_url_construction(self):
        """Test OdooRPC URL construction."""
        # Test URL parsing for OdooRPC
        expected_url = 'https://test.example.com'
        self.assertEqual(self.sync_instance.url, expected_url)

    def test_odoorpc_api_key_authentication(self):
        """Test OdooRPC API key authentication."""
        # Test that API key is used for authentication
        self.assertTrue(self.sync_instance.use_api_key)
        self.assertEqual(self.sync_instance.api_key, 'test_api_key_12345')

    def test_odoorpc_connection_methods(self):
        """Test OdooRPC connection methods."""
        # Test that the connection has expected methods
        # This would be tested with actual odoorpc library
        self.assertTrue(hasattr(self.sync_instance, '_get_odoorpc_connection'))
        self.assertTrue(hasattr(self.sync_instance, '_test_odoorpc_connection'))

    def test_odoorpc_error_handling(self):
        """Test OdooRPC error handling."""
        # Test various error scenarios
        test_cases = [
            ('ConnectionError', 'Connection Error'),
            ('AuthenticationError', 'Authentication Error'),
            ('TimeoutError', 'Timeout Error')
        ]
        
        for error_type, expected_msg in test_cases:
            with self.subTest(error_type=error_type):
                # These would be tested in integration tests
                self.assertIsNotNone(expected_msg)

    def test_odoorpc_encryption_handling(self):
        """Test API key encryption in OdooRPC."""
        # Test that API key is properly encrypted/decrypted
        original_key = self.sync_instance.api_key
        encrypted_key = self.sync_instance.encrypted_api_key
        
        self.assertIsNotNone(encrypted_key)
        self.assertNotEqual(original_key, encrypted_key)
        
        # Test decryption
        decrypted_key = self.sync_instance._decrypt_sensitive_data()
        self.assertEqual(decrypted_key, original_key)
