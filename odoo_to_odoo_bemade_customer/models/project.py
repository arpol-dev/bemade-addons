# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_bemade_project = fields.Boolean(string='Bemade Project', default=False)
    bemade_project_key = fields.Char(string='Bemade Project Key', readonly=True)
    bemade_sync_enabled = fields.Boolean(string='Bemade Sync Enabled', default=False)

    def action_receive_bemade_project(self):
        """Action to receive project from Bemade server"""
        self.ensure_one()
        return {
            'name': _('Receive Bemade Project'),
            'type': 'ir.actions.act_window',
            'res_model': 'odoo.to.bemade.customer.receive.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
            }
        }

    def _sync_from_bemade(self, bemade_data):
        """Sync project data from Bemade server"""
        self.ensure_one()
        try:
            # Update project with received data
            self.write({
                'name': bemade_data.get('name', self.name),
                'description': bemade_data.get('description', self.description),
                'is_bemade_project': True,
                'bemade_project_key': bemade_data.get('project_key'),
                'bemade_sync_enabled': True,
            })
            
            # Sync tasks if provided
            if bemade_data.get('tasks'):
                self._sync_bemade_tasks(bemade_data['tasks'])
                
            return True
        except Exception as e:
            _logger.error("Error syncing from Bemade: %s", e)
            return False

    def _sync_bemade_tasks(self, tasks_data):
        """Sync tasks from Bemade server"""
        task_obj = self.env['project.task']
        for task_data in tasks_data:
            existing_task = task_obj.search([
                ('project_id', '=', self.id),
                ('bemade_task_key', '=', task_data.get('task_key'))
            ], limit=1)
            
            task_vals = {
                'name': task_data.get('name'),
                'description': task_data.get('description'),
                'project_id': self.id,
                'bemade_task_key': task_data.get('task_key'),
                'is_bemade_task': True,
            }
            
            if existing_task:
                existing_task.write(task_vals)
            else:
                task_obj.create(task_vals)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_bemade_task = fields.Boolean(string='Bemade Task', default=False)
    bemade_task_key = fields.Char(string='Bemade Task Key', readonly=True)
    bemade_sync_enabled = fields.Boolean(string='Bemade Sync Enabled', default=False)
