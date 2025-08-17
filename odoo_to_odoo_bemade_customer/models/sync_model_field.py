# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Field Synchronization Configuration for Bemade clients.

This module defines how fields are synchronized between client instances
and the Bemade platform. It simplifies field mapping and transformations
for Bemade customers.
"""

import logging
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class OdooToBemadeCustomerSyncModelField(models.Model):
    """Champ de modèle synchronisé avec Bemade."""

    _name = 'odoo.to.bemade.customer.sync.model.field'
    _description = 'Champ de modèle synchronisé avec Bemade'
    _inherit = 'odoo.sync.model.field'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help='Ordre de traitement des champs lors de la synchronisation'
    )
    
    sync_model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle synchronisé',
        required=True,
        ondelete='cascade',
        help='Modèle auquel ce champ appartient',
    )
    
    field_name = fields.Char(
        string='Nom du champ',
        required=True,
        help='Nom technique du champ dans le modèle local (ex: name)'
    )
    
    bemade_field_name = fields.Char(
        string='Nom du champ Bemade',
        required=True,
        help='Nom technique du champ correspondant chez Bemade'
    )
    
    is_identifier = fields.Boolean(
        string='Est un identifiant',
        default=False,
        help='Indique si ce champ est utilisé pour identifier l\'enregistrement chez Bemade'
    )
    
    transform_type = fields.Selection([
        ('none', 'Aucune transformation'),
        ('function', 'Fonction Python'),
        ('mapping', 'Mapping de valeurs'),
        ('direct', 'Direct'),
        ('computed', 'Computed'),
        ('relation', 'Relation')
    ], string='Type de transformation', default='none', required=True,
       help='Type de transformation à appliquer au champ lors de la synchronisation')
    
    transform_mapping = fields.Text(
        string='Mapping de transformation',
        help='Mapping JSON pour la transformation des valeurs (format: {"valeur_source": "valeur_cible",...})'
    )
    
    transform_function = fields.Text(
        string='Fonction de transformation',
        help='Code Python pour transformer la valeur (doit retourner la valeur transformée)'
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Indique si ce champ est activement synchronisé'
    )
    
    @api.constrains('transform_mapping')
    def _check_transform_mapping_json(self):
        """Vérifie que le mapping de transformation est un JSON valide."""
        for record in self:
            if record.transform_mapping:
                try:
                    mapping = json.loads(record.transform_mapping)
                    if not isinstance(mapping, dict):
                        raise ValidationError(_("Le mapping de transformation doit être un dictionnaire JSON"))
                    # Validate that all keys and values are strings or simple types
                    for key, value in mapping.items():
                        if not isinstance(key, (str, int, float, bool)) or \
                           not isinstance(value, (str, int, float, bool, type(None))):
                            raise ValidationError(_("Le mapping de transformation ne peut contenir que des types simples"))
                except json.JSONDecodeError:
                    raise ValidationError(_("Le mapping de transformation doit être un JSON valide"))
    
    @api.constrains('transform_function')
    def _check_transform_function(self):
        """Vérifie que la fonction de transformation est valide."""
        for record in self:
            if record.transform_function:
                # Basic syntax check
                try:
                    compile(record.transform_function, '<string>', 'exec')
                except SyntaxError as e:
                    raise ValidationError(_("Erreur de syntaxe dans la fonction de transformation: %s") % str(e))
                
                # Check for potentially dangerous functions
                dangerous_terms = ['import', 'exec', 'eval', 'os.', 'sys.', 'subprocess', 'open(', '__']
                for term in dangerous_terms:
                    if term in record.transform_function:
                        raise ValidationError(_("Terme non autorisé dans la fonction de transformation: %s") % term)
    
    @api.constrains('field_name', 'bemade_field_name')
    def _check_field_names(self):
        """Vérifie que les noms de champs sont valides."""
        for record in self:
            # Check that field_name exists in the model
            if record.field_name and record.sync_model_id and record.sync_model_id.model:
                model = self.env.get(record.sync_model_id.model)
                if model and record.field_name not in model._fields:
                    raise ValidationError(_("Le champ '%s' n'existe pas dans le modèle '%s'") % 
                                        (record.field_name, record.sync_model_id.model))
            
            # Validate field name format
            if record.field_name and not record.field_name.replace('_', '').isalnum():
                raise ValidationError(_("Le nom du champ ne peut contenir que des caractères alphanumériques et des underscores"))
            
            if record.bemade_field_name and not record.bemade_field_name.replace('_', '').isalnum():
                raise ValidationError(_("Le nom du champ Bemade ne peut contenir que des caractères alphanumériques et des underscores"))
    
    def transform_value(self, value):
        """Transforme une valeur selon la configuration du champ."""
        self.ensure_one()
        
        if self.transform_type == 'none' or value is False:
            return value
            
        if self.transform_type == 'mapping':
            if not self.transform_mapping:
                return value
            
            try:
                mapping = json.loads(self.transform_mapping)
                str_value = str(value)
                transformed_value = mapping.get(str_value, value)
                
                # Log transformation for audit purposes
                _logger.info(
                    "Field transformation: %s.%s value '%s' transformed to '%s'",
                    self.sync_model_id.model, self.field_name, value, transformed_value
                )
                return transformed_value
            except Exception as e:
                _logger.error(
                    "Error in mapping transformation for %s.%s: %s",
                    self.sync_model_id.model, self.field_name, str(e)
                )
                return value
            
        if self.transform_type == 'function':
            if not self.transform_function:
                return value
                
            # Implémentation sécurisée de l'exécution de code
            allowed_builtins = {
                'str': str, 'int': int, 'float': float, 'bool': bool,
                'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                'len': len, 'max': max, 'min': min, 'sum': sum,
                'round': round, 'abs': abs, 'all': all, 'any': any,
                'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter,
                'True': True, 'False': False, 'None': None
            }
            
            local_dict = {'value': value, 'result': value}
            try:
                # pylint: disable=exec-used
                exec(self.transform_function, {'__builtins__': allowed_builtins}, local_dict)
                transformed_value = local_dict.get('result', value)
                
                # Log transformation for audit purposes
                _logger.info(
                    "Function transformation: %s.%s value '%s' transformed to '%s'",
                    self.sync_model_id.model, self.field_name, value, transformed_value
                )
                return transformed_value
            except Exception as e:
                _logger.error(
                    "Error in function transformation for %s.%s: %s",
                    self.sync_model_id.model, self.field_name, str(e)
                )
                return value
