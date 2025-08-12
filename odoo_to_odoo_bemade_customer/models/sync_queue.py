# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Queue de synchronisation pour Odoo to Bemade Customer.

Ce module gère la file d'attente des opérations de synchronisation
entre Odoo client et Bemade.
"""

import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OdooToBemadeCustomerSyncQueue(models.Model):
    """File d'attente de synchronisation.

    Gère les opérations de synchronisation en file d'attente entre Odoo client et Bemade.
    """

    _name = 'odoo.to.bemade.customer.sync.queue'
    _description = 'File d\'attente de synchronisation Bemade'
    _inherit = 'odoo.sync.queue'
    _order = 'priority desc, create_date'

    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )
    model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle',
        required=True,
        ondelete='cascade',
    )
    record_id = fields.Integer(
        string='ID Enregistrement',
        required=True,
    )
    operation = fields.Selection(
        selection_add=[
            ('sync', 'Synchroniser'),
            ('delete', 'Supprimer'),
        ],
        ondelete={'sync': 'set default', 'delete': 'set default'},
        default='sync',
        string='Opération',
        required=True,
    )
    state = fields.Selection(
        selection_add=[
            ('pending', 'En attente'),
            ('processing', 'En cours'),
            ('done', 'Terminé'),
            ('error', 'Erreur'),
        ],
        ondelete={'pending': 'set default', 'processing': 'set default', 'done': 'set default', 'error': 'set default'},
        default='pending',
        string='État',
    )
    priority = fields.Integer(
        string='Priorité',
        default=10,
        help='Priorité de l\'opération (les valeurs plus élevées sont prioritaires)',
    )
    retry_count = fields.Integer(
        string='Tentatives',
        default=0,
    )
    max_retries = fields.Integer(
        string='Tentatives max',
        default=3,
    )
    error_message = fields.Text(
        string='Message d\'erreur',
    )
    next_retry = fields.Datetime(
        string='Prochaine tentative',
    )
    result = fields.Text(
        string='Résultat',
    )
    execution_time = fields.Float(
        string='Temps d\'exécution (s)',
        digits=(10, 3),
    )

    @api.depends('model_id', 'record_id', 'operation')
    def _compute_name(self):
        """Génère un nom descriptif pour l'entrée de la file d'attente."""
        for queue in self:
            if queue.model_id and queue.record_id:
                queue.name = f"{queue.operation} - {queue.model_id.name} #{queue.record_id}"
            else:
                queue.name = f"Nouvelle entrée {queue.id}"

    def action_reset(self):
        """Réinitialise une entrée de file d'attente en erreur à l'état en attente."""
        return self.write({
            'state': 'pending',
            'retry_count': 0,
            'error_message': False,
            'next_retry': False
        })

    def action_cancel(self):
        """Annule une entrée de file d'attente."""
        return self.unlink()

    def action_retry_now(self):
        """Force la tentative immédiate de traitement d'une entrée en erreur."""
        self.ensure_one()
        self.write({
            'state': 'pending',
            'next_retry': fields.Datetime.now(),
        })
        return self.env['odoo.to.bemade.customer.sync.manager'].process_queue(queue_ids=self.ids)
        
    @api.constrains('model_id', 'record_id')
    def _check_record_exists(self):
        """Vérifie que l'enregistrement à synchroniser existe."""
        for queue in self:
            if queue.model_id and queue.record_id:
                # Vérifier si le modèle existe dans l'environnement
                model_name = queue.model_id.model
                if not model_name or model_name not in self.env:
                    raise ValidationError(_("Le modèle %s n'existe pas dans l'environnement.") % model_name)
                    
                # Vérifier si l'enregistrement existe (sauf pour les suppressions)
                if queue.operation != 'delete':
                    record = self.env[model_name].sudo().browse(queue.record_id)
                    if not record.exists():
                        raise ValidationError(_("L'enregistrement %s #%s n'existe pas.") % 
                                         (model_name, queue.record_id))
    
    @api.constrains('model_id')
    def _check_model_configuration(self):
        """Vérifie que le modèle est correctement configuré pour la synchronisation."""
        for queue in self:
            if not queue.model_id:
                continue
                
            # Vérifier que le modèle a un mapping de champs valide
            if not queue.model_id.field_mapping and not queue.model_id.field_ids:
                raise ValidationError(_("Le modèle %s n'a pas de mapping de champs configuré.") % 
                                   queue.model_id.name)
            
            # Vérifier que le modèle a un modèle Bemade correspondant
            if not queue.model_id.bemade_model:
                raise ValidationError(_("Le modèle %s n'a pas de modèle Bemade correspondant configuré.") % 
                                   queue.model_id.name)
                                   
    @api.constrains('state', 'retry_count', 'max_retries')
    def _check_retry_limits(self):
        """Vérifie les limites de tentatives et l'état de la file d'attente."""
        for queue in self:
            # Vérifier que le nombre de tentatives ne dépasse pas le maximum
            if queue.retry_count > queue.max_retries:
                queue.write({'state': 'error'})
                _logger.warning(
                    "Queue #%s: Nombre maximum de tentatives atteint (%s/%s)", 
                    queue.id, queue.retry_count, queue.max_retries
                )
                
            # Vérifier la cohérence entre l'état et le message d'erreur
            if queue.state == 'error' and not queue.error_message:
                queue.write({'error_message': _("Erreur inconnue lors de la synchronisation.")})
                
    @api.constrains('next_retry')
    def _check_next_retry_date(self):
        """Vérifie que la date de prochaine tentative est cohérente."""
        for queue in self:
            if queue.next_retry and queue.state == 'pending':
                # Vérifier que la date de prochaine tentative n'est pas trop éloignée (max 7 jours)
                max_date = fields.Datetime.now() + timedelta(days=7)
                if queue.next_retry > max_date:
                    queue.write({'next_retry': max_date})
                    _logger.info(
                        "Queue #%s: Date de prochaine tentative ajustée à %s (max 7 jours)", 
                        queue.id, max_date
                    )
