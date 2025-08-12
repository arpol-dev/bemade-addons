# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Conflict Resolution Wizard Field.

This module defines the field-level conflict resolution model used by the
conflict resolution wizard to handle field-by-field resolution choices.
"""

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class OdooSyncConflictWizardField(models.TransientModel):
    """Field-level conflict resolution.
    
    This model represents a single field that needs resolution
    in a synchronization conflict.
    """
    
    _name = 'odoo.sync.conflict.wizard.field'
    _description = 'Conflict Resolution Field'
    
    wizard_id = fields.Many2one(
        comodel_name='odoo.sync.conflict.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    field_name = fields.Char(
        string='Nom du champ',
        required=True
    )
    
    local_value = fields.Text(
        string='Valeur locale',
        readonly=True
    )
    
    remote_value = fields.Text(
        string='Valeur distante',
        readonly=True
    )
    
    source = fields.Selection(
        selection=[
            ('local', 'Source'),
            ('remote', 'Destination'),
            ('custom', 'Personnalisé'),
            ('ignore', 'Ignorer')
        ],
        string='Source',
        required=True,
        default='local'
    )
    
    custom_value = fields.Text(
        string='Valeur personnalisée'
    )
    
    # Timestamp fields for comparison
    local_write_date = fields.Datetime(
        string='Date de modification locale',
        readonly=True
    )
    
    remote_write_date = fields.Datetime(
        string='Date de modification distante',
        readonly=True
    )
