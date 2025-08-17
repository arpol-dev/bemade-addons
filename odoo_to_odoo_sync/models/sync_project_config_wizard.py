# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SyncProjectConfigWizard(models.TransientModel):
    _name = 'sync.project.config.wizard'
    _description = 'Sync Project Configuration Wizard'

    name = fields.Char(string='Configuration Name', required=True)
    remote_url = fields.Char(string='Remote URL', required=True)
    remote_database = fields.Char(string='Remote Database', required=True)
    remote_username = fields.Char(string='Username', required=True)
    remote_api_key = fields.Char(string='API Key', required=True)
    protocol = fields.Selection([
        ('xmlrpc', 'XML-RPC'),
        ('jsonrpc', 'JSON-RPC'),
        ('odoorpc', 'OdooRPC')
    ], string='Protocol', default='jsonrpc', required=True)
    
    def action_configure_project(self):
        """Configure the sync project with provided settings"""
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}
