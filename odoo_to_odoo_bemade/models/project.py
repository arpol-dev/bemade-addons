# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Project Extension for Client Synchronization.

This module extends the project model to support client synchronization features,
including marking projects as client projects and generating API tokens for
secure client connections.
"""

import logging
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProjectProject(models.Model):
    _name = 'project.project'
    _inherit = 'project.project'

    is_client_project = fields.Boolean(
        string='Client Project',
        default=False,
        help='Check this box to mark this project as a client project for synchronization'
    )
    
    client_key = fields.Char(
        string='Client Key',
        readonly=True,
        help='Unique client key for this project. Generated when project is marked as client project.'
    )
    
    client_api_token = fields.Char(
        string='Client API Token',
        readonly=True,
        help='API token for client synchronization. Generated when project is marked as client project.'
    )
    
    client_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.instance',
        string='Client Instance',
        readonly=True,
        help='The client instance associated with this project'
    )
    
    sync_model_ids = fields.One2many(
        comodel_name='odoo.to.bemade.sync.model',
        inverse_name='project_id',
        string='Synchronized Models',
        help='Models configured for synchronization with this project'
    )
    
    @api.onchange('is_client_project')
    def _onchange_is_client_project(self):
        """Generate API token and client key when project is marked as client project."""
        if self.is_client_project and not self.client_api_token:
            self.client_api_token = self._generate_api_token()
            # Generate a unique client key based on project ID and a random component
            if self.id:
                self.client_key = f"{self.id}-{self._generate_api_token()[:8]}"
            else:
                self.client_key = self._generate_api_token()[:16]
        elif not self.is_client_project:
            self.client_api_token = False
            self.client_key = False
            self.client_instance_id = False
    
    def _generate_api_token(self):
        """Generate a secure API token for client authentication.
        
        Returns:
            str: A secure random token
        """
        return secrets.token_urlsafe(32)
    
    def action_generate_api_token(self):
        """Manually generate or regenerate API token for client project.
        
        This method can be called from the UI to generate a new API token
        for an existing client project.
        """
        for record in self:
            if not record.is_client_project:
                raise UserError(_("Only client projects can have API tokens. Please mark this project as a client project first."))
            record.client_api_token = record._generate_api_token()
        return True
    
    def action_revoke_api_token(self):
        """Revoke the API token for a client project.
        
        This method clears the API token and disconnects any associated client instance.
        """
        for record in self:
            record.client_api_token = False
            record.client_instance_id = False
        return True
