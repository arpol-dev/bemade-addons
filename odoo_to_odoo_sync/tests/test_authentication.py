# -*- coding: utf-8 -*-

from odoo.tests import common
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestAPITokenAuthentication(common.TransactionCase):
    """Test API token authentication functionality."""

    def setUp(self):
        super(TestAPITokenAuthentication, self).setUp()
        self.SyncInstance = self.env['odoo.sync.instance']

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

    def test_api_key_field_requirements(self):
        """Test that API key field is properly required."""
        # Should succeed with API key
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'valid_api_key'
        })
        self.assertTrue(instance.id)
        
        # Verify key is stored correctly
        self.assertEqual(instance.api_key, 'valid_api_key')

    def test_missing_credentials_error_handling(self):
        """Test error handling for missing credentials."""
        # Should fail without API key
        with self.assertRaises(ValidationError):
            self.SyncInstance.create({
                'name': 'Test Instance',
                'url': 'https://test.example.com',
                'database': 'test_db',
                'username': 'test_user',
                # Missing api_key
            })

    def test_api_key_format_validation(self):
        """Test API key format validation."""
        # Test valid API key format
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': '1f940dce111dd177907678547230ca6e854ad270'
        })
        
        # Verify key is stored correctly
        self.assertEqual(len(instance.api_key), 40)  # Odoo 18 API key length
        self.assertTrue(instance.api_key.isalnum())

    def test_field_validation(self):
        """Test field validation for sync instance."""
        # Test valid URL format
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://valid-url.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'valid_api_key'
        })
        
        self.assertTrue(instance.url.startswith('http'))

    def test_protocol_selection(self):
        """Test protocol selection validation."""
        # Test valid protocols
        valid_protocols = ['jsonrpc', 'xmlrpc', 'odoorpc']
        
        for protocol in valid_protocols:
            instance = self.SyncInstance.create({
                'name': f'Test {protocol}',
                'url': 'https://test.example.com',
                'database': 'test_db',
                'username': 'test_user',
                'api_key': 'test_api_key',
                'connection_type': protocol
            })
            self.assertEqual(instance.connection_type, protocol)

    def test_instance_creation_and_cleanup(self):
        """Test instance creation and cleanup."""
        instance = self.SyncInstance.create({
            'name': 'Test Instance',
            'url': 'https://test.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key'
        })
        
        # Verify instance was created
        self.assertTrue(instance.id)
        
        # Test that instance can be found
        found = self.SyncInstance.search([('name', '=', 'Test Instance')])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, instance.id)
        
        # Test cleanup
        instance.unlink()
        
        # Verify instance was removed
        remaining = self.SyncInstance.search([('id', '=', instance.id)])
        self.assertFalse(remaining)
