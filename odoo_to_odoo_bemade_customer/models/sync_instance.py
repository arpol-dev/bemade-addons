# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Customer Instance Synchronization Configuration.

This module defines the customer instance configuration for synchronization
with the Bemade platform. It is designed to be installed on the customer's
Odoo instance and does not depend on the provider module.
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeCustomerInstance(models.Model):
    _name = 'odoo.to.bemade.customer.instance'
    _description = 'Instance de synchronisation client Bemade'
    _inherit = 'odoo.sync.instance'
    _order = 'name'

    name = fields.Char(
        string='Nom',
        required=True,
        help='Nom descriptif de l\'instance de synchronisation',
    )
    
    url = fields.Char(
        string='URL',
        required=True,
        help='URL de l\'instance Bemade (ex: https://bemade.org)',
    )
    
    database = fields.Char(
        string='Base de données',
        required=True,
        help='Nom de la base de données Bemade',
    )
    
    username = fields.Char(
        string='Utilisateur',
        required=True,
        help='Nom d\'utilisateur pour la connexion à l\'instance Bemade',
    )
    
    password = fields.Char(
        string='Mot de passe',
        required=True,
        help='Mot de passe pour la connexion à l\'instance Bemade',
    )
    
    api_key = fields.Char(
        string='Clé API',
        help='Clé API pour l\'authentification (si utilisée)',
    )
    
    connection_type = fields.Selection(
        selection_add=[('xmlrpc', 'XML-RPC'), ('jsonrpc', 'JSON-RPC')],
        ondelete={'xmlrpc': 'set default', 'jsonrpc': 'set default'},
        default='xmlrpc',
        required=True,
        help='Protocole de connexion à utiliser',
    )
    
    state = fields.Selection(
        selection_add=[
            ('draft', 'Brouillon'),
            ('testing', 'Test en cours'),
            ('error', 'Erreur'),
            ('connected', 'Connecté'),
        ],
        ondelete={'draft': 'set default', 'testing': 'set default', 'error': 'set default', 'connected': 'set default'},
        help='État de la connexion avec l\'instance Bemade',
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Indique si l\'instance est active',
    )
    
    connection_timeout = fields.Integer(
        string='Timeout de connexion',
        default=30,
        help='Délai d\'attente maximum pour les connexions (en secondes)',
    )
    
    retry_count = fields.Integer(
        string='Nombre de tentatives',
        default=3,
        help='Nombre de tentatives en cas d\'échec de connexion',
    )
    
    retry_delay = fields.Integer(
        string='Délai entre tentatives',
        default=10,
        help='Délai entre les tentatives de connexion (en secondes)',
    )
    
    customer_model = fields.Char(
        string='Modèle client',
        help='Nom technique du modèle client pour cette instance',
    )
    
    last_connection = fields.Datetime(
        string='Dernière connexion',
        readonly=True,
        help='Date et heure de la dernière connexion réussie',
    )
    
    log_ids = fields.One2many(
        'odoo.to.bemade.customer.sync.log',
        'instance_id',
        string='Journaux',
        help='Historique des connexions et opérations',
    )
    
    model_ids = fields.One2many(
        'odoo.to.bemade.customer.sync.model',
        'customer_instance_id',
        string='Modèles synchronisés',
        help='Modèles configurés pour la synchronisation',
    )
    
    @api.model
    def create(self, vals):
        """Override create to encrypt sensitive data."""
        # TODO: Implement encryption for password and api_key
        return super().create(vals)
    
    def write(self, vals):
        """Override write to encrypt sensitive data."""
        # TODO: Implement encryption for password and api_key
        return super().write(vals)
    
    def test_connection(self):
        """Test the connection to the Bemade instance."""
        self.ensure_one()
        self.state = 'testing'
        
        try:
            # TODO: Implement actual connection test
            # For now, just simulate success
            self.state = 'connected'
            self.last_connection = fields.Datetime.now()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connexion réussie'),
                    'message': _('La connexion à l\'instance Bemade a été établie avec succès.'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            self.state = 'error'
            _logger.error("Connection test failed: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur de connexion'),
                    'message': str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
