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
    
    mapping_type = fields.Selection([
        ('direct', 'Direct'),
        ('function', 'Function'),
        ('computed', 'Computed'),
        ('relation', 'Relation')
    ], string='Mapping Type', default='direct',
       help='Type of field mapping for synchronization')

    mapping_function = fields.Char(
        string='Mapping Function',
        help='Python function name to transform the field value. Use format: model.method_name or method_name'
    )
    
    mapping_expression = fields.Text(
        string='Mapping Expression',
        help='Python expression for computed field mapping. Use record.field_name syntax'
    )
    
    relation_model = fields.Char(
        string='Relation Model',
        help='Target model for relation mapping (e.g., res.partner, product.category)'
    )
    
    relation_field = fields.Char(
        string='Relation Field',
        help='Field to match in the relation model (e.g., name, code)'
    )
    
    relation_domain = fields.Text(
        string='Relation Domain',
        help='Domain filter for relation mapping as JSON list of tuples'
    )
    
    transform_function = fields.Char(
        string='Transform Function',
        help='Function to transform field value (deprecated, use mapping_function instead)'
    )
    
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
