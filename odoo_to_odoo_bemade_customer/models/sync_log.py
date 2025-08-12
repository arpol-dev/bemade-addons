# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Journal de synchronisation pour Odoo to Bemade Customer.

Ce module enregistre toutes les opérations de synchronisation effectuées
entre Odoo client et Bemade pour des fins d'audit et de dépannage.
"""

# -*- coding: utf-8 -*-

import json
import logging
import odoo
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OdooToBemadeCustomerSyncLog(models.Model):
    """Journal des synchronisations.

    Enregistre toutes les opérations de synchronisation pour traçabilité.
    """

    _name = 'odoo.to.bemade.customer.sync.log'
    _description = 'Journal de synchronisation Bemade'
    _inherit = 'odoo.sync.log'
    _order = 'create_date desc'

    name = fields.Char(
        string='Opération',
        required=True,
    )
    instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.instance',
        string='Instance',
        ondelete='cascade',
    )
    model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle',
        ondelete='set null',
    )
    record_id = fields.Integer(
        string='ID Enregistrement',
    )
    operation = fields.Selection(
        selection=[
            ('sync', 'Synchronisation'),
            ('delete', 'Suppression'),
            ('conflict', 'Conflit'),
            ('error', 'Erreur'),
        ],
        string='Type d\'opération',
        required=True,
    )
    direction = fields.Selection(
        selection=[
            ('to_bemade', 'Odoo → Bemade'),
            ('from_bemade', 'Bemade → Odoo'),
        ],
        string='Direction',
    )
    result = fields.Selection(
        selection=[
            ('success', 'Succès'),
            ('warning', 'Avertissement'),
            ('error', 'Erreur'),
        ],
        string='Résultat',
        required=True,
    )
    execution_time = fields.Float(
        string='Temps d\'exécution (s)',
        digits=(10, 3),
    )
    details = fields.Text(
        string='Détails',
        help='Détails de l\'opération de synchronisation',
    )
    remote_id = fields.Char(
        string='ID Bemade',
    )
    queue_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.queue',
        string='Entrée file d\'attente',
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Utilisateur',
        default=lambda self: self.env.user.id,
        readonly=True,
    )
    error_message = fields.Text(
        string='Message d\'erreur',
    )
    metadata = fields.Text(
        string='Métadonnées',
        help='Métadonnées d\'audit (utilisateur, IP, timestamp)',
    )

    @api.constrains('model_id', 'record_id')
    def _check_record_consistency(self):
        """Vérifie la cohérence entre le modèle et l'ID d'enregistrement."""
        for log in self:
            # Vérifier que si un ID d'enregistrement est spécifié, un modèle est aussi spécifié
            if log.record_id and not log.model_id:
                raise ValidationError(_("Un ID d'enregistrement a été spécifié sans modèle associé."))
    
    def _collect_audit_metadata(self):
        """Collecte les métadonnées d'audit pour la traçabilité.
        
        Returns:
            dict: Métadonnées d'audit (utilisateur, adresse IP, timestamp, etc.)
        """
        metadata = {
            'timestamp': fields.Datetime.now(),
            'user_id': self.env.user.id if self.env.user else None,
            'user_name': self.env.user.name if self.env.user else 'System',
            'user_login': self.env.user.login if self.env.user else None,
        }
        
        # Ajout de l'adresse IP si disponible
        try:
            if hasattr(odoo.http, 'request') and odoo.http.request:
                metadata['ip_address'] = odoo.http.request.httprequest.remote_addr
        except Exception:
            pass  # Ignorer si l'accès à la requête n'est pas disponible
            
        return metadata
    
    def track_changes(self, old_values=None):
        """Enregistre les changements effectués sur cette entrée de journal.
        
        Cette méthode permet de garder une trace des modifications apportées à une entrée
        de journal, ce qui est utile pour l'audit et la traçabilité.
        
        Args:
            old_values (dict): Valeurs précédentes des champs modifiés
        """
        if not old_values:
            return
            
        # Champs à suivre pour l'audit
        tracked_fields = [
            'result', 'operation', 'details', 'error_message',
            'remote_id', 'record_id', 'model_id', 'instance_id'
        ]
        
        changes = []
        for field in tracked_fields:
            if field in old_values and hasattr(self, field) and getattr(self, field) != old_values[field]:
                # Pour les champs Many2one, on stocke le nom plutôt que l'ID
                if field.endswith('_id') and hasattr(getattr(self, field), 'name'):
                    old_value = old_values[field].name if old_values[field] else False
                    new_value = getattr(self, field).name if getattr(self, field) else False
                else:
                    old_value = old_values[field]
                    new_value = getattr(self, field)
                
                changes.append({
                    'field': field,
                    'old': old_value,
                    'new': new_value
                })
                
        if changes:
            # Collecte des métadonnées d'audit
            metadata = self._collect_audit_metadata()
            
            # Format des détails pour inclure les changements
            current_details = self.details or ''
            change_log = '\n--- Modifications %s ---\n' % fields.Datetime.now()
            
            for change in changes:
                field_label = self._fields[change['field']].string if change['field'] in self._fields else change['field']
                change_log += '%s: %s -> %s\n' % (field_label, change['old'], change['new'])
            
            self.write({
                'details': current_details + '\n' + change_log if current_details else change_log,
                'metadata': json.dumps(metadata, default=str)
            })
            
            # Journaliser les modifications importantes
            if any(c['field'] in ['result', 'operation'] for c in changes):
                change_str = ', '.join(['%s: %s -> %s' % (c['field'], c['old'], c['new']) for c in changes])
                _logger.info('Sync Log #%s modifié: %s', self.id, change_str)

    @api.constrains('result', 'error_message')
    def _check_result_consistency(self):
        """Vérifie la cohérence entre le résultat et le message d'erreur.

        Si le résultat est 'error', un message d'erreur doit être fourni.
        Si le résultat est 'success', aucun message d'erreur ne devrait être présent.
        """
        for log in self:
            if log.result == 'error' and not log.error_message:
                raise ValidationError(_("Un message d'erreur est requis lorsque le résultat est 'error'."))
            if log.result == 'success' and log.error_message:
                raise ValidationError(_("Aucun message d'erreur ne devrait être présent lorsque le résultat est 'success'."))

    def _validate_data_consistency(self):
        """Vérifie la cohérence des données du journal de synchronisation et retourne le résultat.

        Cette méthode s'assure que:
        1. Si un ID d'enregistrement est spécifié, un modèle est également spécifié
        2. Le modèle spécifié existe dans l'environnement
        3. L'enregistrement existe (sauf pour les opérations de suppression)

        Returns:
            dict: Résultat de la validation avec les clés:
                - valid (bool): True si la validation est réussie
                - errors (list): Liste des erreurs rencontrées
                - warnings (list): Liste des avertissements
                - record_exists (bool): True si l'enregistrement existe
                - model_name (str): Nom du modèle si valide
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'record_exists': False,
            'model_name': False
        }

        # Vérifier que si un ID d'enregistrement est spécifié, un modèle est aussi spécifié
        if self.record_id and not self.model_id:
            result['errors'].append(_("Un ID d'enregistrement a été spécifié sans modèle associé."))
            return result

        # Vérifier que le modèle existe dans l'environnement
        if self.model_id and self.model_id.model:
            model_name = self.model_id.model
            result['model_name'] = model_name

            if model_name not in self.env:
                result['errors'].append(_("Le modèle %s n'existe pas dans l'environnement.") % model_name)
                return result

            # Vérifier l'existence de l'enregistrement sauf pour les suppressions
            if self.record_id:
                if self.operation == 'delete':
                    # Pour les suppressions, on ne vérifie pas l'existence de l'enregistrement
                    result['warnings'].append(_("L'enregistrement a été supprimé et n'est plus accessible."))
                else:
                    record = self.env[model_name].sudo().browse(self.record_id)
                    if record.exists():
                        result['record_exists'] = True
                    else:
                        result['warnings'].append(
                            _("L'enregistrement %s #%s n'existe pas ou plus.") % (model_name, self.record_id)
                        )
                        _logger.warning(
                            "Log #%s: L'enregistrement %s #%s n'existe pas ou plus.", 
                            self.id, model_name, self.record_id
                        )

        # Vérifier que le résultat est une valeur valide selon la définition du champ
        valid_results = ['success', 'warning', 'error']
        if self.result and self.result not in valid_results:
            result['errors'].append(
                _("Résultat invalide: %s. Les valeurs autorisées sont: %s") %
                (self.result, ', '.join(valid_results))
            )

        if not result['errors']:
            result['valid'] = True

        return result

    @api.constrains('record_id', 'model_id')
    def validate_data_consistency(self):
        """Vérifie la cohérence des données du journal de synchronisation.

        Cette méthode s'assure que:
        1. Si un ID d'enregistrement est spécifié, un modèle est également spécifié
        2. Le modèle spécifié existe dans l'environnement
        3. L'enregistrement existe (sauf pour les opérations de suppression)
        """
        for log in self:
            result = log._validate_data_consistency()
            if not result['valid']:
                raise ValidationError('\n'.join(result['errors']))

    @api.constrains('queue_id', 'model_id', 'record_id')
    def _check_queue_consistency(self):
        """Vérifie la cohérence avec l'entrée de file d'attente liée."""
        for log in self:
            # Si aucune file d'attente n'est spécifiée, rien à valider
            if not log.queue_id:
                continue
                
            # Vérifier que la file d'attente existe toujours
            if not log.queue_id.exists():
                _logger.warning(
                    "Log #%s: L'entrée de file d'attente #%s n'existe plus.",
                    log.id, log.queue_id.id
                )
                continue
                
            # Vérifier la cohérence entre la file d'attente et le modèle
            if log.model_id and log.queue_id.model_id and log.queue_id.model_id != log.model_id:
                message = _("Incohérence entre le modèle de la file d'attente et celui du log.")
                # On génère un avertissement plutôt qu'une erreur pour ne pas bloquer le processus
                _logger.warning(
                    "Log #%s: %s Queue: %s, Log: %s",
                    log.id, message,
                    log.queue_id.model_id.name if log.queue_id.model_id else 'Non défini',
                    log.model_id.name if log.model_id else 'Non défini'
                )
            
            # Vérifier la cohérence entre la file d'attente et l'ID d'enregistrement
            if log.record_id and log.queue_id.record_id and log.queue_id.record_id != log.record_id:
                message = _("Incohérence entre l'ID d'enregistrement de la file d'attente et celui du log.")
                # On génère un avertissement plutôt qu'une erreur pour ne pas bloquer le processus
                _logger.warning(
                    "Log #%s: %s Queue: %s, Log: %s",
                    log.id, message, log.queue_id.record_id, log.record_id
                )
                
            # Vérifier la cohérence de l'opération si les deux sont spécifiées
            if log.operation and log.queue_id.operation and log.operation not in ['error', 'conflict'] and log.operation != log.queue_id.operation:
                _logger.warning(
                    "Log #%s: L'opération du journal (%s) ne correspond pas à celle de la file d'attente (%s).",
                    log.id, log.operation, log.queue_id.operation
                )
    
    def action_view_record(self):
        """Affiche l'enregistrement associé à cette entrée de journal."""
        self.ensure_one()
        validation = self._validate_data_consistency()
        
        if validation['errors']:
            raise ValidationError('\n'.join(validation['errors']))
            
        # Afficher les avertissements s'il y en a
        if validation.get('warnings'):
            warning_message = '\n'.join(validation.get('warnings', []))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Avertissement'),
                    'message': warning_message,
                    'sticky': True,
                    'type': 'warning',
                    'next': {
                        'type': 'ir.actions.act_window',
                        'name': _('Enregistrement synchronisé'),
                        'view_mode': 'form',
                        'res_model': self.model_id.model,
                        'res_id': self.record_id,
                        'target': 'current',
                    } if validation['record_exists'] else None
                }
            }
        
        # Si l'enregistrement n'existe pas (cas de suppression validé), afficher un message
        if not validation['record_exists']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _('L’enregistrement a été supprimé et n’est plus accessible.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
            
        # Retourner l'action pour afficher l'enregistrement
        model_name = self.model_id.model
        return {
            'name': _('Enregistrement synchronisé'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': model_name,
            'res_id': self.record_id,
            'target': 'current',
        }

    @api.model
    def log(self, operation, model=None, record_id=None, result='success', details=None, 
            direction=None, remote_id=None, queue_id=None, execution_time=0, metadata=None):
        """Crée une entrée dans le journal des synchronisations avec audit trail amélioré.
        
        Args:
            operation (str): Type d'opération ('sync', 'delete', 'conflict', 'error')
            model: Modèle concerné (str ou odoo.to.bemade.customer.sync.model)
            record_id (int): ID de l'enregistrement concerné
            result (str): Résultat de l'opération ('success', 'warning', 'error')
            details (str): Détails supplémentaires
            direction (str): Direction de la synchronisation ('to_bemade', 'from_bemade')
            remote_id (str): ID distant de l'enregistrement
            queue_id: Entrée de file d'attente associée (int ou odoo.to.bemade.customer.sync.queue)
            execution_time (float): Temps d'exécution en secondes
            metadata (dict): Métadonnées supplémentaires pour l'audit trail
        """
        model_id = False
        if model and isinstance(model, str):
            model_rec = self.env['odoo.to.bemade.customer.sync.model'].search(
                [('model', '=', model)], limit=1)
            if model_rec:
                model_id = model_rec.id
        elif model and hasattr(model, 'id'):
            model_id = model.id
            
        name = f"{operation.capitalize()}"
        if model_id:
            model_name = self.env['odoo.to.bemade.customer.sync.model'].browse(model_id).name
            name += f" - {model_name}"
        if record_id:
            name += f" #{record_id}"
            
        # Collecter les métadonnées d'audit
        audit_data = self._collect_audit_metadata(metadata)
        
        # Enrichir les détails avec les métadonnées d'audit si spécifié
        if audit_data:
            audit_details = '\n'.join([f"{k}: {v}" for k, v in audit_data.items()])
            if details:
                details = f"{details}\n\n--- Métadonnées d'audit ---\n{audit_details}"
            else:
                details = f"--- Métadonnées d'audit ---\n{audit_details}"
                
        vals = {
            'name': name,
            'model_id': model_id,
            'record_id': record_id,
            'operation': operation,
            'result': result,
            'details': details,
            'direction': direction,
            'remote_id': remote_id,
            'queue_id': queue_id and queue_id if isinstance(queue_id, int) else queue_id and queue_id.id,
            'execution_time': execution_time,
        }
        
        return self.create(vals)
        
    @api.model
    def _collect_audit_metadata(self, additional_metadata=None):
        """Collecte les métadonnées d'audit pour le journal de synchronisation.
        
        Cette méthode recueille des informations importantes pour l'audit trail,
        comme l'adresse IP de l'utilisateur, l'horodatage précis, l'agent utilisateur,
        et d'autres données contextuelles.
        
        Args:
            additional_metadata (dict): Métadonnées supplémentaires fournies par l'appelant
            
        Returns:
            dict: Métadonnées d'audit enrichies
        """
        metadata = {}
        
        # Obtenir le contexte de la requête HTTP si disponible
        try:
            from odoo.http import request
            if request and hasattr(request, 'httprequest'):
                # Adresse IP de l'utilisateur
                metadata['ip_address'] = request.httprequest.remote_addr
                
                # Agent utilisateur
                if hasattr(request.httprequest, 'user_agent') and request.httprequest.user_agent:
                    metadata['user_agent'] = str(request.httprequest.user_agent)
                    
                # Méthode HTTP
                metadata['http_method'] = request.httprequest.method
                
                # URL de la requête
                metadata['request_url'] = request.httprequest.url
        except (ImportError, RuntimeError):
            # Pas de requête HTTP active ou module non disponible
            pass
        
        # Horodatage précis avec microseconds
        from datetime import datetime
        metadata['timestamp_precise'] = datetime.now().isoformat()
        
        # Identifiant de session
        if self.env.context.get('session_id'):
            metadata['session_id'] = self.env.context.get('session_id')
            
        # Informations sur l'utilisateur
        if self.env.user:
            metadata['user_id'] = self.env.user.id
            metadata['user_login'] = self.env.user.login
            if self.env.user.partner_id:
                metadata['user_partner_name'] = self.env.user.partner_id.name
                metadata['user_partner_id'] = self.env.user.partner_id.id
                
        # Contexte technique Odoo
        metadata['odoo_context'] = str(self.env.context)
        metadata['odoo_lang'] = self.env.context.get('lang', 'fr_FR')
        metadata['odoo_tz'] = self.env.context.get('tz', 'Europe/Paris')
        
        # Informations sur la base de données
        metadata['db_name'] = self.env.cr.dbname
        
        # Informations sur l'instance et le modèle
        if hasattr(self, 'instance_id') and self.instance_id:
            metadata['instance_id'] = self.instance_id.id
            metadata['instance_name'] = self.instance_id.name
            
        if hasattr(self, 'model_id') and self.model_id:
            metadata['model_id'] = self.model_id.id
            metadata['model_name'] = self.model_id.name
                
        # Ajouter les métadonnées supplémentaires si fournies
        if additional_metadata and isinstance(additional_metadata, dict):
            metadata.update(additional_metadata)
            
        return metadata
