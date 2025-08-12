from odoo import models, fields, api

class OdooSyncModelField(models.Model):
    _name = 'odoo.sync.model.field'
    _description = 'Synchronized Field'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order the field mappings'
    )
    
    model_sync_id = fields.Many2one(
        comodel_name='odoo.sync.model', 
        string='Synchronized Model',
        required=True, 
        ondelete='cascade'
    )
    
    field_id = fields.Many2one(
        comodel_name='ir.model.fields', 
        string='Field',
        domain="[('model_id', '=', parent.model_id)]",
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        related='field_id.name', 
        string='Technical Name', 
        store=True
    )

    source_field = fields.Char(
        string='Source Field',
        help='Field name in the source model'
    )
    
    target_field = fields.Char(
        string='Target Field',
        help='Field name in the target model'
    )
    
    transform_type = fields.Selection([
        ('direct', 'Direct'),
        ('function', 'Function'),
        ('relation', 'Relation')
    ], string='Transform Type', default='direct',
       help='How to transform the field value during synchronization')
    
    is_identifier = fields.Boolean(
        string='Is Identifier',
        default=False,
        help='Whether this field is used to identify records'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )

    required = fields.Boolean(
        string='Required', 
        default=False
    )

    sync_default = fields.Char(
        string='Default Value',
        help='Value to use if not available'
    )
    
    conflict_strategy = fields.Selection([
        ('source_wins', 'Source gagne'),
        ('dest_wins', 'Destination gagne'),
        ('newest', 'Plus récent'),
        ('manual', 'Résolution manuelle')
    ], default='newest', string='Stratégie de conflit',
       help='Stratégie à utiliser pour résoudre les conflits de synchronisation sur ce champ')

    _sql_constraints = [
        ('field_uniq', 'unique(model_sync_id, field_id)', 
         'Un champ ne peut être synchronisé qu\'une fois par modèle!')
    ]
