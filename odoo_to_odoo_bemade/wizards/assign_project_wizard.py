# -*- coding: utf-8 -*-

import uuid
import random
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class OdooToBemadeAssignProjectWizard(models.TransientModel):
    _name = 'odoo.to.bemade.assign.project.wizard'
    _description = 'Assign Project to Bemade Client'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    client_instance_id = fields.Many2one('odoo.to.bemade.instance', string='Client Instance', required=True)
    project_key = fields.Char(string='Project Key', readonly=True)
    client_api_token = fields.Char(string='Client API Token', readonly=True)
    sync_project_task = fields.Boolean(string='Sync Tasks', default=True)
    sync_project_timesheet = fields.Boolean(string='Sync Timesheets', default=True)
    protocol = fields.Selection([
        ('xmlrpc', 'XML-RPC'),
        ('jsonrpc', 'JSON-RPC'),
        ('odoorpc', 'OdooRPC')
    ], string='Protocol', default='jsonrpc', required=True)

    @api.model
    def default_get(self, fields_list):
        """Prefill defaults from system parameters and context.

        - project_id from context (default_project_id)
        - protocol from bemade.sync.default_connection_type
        - client_instance_id from existing instance matching URL/DB/username
        """
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()

        # Context default project
        if 'project_id' in fields_list and self.env.context.get('default_project_id'):
            res['project_id'] = self.env.context['default_project_id']

        # Protocol default
        proto = ICP.get_param('bemade.sync.default_connection_type') or 'jsonrpc'
        if 'protocol' in fields_list and proto:
            res.setdefault('protocol', proto)

        # Try to preselect an instance based on defaults
        url = ICP.get_param('bemade.sync.default_url')
        database = ICP.get_param('bemade.sync.default_database')
        username = ICP.get_param('bemade.sync.default_username')

        domain = []
        if url:
            domain.append(('url', '=', url))
        if database:
            domain.append(('database', '=', database))
        if username:
            domain.append(('username', '=', username))

        if 'client_instance_id' in fields_list and domain:
            instance = self.env['odoo.to.bemade.instance'].search(domain, limit=1)
            if instance:
                res.setdefault('client_instance_id', instance.id)

        return res

    @api.onchange('project_id', 'client_instance_id')
    def _onchange_generate_keys(self):
        """Generate unique project key and API token"""
        if self.project_id and self.client_instance_id:
            # Generate random 8-character project key
            chars = string.ascii_uppercase + string.digits
            self.project_key = ''.join(random.choice(chars) for _ in range(8))
            
            # Generate UUID for API token
            self.client_api_token = str(uuid.uuid4())

    def action_assign_project(self):
        """Assign project to client and create sync configuration"""
        self.ensure_one()
        
        if not self.project_id:
            raise UserError(_("Please select a project to assign"))
        
        if not self.client_instance_id:
            raise UserError(_("Please select a client instance"))
            
        if not self.project_key or not self.client_api_token:
            self._onchange_generate_keys()
            
        # Create sync project
        sync_project_vals = {
            'name': f"{self.project_id.name} - {self.client_instance_id.name}",
            'project_id': self.project_id.id,
            'client_instance_id': self.client_instance_id.id,
            'state': 'draft',
            'is_client_project': True,
            'client_key': self.project_key,
            'client_api_token': self.client_api_token,
            'remote_url': self.client_instance_id.url,
            'remote_database': self.client_instance_id.database,
            'remote_username': self.client_instance_id.username,
            'remote_api_key': self.client_instance_id.api_key,
            'protocol': self.protocol,
        }
        
        sync_project = self.env['sync.project'].create(sync_project_vals)
        
        # Update project with bemade flags
        self.project_id.write({
            'is_bemade_project': True,
            'bemade_sync_enabled': True,
            'bemade_project_key': self.project_key,
        })
        
        # Create sync models for project and tasks
        self._create_sync_model(sync_project, 'project.project')
        
        if self.sync_project_task:
            self._create_sync_model(sync_project, 'project.task')
            
        if self.sync_project_timesheet and hasattr(self.env, 'account.analytic.line'):
            self._create_sync_model(sync_project, 'account.analytic.line')
            
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Project Assigned'),
                'message': _(f'Project {self.project_id.name} has been assigned to {self.client_instance_id.name} with key {self.project_key}'),
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Sync Project'),
                    'res_model': 'sync.project',
                    'res_id': sync_project.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        }
        
    def _create_sync_model(self, sync_project, model_name):
        """Create sync model configuration for the given model"""
        model_vals = {
            'name': f"{model_name} - {sync_project.name}",
            'sync_project_id': sync_project.id,
            'model_name': model_name,
            'direction': 'bidirectional',
            'state': 'draft',
        }
        
        sync_model = self.env['sync.model'].create(model_vals)
        
        # Auto-populate fields based on model
        if hasattr(sync_model, 'action_auto_sync_fields'):
            sync_model.action_auto_sync_fields()
            
        return sync_model
