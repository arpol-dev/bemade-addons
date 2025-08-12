# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Synchronization Configuration for Bemade.

This module extends the base model synchronization configuration to add
Bemade-specific functionality for defining how models are synchronized
between Odoo instances.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncModel(models.Model):
    """Bemade synchronization model configuration.

    Extends the base synchronization model configuration to handle
    Bemade-specific requirements for model synchronization.
    """

    _name = 'odoo.to.bemade.sync.model'
    _description = 'Bemade Synchronized Model'
    _inherits = {'odoo.sync.model': 'sync_model_id'}
    
    # Field to store the parent record ID
    sync_model_id = fields.Many2one(
        'odoo.sync.model', 
        required=True, 
        ondelete='cascade', 
        auto_join=True
    )
    
    # Note: This model inherits fields and methods from odoo.sync.model
    # The following fields are inherited and available:
    # - model_id: Many2one to ir.model
    # - name: related field to model_id.model
    # - target_model: Char field for target model name
    # - instance_id: Many2one to odoo.sync.instance
    # - field_ids: One2many to odoo.sync.model.field
    # - active: Boolean field
    # 
    # The following methods are inherited:
    # - generate_field_mappings: Creates field mappings for the model
    
    # Add Bemade-specific fields here
    bemade_specific_setting = fields.Boolean(
        string='Bemade Specific Setting',
        default=False,
        help='Enable this for Bemade-specific synchronization behavior',
    )

    bemade_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.instance',
        string='Bemade Instance',
        required=True,
        help='The Bemade instance this model will be synchronized with',
    )
    
    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Project',
        help='The project this synchronization model is associated with',
    )
    
    @api.onchange('instance_id')
    def _onchange_instance_id(self):
        """Set bemade_instance_id when instance_id changes."""
        if self.instance_id:
            # Try to find a matching bemade instance
            bemade_instance = self.env['odoo.to.bemade.instance'].search(
                [('id', '=', self.instance_id.id)], limit=1)
            if bemade_instance:
                self.bemade_instance_id = bemade_instance.id
                
    @api.model
    def create(self, vals_list):
        """Override create to handle delegation inheritance properly and ensure bemade_instance_id is set.
        
        When creating a record through the form view, we need to:
        1. Check if a parent record already exists for the model_id and instance_id
        2. If it exists, link to it via sync_model_id
        3. If not, create the parent record first
        
        This prevents duplicate key violations on the unique constraint.
        """
        # Handle both single dict and list of dicts
        if isinstance(vals_list, dict):
            vals_items = [vals_list]
        else:
            vals_items = vals_list
            
        result = self.env['odoo.to.bemade.sync.model']
            
        for vals in vals_items:
            # If sync_model_id is already provided, use standard creation
            if not vals.get('sync_model_id') and vals.get('model_id') and vals.get('instance_id'):
                # Check for existing parent record
                existing_parent = self.env['odoo.sync.model'].search([
                    ('model_id', '=', vals['model_id']),
                    ('instance_id', '=', vals['instance_id'])
                ], limit=1)
                
                if existing_parent:
                    # Link to existing parent
                    vals['sync_model_id'] = existing_parent.id
                else:
                    # Create parent record first
                    parent_vals = {
                        'model_id': vals['model_id'],
                        'instance_id': vals['instance_id'],
                        'target_model': vals.get('target_model'),
                        'active': vals.get('active', True),
                    }
                    parent_record = self.env['odoo.sync.model'].create(parent_vals)
                    vals['sync_model_id'] = parent_record.id
            
            # If instance_id is set but bemade_instance_id is not, set it
            if vals.get('instance_id') and not vals.get('bemade_instance_id'):
                vals['bemade_instance_id'] = vals['instance_id']
        
        return super(OdooToBemadeSyncModel, self).create(vals_list)
    
    @api.model
    def create_sync_configuration(self, model_name, instance_id, target_model=None, active=True):
        """Create a synchronization configuration for a model.
        
        This method creates both the parent sync model record and the Bemade-specific
        sync model record with proper linkage between them. If a sync model already exists
        for the given model_id and instance_id, it will be reused instead of creating a new one.
        
        Args:
            model_name: Technical name of the model to synchronize
            instance_id: ID of the remote client instance to sync with
            target_model: Technical name of the model on the remote instance
            active: Whether the synchronization is active
            
        Returns:
            The created or existing model configuration record
        """
        ir_model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not ir_model:
            raise UserError(_('Model %s does not exist') % model_name)
            
        # Find the Bemade instance (provider)
        company_id = self.env.company.id
        bemade_instance = self.env['odoo.to.bemade.instance'].search([('company_id', '=', company_id)], limit=1)
        if not bemade_instance:
            bemade_instance = self.env['odoo.to.bemade.instance'].search([], limit=1)
        if not bemade_instance:
            raise UserError(_('No Bemade instance found. Please create one first.'))
            
        # Check if a parent sync model record already exists for this model and instance
        existing_parent = self.env['odoo.sync.model'].search([
            ('model_id', '=', ir_model.id),
            ('instance_id', '=', instance_id)
        ], limit=1)
        
        if existing_parent:
            # Check if there's already a Bemade sync model linked to this parent
            existing_bemade_sync = self.search([('sync_model_id', '=', existing_parent.id)], limit=1)
            if existing_bemade_sync:
                # Update the existing record if needed
                if existing_bemade_sync.bemade_instance_id.id != bemade_instance.id or existing_bemade_sync.active != active:
                    existing_bemade_sync.write({
                        'bemade_instance_id': bemade_instance.id,
                        'active': active
                    })
                return existing_bemade_sync
            else:
                # Create a new Bemade sync model linked to the existing parent
                return self.create({
                    'sync_model_id': existing_parent.id,
                    'bemade_instance_id': bemade_instance.id,
                    'active': active,
                })
        else:
            # Create the parent sync model record
            parent_record = self.env['odoo.sync.model'].create({
                'model_id': ir_model.id,
                'instance_id': instance_id,
                'target_model': target_model or model_name,
                'active': active,
            })
            
            # Create the Bemade sync model record linked to the parent
            return self.create({
                'sync_model_id': parent_record.id,  # Link to parent record
                'bemade_instance_id': bemade_instance.id,
                'active': active,
            })
        
    def generate_field_mappings(self):
        """Generate field mappings based on model fields.
        
        This method creates sync.model.field records for all the fields
        in the model that should be synchronized.
        
        Returns:
            List of created field mapping records
        """
        self.ensure_one()
        
        # Make sure the record is saved in the database before creating field mappings
        # Use the Odoo API to ensure the record is saved
        self.env.cr.commit()
        
        # Get the model from model_id relation (accessed through the parent record)
        model = self.env[self.sync_model_id.model_id.model]
        model_fields = model._fields
        
        # Create field mappings for each relevant field
        field_mapping_model = self.env['odoo.sync.model.field']
        created_mappings = []
        
        # Verify that the parent record exists in the database
        if not self.sync_model_id.exists():
            raise UserError(_("Cannot create field mappings: parent sync model record not found. Please save the record first."))
        
        for field_name, field in model_fields.items():
            # Skip fields that shouldn't be synchronized
            if field.type in ['one2many', 'many2many']:
                continue
                
            if field_name in ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']:
                continue
                
            # Create a field mapping
            mapping_vals = {
                'model_sync_id': self.sync_model_id.id,  # Use the parent record ID
                'source_field': field_name,
                'target_field': field_name,
                'active': True,
                'transform_type': 'direct',
            }
            
            try:
                # Create the mapping
                mapping = field_mapping_model.create(mapping_vals)
                created_mappings.append(mapping)
            except Exception as e:
                _logger.error("Error creating field mapping for %s: %s", field_name, str(e))
                continue
            
        return created_mappings
        

    
    def create_all_fields(self):
        """Create field mappings for all fields in the model.
        
        This method is called from the view button to automatically
        generate field mappings for all fields in the model.
        
        Returns:
            dict: Action dictionary for refreshing the view
        """
        self.ensure_one()
        
        # Ensure the parent record exists and is properly linked
        if not self.sync_model_id or not self.sync_model_id.exists():
            raise UserError(_("Cannot create field mappings: parent sync model record not found. Please save the record first."))
            
        # Generate field mappings
        self.generate_field_mappings()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
        
    def sync_all_records(self):
        """Synchronize all records of this model.
        
        This method is called from the view button to trigger
        synchronization for all records of this model.
        
        Returns:
            dict: Action dictionary for displaying a success message
        """
        self.ensure_one()
        
        # Get the sync manager
        sync_manager = self.env['odoo.sync.manager']
        
        # Get all records of this model
        # The 'name' field is inherited from odoo.sync.model and is a related field to model_id.model
        # It contains the technical name of the model (e.g. 'res.partner')
        # pylint: disable=no-member
        model = self.env[self.name]
        records = model.search([])
        
        # Queue synchronization for each record
        for record in records:
            sync_manager._queue_sync(record, 'create')
        
        # Return action to show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Synchronisation démarrée",
                'message': f"{len(records)} enregistrements ont été mis en file d'attente pour synchronisation.",
                'type': 'success',
                'sticky': False,
            }
        }
