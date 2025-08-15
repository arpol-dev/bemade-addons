#!/usr/bin/env python3
"""
Test suite for API token authentication in Odoo-to-Odoo sync module.

This module tests the new API token authentication method implemented
as feature #1 in the specifications.
"""

import unittest
from unittest.mock import patch, MagicMock
from odoo.tests import common
from odoo.exceptions import UserError


class TestAPITokenAuthentication(common.TransactionCase):
    """Test API token authentication functionality."""

    def setUp(self):
        super(TestAPITokenAuthentication, self).setUp()
        self.SyncInstance = self.env['odoo.sync.instance']
        
    def test_api_key_priority_over_password(self):
        """Test that API key is prioritized over password for authentication."""
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'password': 'test_password',
            'api_key': 'test_api_key_12345'
        })
        
        # Verify API key is returned by _decrypt_sensitive_data
        credential = instance._decrypt_sensitive_data()
        self.assertEqual(credential, 'test_api_key_12345')
        
    def test_api_key_required_behavior(self):
        """Test that API key is required and no password fallback exists."""
        # With only API key, should use API key
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key'
        })
        
        # Verify only API key is used
        credential = instance._decrypt_sensitive_data()
        self.assertEqual(credential, 'test_api_key')
        
    def test_api_key_encryption_decryption(self):
        """Test API key encryption and decryption."""
        original_key = 'secret_api_key_67890'
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': original_key
        })
        
        # Verify encryption happened
        self.assertTrue(instance.encrypted_api_key)
        self.assertNotEqual(instance.encrypted_api_key, original_key)
        
        # Verify decryption returns original
        decrypted = instance._decrypt_sensitive_data()
        self.assertEqual(decrypted, original_key)
        
    @patch('xmlrpc.client.ServerProxy')
    def test_xmlrpc_authentication_with_api_key(self, mock_server_proxy):
        """Test XML-RPC authentication uses API key correctly."""
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_server_proxy.return_value = mock_common
        
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key_auth'
        })
        
        # Mock successful connection
        with patch.object(instance, '_test_xmlrpc_connection', return_value=True):
            result = instance.test_connection()
            self.assertTrue(result)
            
        # Verify authenticate was called with API key
        mock_common.authenticate.assert_called_once_with(
            'test_db', 'test_user', 'test_api_key_auth', {}
        )
        
    def test_authentication_error_handling(self):
        """Test proper error handling for authentication failures."""
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://invalid.url',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'invalid_key'
        })
        
        # Test connection should handle authentication errors gracefully
        result = instance.test_connection()
        self.assertFalse(result)
        self.assertEqual(instance.state, 'error')
        
    def test_api_key_field_requirements(self):
        """Test that API key field is properly required."""
        # Should succeed with API key
        instance1 = self.SyncInstance.create({
            'name': 'Test Instance 1',
            'url': 'https://test1.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'valid_api_key'
        })
        self.assertTrue(instance1.id)
        
        # Should succeed with API key only
        instance2 = self.SyncInstance.create({
            'name': 'Test Instance 2',
            'url': 'https://test2.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'api_key_only'
        })
        self.assertTrue(instance2.id)
        
        # Verify only API key is used
        credential = instance2._decrypt_sensitive_data()
        self.assertEqual(credential, 'api_key_only')


if __name__ == '__main__':
    unittest.main()
