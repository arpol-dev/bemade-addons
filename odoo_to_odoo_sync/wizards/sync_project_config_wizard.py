# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

from odoo import api, fields, models, _

class SyncProjectConfigWizard(models.TransientModel):
    _name = 'sync.project.config.wizard'
    _description = 'Sync Project Configuration Wizard'

    name = fields.Char(string='Instance Name', required=True)
    url = fields.Char(string='Server URL', required=True)
    database = fields.Char(string='Database', required=True)
    username = fields.Char(string='Username', required=True)
    api_token = fields.Char(string='API Token', required=True)
    protocol = fields.Selection([
        ('xmlrpc', 'XML-RPC'),
        ('jsonrpc', 'JSON-RPC'),
        ('odoorpc', 'OdooRPC'),
    ], string='Protocol', default='odoorpc', required=True)
    
    project_id = fields.Many2one('sync.project', string='Project')
    
    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            project = self.env['sync.project'].browse(active_id)
            if project.exists():
                defaults['project_id'] = project.id
                defaults['name'] = f"{project.name} - Sync Instance"
        return defaults
    
    def action_configure_sync(self):
        """Configure the sync instance and project."""
        self.ensure_one()
        
        # Create or update sync instance
        instance = self.env['sync.instance'].create({
            'name': self.name,
            'url': self.url,
            'database': self.database,
            'username': self.username,
            'api_key': self.api_token,
            'protocol': self.protocol,
        })
        
        # Update project with sync instance
        if self.project_id:
            self.project_id.sync_instance_id = instance.id
            self.project_id.remote_url = self.url
            self.project_id.remote_database = self.database
            self.project_id.remote_username = self.username
            self.project_id.state = 'configured'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Sync configuration completed successfully.'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
