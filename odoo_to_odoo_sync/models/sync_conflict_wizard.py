# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Conflict Resolution Wizard.

This module provides a wizard interface for manually resolving
synchronization conflicts between Odoo instances.
"""

import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooSyncConflictWizard(models.TransientModel):
    """Wizard for manual conflict resolution.
    
    This wizard allows users to manually resolve conflicts by:
    1. Viewing differences between local and remote data
    2. Selecting which fields to keep from each version
    3. Creating a custom merged resolution
    """
    _name = 'odoo.sync.conflict.wizard'
    _description = 'Conflict Resolution Wizard'

    conflict_id = fields.Many2one(
        comodel_name='odoo.sync.conflict',
        string='Conflit',
        required=True
    )
    
    # Related fields from conflict
    model_name = fields.Char(
        related='conflict_id.model_name',
        string='Modèle',
        readonly=True
    )
    
    record_id = fields.Integer(
        related='conflict_id.record_id',
        string='ID Enregistrement',
        readonly=True
    )
    
    record_name = fields.Char(
        related='conflict_id.name',
        string='Nom',
        readonly=True
    )
    
    diff_html = fields.Html(
        related='conflict_id.diff_html',
        string='Différences',
        readonly=True,
        sanitize=False
    )
    
    resolution_fields = fields.One2many(
        comodel_name='odoo.sync.conflict.wizard.field',
        inverse_name='wizard_id',
        string='Champs à résoudre'
    )
    
    # Custom resolution data
    custom_data = fields.Text(
        string='Données personnalisées'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Initialize the wizard with conflict data."""
        res = super(OdooSyncConflictWizard, self).default_get(fields_list)
        
        if 'conflict_id' in res:
            conflict = self.env['odoo.sync.conflict'].browse(res['conflict_id'])
            
            try:
                # Parse JSON data
                local_data = json.loads(conflict.local_data)
                remote_data = json.loads(conflict.remote_data)
                
                # Find differing fields
                differing_fields = []
                
                # Compare all fields in both datasets
                all_fields = set(list(local_data.keys()) + list(remote_data.keys()))
                
                # Extract write dates if available
                local_write_date = None
                remote_write_date = None
                
                if '__write_date' in dlocal_data:
                    try:
                        local_write_date = fields.Datetime.from_string(local_data['__write_date'])
                    except Exception:
                        _logger.warning('Invalid local write date format')
                
                if '__write_date' in remote_data:
                    try:
                        remote_write_date = fields.Datetime.from_string(remote_data['__write_date'])
                    except Exception:
                        _logger.warning('Invalid remote write date format')
                
                # Extract field-specific write dates if available
                field_write_dates = {}
                if '__field_write_dates' in local_data and isinstance(local_data['__field_write_dates'], dict):
                    field_write_dates['local'] = local_data['__field_write_dates']
                else:
                    field_write_dates['local'] = {}
                
                if '__field_write_dates' in remote_data and isinstance(remote_data['__field_write_dates'], dict):
                    field_write_dates['remote'] = remote_data['__field_write_dates']
                else:
                    field_write_dates['remote'] = {}
                
                for field_name in all_fields:
                    # Skip system fields
                    if field_name.startswith('__') or field_name in ('id', 'write_date', 'create_date'):
                        continue
                    
                    local_value = local_data.get(field_name)
                    remote_value = remote_data.get(field_name)
                    
                    # Get field-specific write dates if available
                    field_local_write_date = None
                    field_remote_write_date = None
                    
                    if field_name in field_write_dates['local']:
                        try:
                            field_local_write_date = fields.Datetime.from_string(
                                field_write_dates['local'][field_name]
                            )
                        except Exception:
                            field_local_write_date = local_write_date
                    else:
                        field_local_write_date = local_write_date
                    
                    if field_name in field_write_dates['remote']:
                        try:
                            field_remote_write_date = fields.Datetime.from_string(
                                field_write_dates['remote'][field_name]
                            )
                        except Exception:
                            field_remote_write_date = remote_write_date
                    else:
                        field_remote_write_date = remote_write_date
                    
                    # Check if values differ
                    if local_value != remote_value:
                        # Determine default source based on timestamps if available
                        source = 'local'  # Default to local
                        
                        if field_local_write_date and field_remote_write_date:
                            if field_remote_write_date > field_local_write_date:
                                source = 'remote'
                        
                        differing_fields.append({
                            'field_name': field_name,
                            'local_value': str(local_value) if local_value is not None else '',
                            'remote_value': str(remote_value) if remote_value is not None else '',
                            'source': source,
                            'local_write_date': field_local_write_date,
                            'remote_write_date': field_remote_write_date
                        })
                
                res['resolution_fields'] = [(0, 0, vals) for vals in differing_fields]
                
            except Exception as e:
                _logger.error('Error initializing conflict resolution: %s', str(e))
        
        return res
    
    def action_select_all_local(self):
        """Set all fields to use local values."""
        self.ensure_one()
        self.resolution_fields.write({'source': 'local'})
        return {'type': 'ir.actions.do_nothing'}
    
    def action_select_all_remote(self):
        """Set all fields to use remote values."""
        self.ensure_one()
        self.resolution_fields.write({'source': 'remote'})
        return {'type': 'ir.actions.do_nothing'}
    
    def action_select_newest(self):
        """Set each field to use the newest value based on write_date."""
        self.ensure_one()
        
        for field in self.resolution_fields:
            if field.local_write_date and field.remote_write_date:
                if field.local_write_date >= field.remote_write_date:
                    field.source = 'local'
                else:
                    field.source = 'remote'
            elif field.local_write_date:
                field.source = 'local'
            elif field.remote_write_date:
                field.source = 'remote'
            # If neither has a timestamp, keep the current selection
        
        return {'type': 'ir.actions.do_nothing'}
    
    def action_reset_selections(self):
        """Reset all field selections to default."""
        self.ensure_one()
        self.resolution_fields.write({'source': 'local', 'custom_value': False})
        return {'type': 'ir.actions.do_nothing'}
    
    def action_apply_resolution(self):
        """Apply the custom resolution."""
        self.ensure_one()
        
        try:
            # Get original data
            local_data = json.loads(self.conflict_id.local_data)
            remote_data = json.loads(self.conflict_id.remote_data)
            
            # Create merged data based on field selections
            merged_data = {}
            
            # Start with all fields from local data
            merged_data.update(local_data)
            
            # Override with selected remote fields or custom values
            for field in self.resolution_fields:
                if field.source == 'remote' and field.field_name in remote_data:
                    merged_data[field.field_name] = remote_data[field.field_name]
                elif field.source == 'custom':
                    merged_data[field.field_name] = field.custom_value
                elif field.source == 'ignore':
                    # Remove field from merged data if it should be ignored
                    if field.field_name in merged_data:
                        del merged_data[field.field_name]
            
            # Update the conflict with the resolution
            self.conflict_id.write({
                'resolution': 'custom',
                'custom_data': json.dumps(merged_data),
                'state': 'resolved',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now()
            })
            
            # Apply the resolution
            return self.conflict_id._apply_resolution()
            
        except Exception as e:
            _logger.error('Error applying custom resolution: %s', str(e))
            raise UserError(f'Erreur lors de l\'application de la résolution personnalisée: {str(e)}')

