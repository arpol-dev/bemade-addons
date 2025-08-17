# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeInstance(models.Model):
    _name = 'odoo.to.bemade.instance'
    _description = 'Bemade Remote Odoo Instance'
    _inherit = ['odoo.to.bemade.instance', 'mail.thread', 'mail.activity.mixin']

    # Bemade-specific fields (do not duplicate base sync fields)
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        domain=[('is_client_project', '=', True)]
    )

    client_key = fields.Char(string='Client Key', readonly=True)
    bemade_api_token = fields.Char(string='Bemade API Token', readonly=True)

    is_client_instance = fields.Boolean(string='Is Client Instance', default=False)

    # Additional informational field not present in base model
    last_sync_date = fields.Datetime(string='Last Sync Date')

    def action_test_connection(self):
        """Delegate to the inherited test_connection and notify the user."""
        self.ensure_one()
        ok = False
        message = _('Connection test completed.')
        try:
            ok = bool(self.test_connection())
            message = _('Connection successful') if ok else _('Connection failed')
        except Exception as e:  # noqa: BLE001 - notify without breaking UI
            message = _('Connection failed: %s') % str(e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Test'),
                'message': message,
                'type': 'success' if ok else 'danger',
            }
        }

    def action_sync_project_data(self):
        """Sync project data with the client instance."""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_('Please test the connection first.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Project Data'),
            'res_model': 'odoo.sync.queue',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_instance_id': self.id,
                'default_project_id': self.project_id.id,
            }
        }
