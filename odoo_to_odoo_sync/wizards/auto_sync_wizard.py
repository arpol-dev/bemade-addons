# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AutoSyncWizard(models.TransientModel):
    """Wizard for selecting auto-sync field modes."""
    
    _name = 'odoo.sync.auto.sync.wizard'
    _description = 'Auto Sync Fields Configuration'
    
    sync_model_id = fields.Many2one(
        comodel_name='odoo.sync.model',
        string='Sync Model',
        required=True,
        ondelete='cascade'
    )
    
    mode = fields.Selection([
        ('full', 'Full'),
        ('required', 'Required'),
    ], string='Field Selection Mode', default='full', required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context."""
        res = super(AutoSyncWizard, self).default_get(fields_list)
        if self.env.context.get('active_id'):
            res['sync_model_id'] = self.env.context['active_id']
        return res
    
    def action_auto_sync_fields(self):
        """Execute auto-sync based on selected mode."""
        self.ensure_one()
        
        if not self.sync_model_id.model_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Error adding fields',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        try:
            sync_model = self.sync_model_id
            model_fields = self.env['ir.model.fields'].search([
                ('model_id', '=', sync_model.model_id.id),
                ('store', '=', True),
                ('name', 'not in', ['id', '__last_update']),
            ])
            
            existing_fields = sync_model.field_ids.mapped('field_id.name')
            fields_added = 0
            
            # Define field sets based on mode
            if self.mode == 'full':
                # Include ALL usable fields
                fields_to_add = model_fields
                
            elif self.mode == 'required':
                # Only REQUIRED fields
                fields_to_add = model_fields.filtered(lambda f: f.required)
            
            # Process fields
            exclude_fields = [
                'create_date', 'write_date', 'create_uid', 'write_uid',
                '__last_update', 'id'
            ]
            
            for field in fields_to_add:
                if field.name in exclude_fields or field.name in existing_fields:
                    continue
                    
                # Skip binary fields to avoid sync issues
                if field.ttype in ['binary', 'many2many']:
                    continue
                
                is_required = field.required or field.name in ['active', 'name']
                
                sequence = 10 if not field.required else 5
                self.env['odoo.sync.model.field'].create({
                    'model_sync_id': sync_model.id,
                    'field_id': field.id,
                    'required': field.required,
                    'sequence': sequence,
                    'mapping_type': 'direct',
                })
                fields_added += 1
            
            # Always ensure basic audit fields
            basic_fields = ['create_date', 'write_date', 'create_uid', 'write_uid']
            for field_name in basic_fields:
                field = self.env['ir.model.fields'].search([
                    ('model_id', '=', sync_model.model_id.id),
                    ('name', '=', field_name)
                ])
                if field and field.name not in existing_fields:
                    self.env['odoo.sync.model.field'].create({
                        'model_sync_id': sync_model.id,
                        'field_id': field.id,
                        'required': True,
                        'sequence': 1,
                        'mapping_type': 'direct',
                    })
                    fields_added += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': '%d fields added successfully' % fields_added,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
