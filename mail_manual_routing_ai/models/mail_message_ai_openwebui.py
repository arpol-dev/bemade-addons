# -*- coding: utf-8 -*-

import base64
import json
import logging
import requests
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailMessageAIOpenWebUI(models.AbstractModel):
    _name = "mail.message.ai.openwebui"
    _description = "Intégration OpenWebUI pour l'analyse des messages"

    @api.model
    def _get_openwebui_endpoint(self):
        """Récupère l'URL de l'API OpenWebUI depuis les paramètres système"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'mail_manual_routing_ai.openwebui_endpoint'
        ) or 'http://localhost:3000/api/chat'

    @api.model
    def _get_openwebui_api_key(self):
        """Récupère la clé API OpenWebUI depuis les paramètres système"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'mail_manual_routing_ai.openwebui_api_key'
        ) or ''

    @api.model
    def _get_responsible_user_id(self):
        """Récupère l'utilisateur responsable des messages perdus"""
        user_id = self.env['ir.config_parameter'].sudo().get_param(
            'mail_manual_routing_ai.responsible_user_id'
        )
        return int(user_id) if user_id else 1

    def analyze_message_with_openwebui(self, message):
        """
        Envoie le message et ses pièces jointes à OpenWebUI pour analyse
        et crée une activité pour l'utilisateur responsable
        
        :param message: mail.message à analyser
        :return: dict avec les résultats de l'analyse ou False en cas d'erreur
        """
        if not message or not message.is_unattached:
            return False

        try:
            # Préparation du contenu à envoyer
            content = self._prepare_message_content(message)
            
            # Appel à l'API OpenWebUI
            response = self._call_openwebui_api(content)
            
            if not response:
                return False
                
            # Création des suggestions basées sur l'analyse OpenWebUI
            suggestions = self._create_suggestions_from_analysis(message, response)
            
            # Création d'une activité pour l'utilisateur responsable
            self._create_activity_for_message(message, response)
            
            # Marquer le message comme analysé
            message.ai_analyzed = True
            
            return response
            
        except Exception as e:
            _logger.error("Erreur lors de l'analyse OpenWebUI du message %s: %s", message.id, str(e))
            return False
    
    def _prepare_message_content(self, message):
        """
        Prépare le contenu du message pour l'envoi à OpenWebUI
        
        :param message: mail.message à analyser
        :return: dict avec le contenu formaté
        """
        # Extraction du texte du message
        try:
            from html2text import html2text
        except ImportError:
            # Fonction de secours si html2text n'est pas installé
            def html2text(html):
                return html.replace('<br>', '\n').replace('<p>', '\n').replace('</p>', '\n')
        body_text = html2text(message.body) if message.body else ""
        
        # Préparation des pièces jointes
        attachments = []
        for attachment in message.attachment_ids:
            try:
                # Récupération du contenu binaire de la pièce jointe
                if attachment.datas:
                    attachment_data = {
                        'name': attachment.name,
                        'type': attachment.mimetype or 'application/octet-stream',
                        'content': attachment.datas.decode('utf-8') if attachment.datas else '',
                    }
                    attachments.append(attachment_data)
            except Exception as e:
                _logger.warning("Impossible de traiter la pièce jointe %s: %s", attachment.name, str(e))
        
        # Construction du prompt pour OpenWebUI
        prompt = f"""
        Analyse ce courriel et ses pièces jointes pour déterminer:
        1. Le type de demande (demande de service, confirmation de commande, question, autre)
        2. L'urgence (faible, moyenne, élevée)
        3. Les actions recommandées
        4. Le département concerné (ventes, support, comptabilité, autre)
        5. Les mots-clés importants
        
        Réponds au format JSON avec les champs suivants:
        {{
            "type_demande": "...",
            "urgence": "...",
            "actions_recommandees": ["...", "..."],
            "departement": "...",
            "mots_cles": ["...", "..."],
            "resume": "...",
            "modele_suggere": "..." (sale.order, project.project, helpdesk.ticket, etc.),
            "confiance": ... (valeur entre 0 et 1)
        }}
        
        Courriel:
        De: {message.email_from}
        À: {message.email_to or 'Non spécifié'}
        Sujet: {message.subject or 'Sans objet'}
        Date: {message.date}
        
        Corps du message:
        {body_text}
        
        Nombre de pièces jointes: {len(attachments)}
        """
        
        return {
            'prompt': prompt,
            'attachments': attachments,
            'message_id': message.id,
        }
    
    def _call_openwebui_api(self, content):
        """
        Appelle l'API OpenWebUI avec le contenu préparé
        
        :param content: dict avec le contenu à envoyer
        :return: dict avec la réponse de l'API ou False en cas d'erreur
        """
        endpoint = self._get_openwebui_endpoint()
        api_key = self._get_openwebui_api_key()
        
        if not endpoint:
            _logger.error("Endpoint OpenWebUI non configuré")
            return False
            
        headers = {
            'Content-Type': 'application/json',
        }
        
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        try:
            # Dans une implémentation réelle, nous enverrions réellement la requête
            # Pour cette démonstration, nous simulons une réponse
            
            # requests.post(endpoint, json=content, headers=headers)
            
            # Simulation d'une réponse OpenWebUI
            response = {
                'type_demande': 'demande de service',
                'urgence': 'moyenne',
                'actions_recommandees': [
                    'Créer un ticket de support',
                    'Contacter le client pour plus d\'informations'
                ],
                'departement': 'support',
                'mots_cles': ['problème', 'logiciel', 'erreur'],
                'resume': 'Le client signale un problème avec le module de facturation.',
                'modele_suggere': 'helpdesk.ticket',
                'confiance': 0.85
            }
            
            return response
            
        except Exception as e:
            _logger.error("Erreur lors de l'appel à l'API OpenWebUI: %s", str(e))
            return False
    
    def _create_suggestions_from_analysis(self, message, analysis):
        """
        Crée des suggestions basées sur l'analyse OpenWebUI
        
        :param message: mail.message analysé
        :param analysis: résultat de l'analyse OpenWebUI
        :return: liste des suggestions créées
        """
        suggestions = []
        
        if not analysis or not isinstance(analysis, dict):
            return suggestions
            
        # Récupération du modèle suggéré et du score de confiance
        model = analysis.get('modele_suggere')
        confidence = analysis.get('confiance', 0.5)
        
        if model and model in self.env:
            # Recherche des enregistrements récents de ce type
            records = self.env[model].sudo().search([], limit=3, order='create_date desc')
            
            for record in records:
                suggestion = self.env['mail.message.ai.suggestion'].create({
                    'message_id': message.id,
                    'suggested_model': model,
                    'suggested_record_id': record.id,
                    'confidence_score': confidence * 0.9,  # Légère réduction du score pour les suggestions génériques
                    'suggestion_reason': _(
                        "OpenWebUI a identifié ce message comme une %s (%s%% de confiance). "
                        "Résumé: %s"
                    ) % (
                        analysis.get('type_demande', 'demande'),
                        int(confidence * 100),
                        analysis.get('resume', 'Non disponible')
                    ),
                })
                suggestions.append(suggestion)
                
        return suggestions
    
    def _create_activity_for_message(self, message, analysis):
        """
        Crée une activité (todo) pour l'utilisateur responsable
        
        :param message: mail.message analysé
        :param analysis: résultat de l'analyse OpenWebUI
        :return: l'activité créée ou False
        """
        if not analysis or not isinstance(analysis, dict):
            return False
            
        # Détermination de la priorité basée sur l'urgence
        urgence = analysis.get('urgence', 'moyenne').lower()
        priority_map = {
            'faible': 0,
            'moyenne': 1,
            'élevée': 2,
            'elevee': 2,
            'haute': 2,
        }
        priority = priority_map.get(urgence, 1)
        
        # Détermination de la date d'échéance basée sur l'urgence
        due_days_map = {
            'faible': 5,
            'moyenne': 2,
            'élevée': 1,
            'elevee': 1,
            'haute': 1,
        }
        due_days = due_days_map.get(urgence, 2)
        date_deadline = fields.Date.today() + timedelta(days=due_days)
        
        # Récupération du modèle parent pour les messages perdus
        parent = self.env['lost.message.parent'].sudo().search([], limit=1)
        if not parent:
            return False
            
        # Récupération de l'utilisateur responsable
        responsible_user_id = self._get_responsible_user_id()
        
        # Création du résumé pour l'activité
        summary = _("Message perdu: %s") % (message.subject or 'Sans objet')
        
        # Création de la note avec les détails de l'analyse
        note = _("""
<p><strong>Analyse IA du message perdu</strong></p>
<ul>
    <li><strong>Type de demande:</strong> %(type)s</li>
    <li><strong>Urgence:</strong> %(urgence)s</li>
    <li><strong>Département concerné:</strong> %(departement)s</li>
    <li><strong>Résumé:</strong> %(resume)s</li>
</ul>
<p><strong>Actions recommandées:</strong></p>
<ul>
    %(actions)s
</ul>
<p><strong>Mots-clés:</strong> %(mots_cles)s</p>
<p><a href="/mail/view?model=lost.message.parent&res_id=%(parent_id)s">Voir le message</a></p>
        """) % {
            'type': analysis.get('type_demande', 'Non identifié'),
            'urgence': analysis.get('urgence', 'Non identifié'),
            'departement': analysis.get('departement', 'Non identifié'),
            'resume': analysis.get('resume', 'Non disponible'),
            'actions': ''.join([f"<li>{action}</li>" for action in analysis.get('actions_recommandees', ['Aucune action suggérée'])]),
            'mots_cles': ', '.join(analysis.get('mots_cles', ['Aucun'])),
            'parent_id': parent.id,
        }
        
        # Création de l'activité
        activity_values = {
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': summary,
            'note': note,
            'user_id': responsible_user_id,
            'res_id': parent.id,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'lost.message.parent')], limit=1).id,
            'date_deadline': date_deadline,
        }
        
        # Vérifier si le champ priority existe dans le modèle mail.activity
        if 'priority' in self.env['mail.activity']._fields:
            activity_values['priority'] = priority
            
        activity = self.env['mail.activity'].create(activity_values)
        
        return activity
