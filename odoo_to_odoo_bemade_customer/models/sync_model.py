# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Synchronization Configuration for Bemade clients.

This module defines how models are synchronized between client instances
and the Bemade platform. It is simplified to focus on the specific needs
of Bemade clients.
"""

import logging
import json
import ast

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def safe_eval_domain(domain_str):
    """Safely evaluate a domain string to a domain list.
    
    Args:
        domain_str (str): Domain string to evaluate
        
    Returns:
        list: Domain list
        
    Raises:
        ValidationError: If domain is invalid or contains dangerous code
    """
    if not domain_str:
        return []
        
    # Check for potentially dangerous code
    dangerous_terms = ['import', 'exec', 'eval', 'os.', 'sys.', 'subprocess', 'open(', '__']
    for term in dangerous_terms:
        if term in domain_str:
            raise ValidationError(_("Terme non autorisé dans le domaine: %s") % term)
            
    try:
        # Use ast.literal_eval for safer evaluation
        domain = ast.literal_eval(domain_str)
        return domain
    except (SyntaxError, ValueError) as e:
        raise ValidationError(_("Erreur de syntaxe dans le domaine: %s") % str(e))

class OdooToBemadeCustomerSyncModel(models.Model):
    _name = 'odoo.to.bemade.customer.sync.model'
    _description = 'Modèle synchronisé avec Bemade'
    _inherit = 'odoo.sync.model'
    _order = 'priority, id'

    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom descriptif du modèle synchronisé',
    )
    
    model = fields.Char(
        string='Modèle local',
        required=True,
        help='Nom technique du modèle local (ex: res.partner)',
    )
    
    bemade_model = fields.Char(
        string='Modèle Bemade',
        required=True,
        help='Nom technique du modèle correspondant chez Bemade',
    )
    
    config_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
    )
    
    customer_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.instance',
        string='Instance',
        ondelete='cascade',
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Indique si ce modèle est synchronisé activement',
    )
    
    priority = fields.Integer(
        string='Priorité',
        default=10,
        help='Ordre de synchronisation (les valeurs plus élevées sont prioritaires)',
    )
    
    field_mapping = fields.Text(
        string='Mapping des champs',
        help='Mapping JSON des champs entre le modèle local et Bemade',
    )
    
    field_ids = fields.One2many(
        comodel_name='odoo.to.bemade.customer.sync.model.field', 
        inverse_name='sync_model_id', 
        string='Champs synchronisés'
    )
    
    field_count = fields.Integer(
        string='Nombre de champs',
        compute='_compute_field_count',
    )
    
    @api.depends('field_ids')
    def _compute_field_count(self):
        """Calcule le nombre de champs synchronisés pour ce modèle"""
        for record in self:
            record.field_count = len(record.field_ids) if record.field_ids else 0
    
    queue_ids = fields.One2many(
        comodel_name='odoo.to.bemade.customer.sync.queue',
        inverse_name='model_id',
        string='File d\'attente',
    )
    
    create_active = fields.Boolean(
        string='Création active',
        default=True,
        help='Activer la synchronisation des créations',
    )
    
    write_active = fields.Boolean(
        string='Modification active',
        default=True,
        help='Activer la synchronisation des modifications',
    )
    
    unlink_active = fields.Boolean(
        string='Suppression active',
        default=True,
        help='Activer la synchronisation des suppressions',
    )
    
    sync_domain = fields.Char(
        string='Domaine de synchronisation',
        default='[]',
        help='Domaine pour filtrer les enregistrements à synchroniser, au format liste Python',
    )
    
    last_error = fields.Text(
        string='Dernière erreur',
        readonly=True,
        help='Description de la dernière erreur rencontrée lors de la synchronisation',
    )
    
    last_sync = fields.Datetime(
        string='Dernière synchronisation',
        readonly=True,
    )
    
    sync_status = fields.Selection(
        selection=[
            ('pending', 'En attente'),
            ('synced', 'Synchronisé'),
            ('error', 'Erreur')
        ],
        default='pending',
        string='Statut de synchronisation',
    )

    error_count = fields.Integer(
        string='Nombre d\'erreurs',
        default=0,
    )
    
    record_count = fields.Integer(
        string='Enregistrements synchronisés',
        compute='_compute_record_count',
    )
    
    @api.depends('model', 'sync_domain')
    def _compute_record_count(self):
        """Calcule le nombre d'enregistrements synchronisés pour ce modèle"""
        for record in self:
            try:
                if not record.model:
                    record.record_count = 0
                    continue
                    
                model_obj = self.env.get(record.model)
                if not model_obj:
                    record.record_count = 0
                    continue
                    
                domain = safe_eval_domain(record.sync_domain)
                record.record_count = model_obj.search_count(domain)
            except Exception as e:
                _logger.error("Erreur lors du calcul du nombre d'enregistrements pour %s: %s", 
                             record.model, str(e))
                record.record_count = 0
    
    @api.constrains('model')
    def _check_model_exists(self):
        """Vérifie que le modèle existe dans l'instance Odoo."""
        for record in self:
            if record.model:
                model_obj = self.env.get(record.model)
                if not model_obj:
                    raise ValidationError(_("Le modèle '%s' n'existe pas dans cette instance Odoo") % record.model)
    
    @api.constrains('sync_domain')
    def _check_sync_domain(self):
        """Vérifie que le domaine de synchronisation est valide."""
        for record in self:
            if record.sync_domain:
                try:
                    domain = safe_eval_domain(record.sync_domain)
                    
                    # Validate domain structure
                    if not isinstance(domain, list):
                        raise ValidationError(_("Le domaine de synchronisation doit être une liste"))
                        
                    # Check if model exists before validating domain
                    if record.model:
                        model_obj = self.env.get(record.model)
                        if model_obj:
                            # Try a search with the domain to validate it
                            try:
                                model_obj.search(domain, limit=1)
                            except Exception as e:
                                raise ValidationError(_("Domaine de synchronisation invalide pour le modèle '%s': %s") % 
                                                    (record.model, str(e)))
                except Exception as e:
                    raise ValidationError(_("Erreur dans le domaine de synchronisation: %s") % str(e))
    
    @api.constrains('field_mapping')
    def _check_field_mapping(self):
        """Vérifie que le mapping des champs est un JSON valide et que les champs existent."""
        for record in self:
            if record.field_mapping:
                try:
                    # Validate JSON format
                    mapping = json.loads(record.field_mapping)
                    
                    # Validate mapping structure
                    if not isinstance(mapping, dict):
                        raise ValidationError(_("Le mapping des champs doit être un dictionnaire JSON"))
                    
                    # Check if model exists before validating fields
                    if record.model:
                        model_obj = self.env.get(record.model)
                        if model_obj:
                            # Validate field existence
                            for local_field in mapping.keys():
                                if local_field not in model_obj._fields:
                                    raise ValidationError(_("Le champ '%s' n'existe pas dans le modèle '%s'") % 
                                                        (local_field, record.model))
                except json.JSONDecodeError:
                    raise ValidationError(_("Le mapping des champs n'est pas un JSON valide"))
                except Exception as e:
                    raise ValidationError(_("Erreur dans le mapping des champs: %s") % str(e))
    
    @api.constrains('bemade_model')
    def _check_bemade_model(self):
        """Vérifie que le modèle Bemade est spécifié et a un format valide."""
        for record in self:
            if record.bemade_model:
                # Check format (should be in the form 'module.model')
                if '.' not in record.bemade_model:
                    raise ValidationError(_("Le modèle Bemade doit être au format 'module.model'"))
                    
                # Additional checks could be added here if we had a way to validate
                # against the actual Bemade instance models
    
    def create_all_fields(self):
        """Create field mappings for all fields in the model.
        
        This method is called from the view button to automatically
        generate field mappings for all fields in the model.
        
        Enhanced with intelligent field mapping based on field types and names.
        
        Returns:
            dict: Action dictionary for refreshing the view
        """
        self.ensure_one()
        
        # Get the model
        model = self.env[self.model]
        model_fields = model._fields
        
        # Create field mappings for each relevant field
        field_mapping_model = self.env['odoo.to.bemade.customer.sync.model.field']
        
        # Get target model fields if possible
        target_fields = {}
        try:
            # Try to get information about the target model structure
            if self.customer_instance_id and self.bemade_model:
                # This would be replaced with actual API call in production
                _logger.info(f"Attempting to get fields for {self.bemade_model} from Bemade")
                # For now we'll simulate with empty dict
                target_fields = {}
        except Exception as e:
            _logger.warning(f"Could not retrieve target model fields: {str(e)}")
        
        # Common field name variations to check
        name_variations = {
            '_id': ['_id', '_uid', '_identifier'],
            'name': ['name', 'label', 'title', 'display_name'],
            'code': ['code', 'reference', 'ref'],
            'date': ['date', 'datetime', 'day', 'timestamp'],
            'partner': ['partner', 'customer', 'client'],
            'product': ['product', 'item', 'article'],
            'quantity': ['quantity', 'qty', 'amount', 'number'],
            'price': ['price', 'cost', 'rate', 'value'],
            'total': ['total', 'sum', 'amount_total'],
            'state': ['state', 'status', 'stage'],
            'active': ['active', 'is_active', 'enabled'],
        }
        
        for field_name, field in model_fields.items():
            # Skip fields that shouldn't be synchronized
            if field.type in ['one2many', 'many2many']:
                continue
                
            if field_name in ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']:
                continue
            
            # Check if field mapping already exists
            existing = field_mapping_model.search([
                ('sync_model_id', '=', self.id),
                ('source_field', '=', field_name)
            ], limit=1)
            
            if not existing:
                # Determine best target field and transform type
                target_field = field_name
                transform_type = 'direct'
                
                # Check if we need special handling based on field type
                if field.type == 'many2one':
                    # For many2one fields, we might want to map to a different field
                    # or use a different transform type
                    transform_type = 'relation_id'
                    
                    # If field ends with _id, suggest the base name as target
                    if field_name.endswith('_id') and len(field_name) > 3:
                        target_field = field_name[:-3]  # Remove _id suffix
                
                # Check for common name variations
                for base, variations in name_variations.items():
                    for part in field_name.split('_'):
                        if part in variations:
                            # Found a variation, suggest the base name
                            for var in variations:
                                if var != part and f"{field_name.replace(part, var)}" in target_fields:
                                    target_field = field_name.replace(part, base)
                                    break
                
                # Create the field mapping with intelligent defaults
                field_mapping_model.create({
                    'sync_model_id': self.id,
                    'source_field': field_name,
                    'target_field': target_field,
                    'active': True,
                    'transform_type': transform_type,
                    'notes': f"Auto-mapped from {field.type} field",
                })
        
        # Return action to refresh the view
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
        
        if not self.active:
            raise UserError(_("Ce modèle n'est pas actif pour la synchronisation."))
        
        # Get all records of this model
        model_obj = self.env[self.model]
        domain = eval(self.sync_domain)
        records = model_obj.search(domain)
        
        # Queue synchronization for each record
        queue_obj = self.env['odoo.to.bemade.customer.sync.queue']
        count = 0
        
        for record in records:
            queue_obj.create({
                'model_id': self.id,
                'record_id': record.id,
                'operation': 'sync',
                'state': 'pending',
                'priority': self.priority,
            })
            count += 1
        
        # Return action to show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Synchronisation démarrée"),
                'message': _(f"{count} enregistrements ont été mis en file d'attente pour synchronisation."),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_sync_model(self):
        """Synchroniser ce modèle spécifique avec Bemade"""
        self.ensure_one()
        if not self.active:
            raise UserError(_("Ce modèle n'est pas actif pour la synchronisation."))
            
        # Obtenir la configuration
        config = self.config_id
        if not config or config.state != 'connected':
            raise UserError(_("La connexion avec Bemade n'est pas établie."))
            
        # Obtenir les enregistrements à synchroniser
        model_obj = self.env[self.model]
        domain = eval(self.sync_domain)
        records = model_obj.search(domain)
        
        # Queue des enregistrements pour synchronisation
        queue_obj = self.env['odoo.to.bemade.customer.sync.queue']
        count = 0
        
        for record in records:
            queue_obj.create({
                'model_id': self.id,
                'record_id': record.id,
                'operation': 'sync',
                'state': 'pending',
                'priority': self.priority,
            })
            count += 1
            
        # Mettre à jour le statut
        self.write({
            'last_sync': fields.Datetime.now(),
            'sync_status': 'pending',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation programmée'),
                'message': _(f"{count} enregistrements ont été mis en file d'attente pour la synchronisation."),
                'sticky': False,
                'type': 'success',
            }
        }
    
    def action_view_records(self):
        """Afficher les enregistrements correspondant à ce modèle"""
        self.ensure_one()
        return {
            'name': _('Enregistrements à synchroniser'),
            'type': 'ir.actions.act_window',
            'res_model': self.model,
            'view_mode': 'tree,form',
            'domain': self.sync_domain,
        }
        
    def action_view_queue(self):
        """Afficher les entrées de file d'attente pour ce modèle"""
        self.ensure_one()
        return {
            'name': _('File d\'attente de synchronisation'),
            'type': 'ir.actions.act_window',
            'res_model': 'odoo.to.bemade.customer.sync.queue',
            'view_mode': 'tree,form',
            'domain': [('model_id', '=', self.id)],
        }
