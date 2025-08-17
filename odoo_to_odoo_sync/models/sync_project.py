# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

import logging
import secrets
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SyncProject(models.Model):
    _name = 'sync.project'
    _description = 'Synchronization Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # Project identification
    is_sync_project = fields.Boolean(string='Synchronization Project', default=False)
    is_client_project = fields.Boolean(string='Client Project', default=False)
    
    # API Token management
    client_key = fields.Char(string='Client Key', readonly=True)
    api_token = fields.Char(string='API Token', readonly=True)
    
    # Connection details
    remote_url = fields.Char(string='Remote URL')
    remote_database = fields.Char(string='Remote Database')
    remote_username = fields.Char(string='Remote Username')
    
    # Sync configuration
    sync_instance_id = fields.Many2one(
        'odoo.sync.instance', string='Sync Instance',
        help='The sync instance associated with this project'
    )
    
    sync_model_ids = fields.One2many(
        'odoo.sync.model', 'project_id', string='Synchronized Models',
        help='Models configured for synchronization with this project'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('configured', 'Configured'),
        ('connected', 'Connected'),
        ('syncing', 'Syncing'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)
    
    last_sync_date = fields.Datetime(string='Last Sync Date')
    error_message = fields.Text(string='Error Message')
    
    @api.onchange('is_client_project')
    def _onchange_is_client_project(self):
        """Generate API token when project is marked as client project."""
        if self.is_client_project and not self.api_token:
            self.api_token = self._generate_api_token()
            self.client_key = self._generate_client_key()
        elif not self.is_client_project:
            self.api_token = False
            self.client_key = False
    
    def _generate_api_token(self):
        """Generate a secure API token."""
        return secrets.token_urlsafe(32)
    
    def _generate_client_key(self):
        """Generate a unique client key."""
        return f"{self.id or 'new'}-{secrets.token_urlsafe(8)}"
    
    def action_generate_api_token(self):
        """Manually generate or regenerate API token."""
        for record in self:
            if not record.is_client_project:
                raise UserError(_("Only client projects can have API tokens."))
            record.api_token = record._generate_api_token()
            record.client_key = record._generate_client_key()
        return True
    
    def action_revoke_api_token(self):
        """Revoke the API token."""
        for record in self:
            record.api_token = False
            record.client_key = False
            record.sync_instance_id = False
        return True
    
    def action_configure_sync(self):
        """Open the sync configuration wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configure Sync'),
            'res_model': 'sync.project.config.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
            }
        }
    
    def action_test_connection(self):
        """Test the connection to the remote instance."""
        self.ensure_one()
        if not self.sync_instance_id:
            raise UserError(_("Please configure a sync instance first."))
            
        try:
            self.sync_instance_id.test_connection()
            self.state = 'connected'
            self.error_message = False
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Test'),
                'message': _('Connection test completed.'),
                'type': 'success' if self.state == 'connected' else 'danger',
            }
        }
