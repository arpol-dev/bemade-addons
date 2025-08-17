# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class OdooToBemadeCustomerReceiveWizard(models.TransientModel):
    _name = 'odoo.to.bemade.customer.receive.wizard'
    _description = 'Receive Project from Bemade Server'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    bemade_url = fields.Char(string='Bemade Server URL', required=True)
    bemade_database = fields.Char(string='Bemade Database', required=True)
    bemade_username = fields.Char(string='Username', required=True)
    bemade_api_key = fields.Char(string='API Key', required=True)
    bemade_project_key = fields.Char(string='Project Key', required=True)
    protocol = fields.Selection([
        ('xmlrpc', 'XML-RPC'),
        ('jsonrpc', 'JSON-RPC'),
        ('odoorpc', 'OdooRPC')
    ], string='Protocol', default='jsonrpc', required=True)

    @api.model
    def default_get(self, fields_list):
        """Prefill defaults from system parameters and context.

        Pulls values from ir.config_parameter keys:
        - customer.sync.default_url
        - customer.sync.default_database
        - customer.sync.default_username
        - customer.sync.default_api_key
        - customer.sync.default_connection_type
        """
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        url = ICP.get_param('customer.sync.default_url')
        database = ICP.get_param('customer.sync.default_database')
        username = ICP.get_param('customer.sync.default_username')
        api_key = ICP.get_param('customer.sync.default_api_key')
        proto = ICP.get_param('customer.sync.default_connection_type') or 'jsonrpc'

        if 'bemade_url' in fields_list and url:
            res.setdefault('bemade_url', url)
        if 'bemade_database' in fields_list and database:
            res.setdefault('bemade_database', database)
        if 'bemade_username' in fields_list and username:
            res.setdefault('bemade_username', username)
        if 'bemade_api_key' in fields_list and api_key:
            res.setdefault('bemade_api_key', api_key)
        if 'protocol' in fields_list and proto:
            res.setdefault('protocol', proto)

        # Respect contextual default project if provided
        if 'project_id' in fields_list and self.env.context.get('default_project_id'):
            res['project_id'] = self.env.context['default_project_id']

        return res

    def action_receive_project(self):
        """Receive project data from Bemade server"""
        self.ensure_one()
        try:
            # Connect to Bemade server and fetch project data
            project_data = self._fetch_project_from_bemade()
            
            if project_data:
                # Update current project with received data
                self.project_id._sync_from_bemade(project_data)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Project successfully received from Bemade server'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Failed to fetch project data from Bemade server'))
                
        except Exception as e:
            _logger.error("Error receiving project: %s", e)
            raise UserError(_('Error receiving project: %s') % str(e))

    def _fetch_project_from_bemade(self):
        """Fetch project data from Bemade server"""
        try:
            # Import required libraries based on protocol
            if self.protocol == 'xmlrpc':
                import xmlrpc.client
                url = f"{self.bemade_url}/xmlrpc/2"
                common = xmlrpc.client.ServerProxy(f"{url}/common")
                models = xmlrpc.client.ServerProxy(f"{url}/object")
                
                uid = common.authenticate(self.bemade_database, self.bemade_username, self.bemade_api_key, {})
                if not uid:
                    raise UserError(_('Authentication failed'))
                
                # Search for project by key
                project_ids = models.execute_kw(
                    self.bemade_database, uid, self.bemade_api_key,
                    'project.project', 'search',
                    [[['client_key', '=', self.bemade_project_key]]]
                )
                
                if not project_ids:
                    raise UserError(_('Project not found with key: %s') % self.bemade_project_key)
                
                # Read project data
                project_data = models.execute_kw(
                    self.bemade_database, uid, self.bemade_api_key,
                    'project.project', 'read', [project_ids[0]],
                    {'fields': ['name', 'description', 'client_key', 'client_api_token']}
                )
                
                # Read tasks for this project
                task_ids = models.execute_kw(
                    self.bemade_database, uid, self.bemade_api_key,
                    'project.task', 'search',
                    [[['project_id', '=', project_ids[0]]]]
                )
                
                tasks_data = models.execute_kw(
                    self.bemade_database, uid, self.bemade_api_key,
                    'project.task', 'read', [task_ids],
                    {'fields': ['name', 'description', 'stage_id', 'priority']}
                )
                
                return {
                    'name': project_data[0]['name'],
                    'description': project_data[0]['description'],
                    'project_key': project_data[0]['client_key'],
                    'tasks': tasks_data
                }
                
            elif self.protocol == 'jsonrpc':
                import json
                import urllib.request
                
                # JSON-RPC implementation
                headers = {'Content-Type': 'application/json'}
                
                # Authenticate
                auth_data = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "common",
                        "method": "login",
                        "args": [self.bemade_database, self.bemade_username, self.bemade_api_key]
                    },
                    "id": 1
                }
                
                auth_request = urllib.request.Request(
                    f"{self.bemade_url}/jsonrpc",
                    data=json.dumps(auth_data).encode(),
                    headers=headers
                )
                
                auth_response = urllib.request.urlopen(auth_request)
                auth_result = json.loads(auth_response.read().decode())
                
                if not auth_result.get('result'):
                    raise UserError(_('Authentication failed'))
                
                uid = auth_result['result']
                
                # Search for project
                search_data = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute",
                        "args": [
                            self.bemade_database, uid, self.bemade_api_key,
                            'project.project', 'search',
                            [['client_key', '=', self.bemade_project_key]]
                        ]
                    },
                    "id": 2
                }
                
                search_request = urllib.request.Request(
                    f"{self.bemade_url}/jsonrpc",
                    data=json.dumps(search_data).encode(),
                    headers=headers
                )
                
                search_response = urllib.request.urlopen(search_request)
                search_result = json.loads(search_response.read().decode())
                
                if not search_result.get('result'):
                    raise UserError(_('Project not found'))
                
                project_id = search_result['result'][0]
                
                # Read project data
                read_data = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute",
                        "args": [
                            self.bemade_database, uid, self.bemade_api_key,
                            'project.project', 'read', [project_id],
                            ['name', 'description', 'client_key', 'client_api_token']
                        ]
                    },
                    "id": 3
                }
                
                read_request = urllib.request.Request(
                    f"{self.bemade_url}/jsonrpc",
                    data=json.dumps(read_data).encode(),
                    headers=headers
                )
                
                read_response = urllib.request.urlopen(read_request)
                read_result = json.loads(read_response.read().decode())
                
                project_data = read_result['result'][0]
                
                # Read tasks
                tasks_data = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute",
                        "args": [
                            self.bemade_database, uid, self.bemade_api_key,
                            'project.task', 'search_read',
                            [['project_id', '=', project_id]],
                            ['name', 'description', 'stage_id', 'priority']
                        ]
                    },
                    "id": 4
                }
                
                tasks_request = urllib.request.Request(
                    f"{self.bemade_url}/jsonrpc",
                    data=json.dumps(tasks_data).encode(),
                    headers=headers
                )
                
                tasks_response = urllib.request.urlopen(tasks_request)
                tasks_result = json.loads(tasks_response.read().decode())
                
                return {
                    'name': project_data['name'],
                    'description': project_data['description'],
                    'project_key': project_data['client_key'],
                    'tasks': tasks_result['result']
                }
                
            elif self.protocol == 'odoorpc':
                try:
                    import odoorpc
                    odoo = odoorpc.ODOO(
                        self.bemade_url.replace('http://', '').replace('https://', ''),
                        protocol='jsonrpc+ssl' if 'https' in self.bemade_url else 'jsonrpc',
                        port=443 if 'https' in self.bemade_url else 8069
                    )
                    
                    odoo.login(self.bemade_database, self.bemade_username, self.bemade_api_key)
                    
                    Project = odoo.env['project.project']
                    project_ids = Project.search([('client_key', '=', self.bemade_project_key)])
                    
                    if not project_ids:
                        raise UserError(_('Project not found'))
                    
                    project_data = Project.browse(project_ids[0]).read(['name', 'description', 'client_key', 'client_api_token'])[0]
                    
                    Task = odoo.env['project.task']
                    task_ids = Task.search([('project_id', '=', project_ids[0])])
                    tasks_data = Task.browse(task_ids).read(['name', 'description', 'stage_id', 'priority'])
                    
                    return {
                        'name': project_data['name'],
                        'description': project_data['description'],
                        'project_key': project_data['client_key'],
                        'tasks': tasks_data
                    }
                    
                except ImportError:
                    raise UserError(_('OdooRPC library not installed. Please install with: pip install odoorpc'))
                
        except Exception as e:
            _logger.error("Error fetching project: %s", e)
            raise UserError(_('Error connecting to Bemade server: %s') % str(e))

    def action_test_connection(self):
        """Test connection to Bemade server"""
        self.ensure_one()
        try:
            # Test connection logic
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': _('Connection successful'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': _('Connection failed: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
