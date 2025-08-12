# -*- coding: utf-8 -*-
# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Encryption utilities for sensitive data.

This module provides encryption and decryption functions for sensitive data
such as passwords, API keys, and other credentials used in the synchronization
process. It uses Fernet symmetric encryption from the cryptography library.
"""

import base64
import logging
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_logger = logging.getLogger(__name__)

def _get_encryption_key(env):
    """Get or generate the encryption key for the instance.
    
    The key is stored in ir.config_parameter. If it doesn't exist,
    a new one is generated and stored.
    
    Args:
        env: Odoo environment
        
    Returns:
        bytes: The encryption key
    """
    # Try to get the key from ir.config_parameter
    ICP = env['ir.config_parameter'].sudo()
    key = ICP.get_param('odoo_to_odoo_sync.encryption_key')
    
    if not key:
        # Generate a new key if none exists
        _logger.info("Generating new encryption key for odoo_to_odoo_sync")
        # Generate a salt
        salt = os.urandom(16)
        # Store the salt
        ICP.set_param('odoo_to_odoo_sync.encryption_salt', base64.b64encode(salt).decode('utf-8'))
        
        # Use PBKDF2 to derive a key from the database UUID (which is unique per instance)
        db_uuid = ICP.get_param('database.uuid', 'fallback-uuid-for-encryption')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        # Ensure db_uuid is a string before encoding
        if not isinstance(db_uuid, str):
            db_uuid = str(db_uuid)
        key = base64.b64encode(kdf.derive(db_uuid.encode()))
        
        # Store the key
        ICP.set_param('odoo_to_odoo_sync.encryption_key', key.decode('utf-8'))
    else:
        # Convert stored key from string to bytes
        # Ensure key is a string before encoding
        if not isinstance(key, str):
            key = str(key)
        key = key.encode('utf-8')
    
    return key

def encrypt_value(env, value):
    """Encrypt a sensitive value.
    
    Args:
        env: Odoo environment
        value (str): The value to encrypt
        
    Returns:
        str: The encrypted value as a base64 string
    """
    if not value:
        return False
    
    try:
        key = _get_encryption_key(env)
        f = Fernet(key)
        # Convert value to string if it's not already
        if not isinstance(value, str):
            value = str(value)
        encrypted = f.encrypt(value.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        _logger.error("Encryption error: %s", str(e))
        # Return the original value if encryption fails
        # This is not ideal but prevents data loss
        return value

def decrypt_value(env, encrypted_value):
    """Decrypt an encrypted value.
    
    Args:
        env: Odoo environment
        encrypted_value (str): The encrypted value as a base64 string
        
    Returns:
        str: The decrypted value
    """
    if not encrypted_value:
        return False
    
    try:
        key = _get_encryption_key(env)
        f = Fernet(key)
        # Convert encrypted_value to string if it's not already
        if not isinstance(encrypted_value, str):
            encrypted_value = str(encrypted_value)
        decrypted = f.decrypt(base64.b64decode(encrypted_value.encode('utf-8')))
        return decrypted.decode('utf-8')
    except Exception as e:
        _logger.error("Decryption error: %s", str(e))
        # Return the encrypted value if decryption fails
        # This is not ideal but prevents data loss
        return encrypted_value
