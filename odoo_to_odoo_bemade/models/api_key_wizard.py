# -*- coding: utf-8 -*-
# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""API Key Display Wizard.

This module provides a wizard for displaying a newly generated API key
to the user. The key is only shown once for security reasons.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class OdooToBemadeApiKeyDisplay(models.TransientModel):
    """Wizard to display a newly generated API key."""

    _name = 'odoo.to.bemade.api.key.display'
    _description = 'API Key Display Wizard'

    api_key_id = fields.Many2one(
        'odoo.to.bemade.api.key',
        string='API Key',
        required=True,
        readonly=True,
    )
    
    api_key = fields.Char(
        string='API Key Value',
        readonly=True,
        help='This API key will only be shown once. Please copy it now.',
    )
    
    warning_message = fields.Html(
        string='Warning',
        readonly=True,
        default="""
            <div class="alert alert-warning" role="alert">
                <strong>Important!</strong> This API key will only be shown once.
                Please copy it now and store it securely. You will not be able to
                retrieve it later.
            </div>
        """,
    )
