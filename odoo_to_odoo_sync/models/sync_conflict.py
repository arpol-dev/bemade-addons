# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Conflict Management.

This module implements the conflict detection and resolution system for
synchronization operations. It handles cases where changes on both source
and destination instances conflict and require manual resolution.
"""

import json
import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Dictionary of model-specific restricted fields that should not be written during conflict resolution
RESTRICTED_FIELDS = {
    'res.company': ['parent_id', 'child_ids'],  # Company hierarchy fields
}

class OdooSyncConflict(models.Model):
    """Manages synchronization conflicts between Odoo instances.
    
    This model stores conflicts that occur during synchronization and
    provides tools for manual resolution. Conflicts arise when both
    source and destination instances have changes that cannot be
    automatically reconciled.
    """
    _name = 'odoo.sync.conflict'
    _description = 'Synchronization Conflict'
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True
    )
    
    model_name = fields.Char(
        string='Model',
        required=True,
        help='Technical name of the model with conflict'
    )
    
    record_id = fields.Integer(
        string='Record ID',
        required=True,
        help='ID of the record with conflict'
    )
    
    local_data = fields.Text(
        string='Local Data',
        required=True,
        help='JSON representation of local data'
    )
    
    remote_data = fields.Text(
        string='Remote Data',
        required=True,
        help='JSON representation of remote data'
    )
    
    resolution = fields.Selection(
        selection=[
            ('local', 'Keep Local'),
            ('remote', 'Keep Remote'),
            ('merge', 'Merge'),
            ('custom', 'Custom')
        ],
        string='Resolution',
        help='How to resolve the conflict'
    )
    
    custom_data = fields.Text(
        string='Custom Data',
        help='JSON representation of custom resolution data'
    )
    
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('resolved', 'Resolved'),
            ('cancelled', 'Cancelled')
        ],
        default='pending',
        required=True,
        string='State'
    )
    
    resolved_by = fields.Many2one(
        comodel_name='res.users',
        string='Resolved By'
    )
    
    resolved_date = fields.Datetime(
        string='Resolved Date'
    )
    
    diff_html = fields.Html(
        string='Differences',
        compute='_compute_diff_html',
        sanitize=False,
        help='HTML representation of differences between local and remote data'
    )

    @api.depends('model_name', 'record_id')
    def _compute_name(self):
        """Compute the display name of the conflict.
        
        The name is generated using the format: 'Conflict - model_name#record_id'
        e.g., 'Conflict - res.partner#42'
        """
        for record in self:
            record.name = f'Conflict - {record.model_name}#{record.record_id}'

    @api.depends('local_data', 'remote_data')
    def _compute_diff_html(self):
        """Compute HTML representation of differences between local and remote data."""
        for record in self:
            try:
                local = json.loads(record.local_data)
                remote = json.loads(record.remote_data)
                
                # Generate HTML diff
                diff_html = '<table class="table table-bordered table-sm">'
                diff_html += '<thead><tr><th>Field</th><th>Local Value</th><th>Remote Value</th></tr></thead>'
                diff_html += '<tbody>'
                
                # Combine all keys from both dictionaries
                all_keys = set(local.keys()) | set(remote.keys())
                
                for key in sorted(all_keys):
                    local_val = local.get(key, '')
                    remote_val = remote.get(key, '')
                    
                    # Skip if values are identical
                    if local_val == remote_val:
                        continue
                    
                    # Add row with different styling for different values
                    diff_html += '<tr>'
                    diff_html += f'<td>{key}</td>'
                    
                    # Local value
                    if key in local:
                        diff_html += f'<td class="bg-light">{local_val}</td>'
                    else:
                        diff_html += '<td class="bg-warning">Missing</td>'
                    
                    # Remote value
                    if key in remote:
                        diff_html += f'<td class="bg-light">{remote_val}</td>'
                    else:
                        diff_html += '<td class="bg-warning">Missing</td>'
                    
                    diff_html += '</tr>'
                
                diff_html += '</tbody></table>'
                
                record.diff_html = diff_html
            except Exception as e:
                record.diff_html = f'<div class="alert alert-danger">Error computing diff: {str(e)}</div>'

    def action_resolve_local(self):
        """Resolve conflict by keeping local data."""
        self.ensure_one()
        self.write({
            'resolution': 'local',
            'state': 'resolved',
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now()
        })
        return self._apply_resolution()

    def action_resolve_remote(self):
        """Resolve conflict by keeping remote data."""
        self.ensure_one()
        self.write({
            'resolution': 'remote',
            'state': 'resolved',
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now()
        })
        return self._apply_resolution()

    def action_resolve_custom(self):
        """Open wizard for custom conflict resolution."""
        self.ensure_one()
        return {
            'name': 'Custom Conflict Resolution',
            'type': 'ir.actions.act_window',
            'res_model': 'odoo.sync.conflict.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_conflict_id': self.id}
        }

    def action_cancel(self):
        """Cancel the conflict resolution."""
        self.write({
            'state': 'cancelled',
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now()
        })

    def _apply_resolution(self):
        """Apply the selected resolution strategy."""
        self.ensure_one()
        
        if self.state != 'resolved':
            raise UserError('Cannot apply resolution for unresolved conflict')
        
        try:
            if self.resolution == 'local':
                data = json.loads(self.local_data)
            elif self.resolution == 'remote':
                data = json.loads(self.remote_data)
            elif self.resolution == 'custom':
                if not self.custom_data:
                    raise UserError('Custom resolution data is missing')
                data = json.loads(self.custom_data)
            else:
                raise UserError(f'Unsupported resolution strategy: {self.resolution}')
            
            # Get the model and record
            model = self.env[self.model_name]
            record = model.browse(self.record_id)
            
            # Apply the resolved data
            if not record.exists():
                raise UserError(f'Record {self.model_name}#{self.record_id} does not exist')
            
            # Remove special fields that shouldn't be written directly
            for field in ['id', 'create_date', 'write_date', 'create_uid', 'write_uid']:
                if field in data:
                    del data[field]
            
            # Handle model-specific field restrictions
            self._filter_restricted_fields(data)
            
            # If no fields left to write after filtering, return success
            if not data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'No fields to update after filtering restricted fields',
                        'type': 'success',
                    }
                }
            
            # Write the resolved data
            record.write(data)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Conflict resolution applied successfully',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error('Error applying conflict resolution: %s', str(e))
            raise UserError(f'Error applying resolution: {str(e)}')
    
    def _filter_restricted_fields(self, data):
        """Filter out restricted fields based on the model.
        
        Some models have fields that cannot be written directly due to business logic
        constraints. This method removes those fields from the data dictionary.
        
        Args:
            data: Dictionary of field values to be written
        """
        if self.model_name in RESTRICTED_FIELDS:
            for field in RESTRICTED_FIELDS[self.model_name]:
                if field in data:
                    _logger.debug(f'Removing restricted field {field} for model {self.model_name}')
                    del data[field]
