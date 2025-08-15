# -*- coding: utf-8 -*-
# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""API Key Management for Bemade Odoo Sync.

This module provides functionality for generating, tracking, and revoking
API keys used for authentication between Odoo instances.
"""

import logging
import secrets
import string
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeApiKey(models.Model):
    """API Key for Bemade Odoo Sync.

    This model stores API keys that can be used for authentication
    between Odoo instances.
    """

    _name = 'odoo.to.bemade.api.key'
    _description = 'Bemade API Key'
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        required=True,
        help='A descriptive name for this API key',
    )

    key = fields.Char(
        string='API Key',
        readonly=True,
        copy=False,
        help='The API key value (only shown once upon creation)',
    )

    key_hash = fields.Char(
        string='API Key Hash',
        readonly=True,
        copy=False,
        help='Hashed value of the API key for verification',
    )

    user_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True,
        required=True,
        help='User who created this API key',
    )

    create_date = fields.Datetime(
        string='Created On',
        readonly=True,
    )

    last_used = fields.Datetime(
        string='Last Used',
        readonly=True,
        help='Last time this API key was used for authentication',
    )

    expiration_date = fields.Date(
        string='Expiration Date',
        help='Date when this API key expires (leave empty for no expiration)',
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this API key is active and can be used for authentication',
    )

    instance_ids = fields.One2many(
        'odoo.to.bemade.instance',
        'api_key_id',
        string='Used In Instances',
        help='Instances using this API key',
    )

    usage_count = fields.Integer(
        string='Usage Count',
        default=0,
        readonly=True,
        help='Number of times this API key has been used',
    )

    notes = fields.Text(
        string='Notes',
        help='Additional notes about this API key',
    )

    @api.model
    def generate_key(self):
        """Generate a new API key.

        Returns:
            str: The generated API key
        """
        # Generate a random 32-character string
        alphabet = string.ascii_letters + string.digits
        key = ''.join(secrets.choice(alphabet) for _ in range(32))
        return key

    def action_generate_key(self):
        """Generate a new API key and store its hash.

        Returns:
            dict: Action to open a wizard showing the generated key
        """
        self.ensure_one()
        
        # Generate a new API key
        key = self.generate_key()
        
        # Store the key hash (in a real implementation, use a proper hashing algorithm)
        # For this example, we're just storing the key directly, but in production
        # you should use a secure hashing algorithm like bcrypt
        self.write({
            'key': key,
            'key_hash': key,  # In production, store a hash instead
            'is_active': True,
        })
        
        # Return an action to open a wizard showing the key
        return {
            'name': _('API Key Generated'),
            'type': 'ir.actions.act_window',
            'res_model': 'odoo.to.bemade.api.key.display',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_api_key_id': self.id,
                'default_api_key': key,
            },
        }

    def action_revoke(self):
        """Revoke this API key.

        Returns:
            bool: True
        """
        self.ensure_one()
        self.write({
            'is_active': False,
        })
        return True

    def action_activate(self):
        """Activate this API key.

        Returns:
            bool: True
        """
        self.ensure_one()
        self.write({
            'is_active': True,
        })
        return True

    def record_usage(self):
        """Record that this API key has been used.

        Returns:
            bool: True
        """
        self.ensure_one()
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1,
        })
        return True

    @api.model
    def validate_key(self, key):
        """Validate an API key.

        Args:
            key (str): The API key to validate

        Returns:
            bool: True if the key is valid, False otherwise
        """
        # In a real implementation, hash the key and compare with stored hashes
        # For this example, we're just comparing the key directly
        api_key = self.search([
            ('key_hash', '=', key),
            ('is_active', '=', True),
        ], limit=1)
        
        if not api_key:
            return False
            
        # Check if the key has expired
        if api_key.expiration_date and api_key.expiration_date < fields.Date.today():
            return False
            
        # Record usage
        api_key.record_usage()
        
        return True
