# -*- coding: utf-8 -*-

import logging
import re
from html2text import html2text

from odoo import api, models, _
from odoo.tools.misc import clean_context

_logger = logging.getLogger(__name__)


class MailMessageAIAnalyzer(models.AbstractModel):
    _name = "mail.message.ai.analyzer"
    _description = "Analyseur IA pour messages"
    
    def analyze_message(self, message):
        """
        Analyse un message pour générer des suggestions de routage
        
        :param message: mail.message à analyser
        :return: True si l'analyse a été effectuée
        """
        self.ensure_one()
        if not message or not message.is_unattached or message.ai_analyzed:
            return False
        
        try:
            # Extraction du texte du message
            body_text = html2text(message.body) if message.body else ""
            subject_text = message.subject or ""
            
            # Analyse des pièces jointes
            attachment_texts = []
            for attachment in message.attachment_ids:
                attachment_text = self._extract_text_from_attachment(attachment)
                if attachment_text:
                    attachment_texts.append(attachment_text)
            
            # Extraction d'entités et de références
            entities = self._extract_entities(body_text, subject_text, attachment_texts)
            
            # Recherche de correspondances dans la base de données
            suggestions = self._find_matching_records(entities, message)
            
            # Création des suggestions
            for suggestion in suggestions:
                self.env['mail.message.ai.suggestion'].create({
                    'message_id': message.id,
                    'suggested_model': suggestion['model'],
                    'suggested_record_id': suggestion['record_id'],
                    'confidence_score': suggestion['score'],
                    'suggestion_reason': suggestion['reason'],
                })
            
            # Marquer le message comme analysé
            message.ai_analyzed = True
            return True
            
        except Exception as e:
            _logger.error("Erreur lors de l'analyse IA du message %s: %s", message.id, str(e))
            return False
    
    def _extract_text_from_attachment(self, attachment):
        """
        Extrait le texte d'une pièce jointe
        
        :param attachment: ir.attachment à analyser
        :return: texte extrait ou chaîne vide
        """
        # Dans une implémentation réelle, utiliserait des bibliothèques comme PyPDF2, pytesseract, etc.
        # Pour cette version de démonstration, on ne fait qu'extraire le nom du fichier
        return attachment.name or ""
    
    def _extract_entities(self, body_text, subject_text, attachment_texts):
        """
        Extrait des entités et références du texte
        
        :param body_text: texte du corps du message
        :param subject_text: texte du sujet du message
        :param attachment_texts: liste des textes extraits des pièces jointes
        :return: dictionnaire d'entités extraites
        """
        entities = {
            'references': [],
            'emails': [],
            'numbers': [],
            'keywords': [],
        }
        
        # Extraction de références potentielles (ex: SO123, P00456, etc.)
        all_text = body_text + " " + subject_text + " " + " ".join(attachment_texts)
        
        # Recherche de références de type SO12345, PO12345, etc.
        ref_patterns = [
            (r'SO[0-9]{5,}', 'sale.order'),
            (r'PO[0-9]{5,}', 'purchase.order'),
            (r'INV[0-9]{5,}', 'account.move'),
            (r'P[0-9]{5,}', 'project.project'),
            (r'T[0-9]{5,}', 'project.task'),
        ]
        
        for pattern, model in ref_patterns:
            matches = re.findall(pattern, all_text)
            for match in matches:
                entities['references'].append({
                    'text': match,
                    'type': 'reference',
                    'model': model,
                    'confidence': 0.8,
                })
        
        # Extraction d'emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, all_text)
        for email in emails:
            entities['emails'].append({
                'text': email,
                'type': 'email',
                'confidence': 0.9,
            })
        
        # Extraction de numéros
        number_pattern = r'\b\d{5,}\b'
        numbers = re.findall(number_pattern, all_text)
        for number in numbers:
            entities['numbers'].append({
                'text': number,
                'type': 'number',
                'confidence': 0.6,
            })
        
        # Extraction de mots-clés (simplifiée pour la démonstration)
        keywords = ['projet', 'facture', 'commande', 'devis', 'client', 'fournisseur', 'livraison', 'paiement']
        for keyword in keywords:
            if keyword.lower() in all_text.lower():
                entities['keywords'].append({
                    'text': keyword,
                    'type': 'keyword',
                    'confidence': 0.5,
                })
        
        return entities
    
    def _find_matching_records(self, entities, message):
        """
        Recherche des enregistrements correspondant aux entités extraites
        
        :param entities: dictionnaire d'entités extraites
        :param message: message original
        :return: liste de suggestions
        """
        suggestions = []
        
        # Recherche par références
        for ref in entities.get('references', []):
            model = ref.get('model')
            text = ref.get('text')
            
            if model and text:
                # Recherche par nom ou référence
                records = self.env[model].sudo().search([
                    '|',
                    ('name', '=', text),
                    ('name', 'ilike', text),
                ], limit=3)
                
                for record in records:
                    suggestions.append({
                        'model': model,
                        'record_id': record.id,
                        'score': ref.get('confidence', 0.5) * 0.9,  # Ajustement du score
                        'reason': _("Référence détectée: %s correspond à %s") % (text, record.display_name),
                    })
        
        # Recherche par emails
        for email_entity in entities.get('emails', []):
            email = email_entity.get('text')
            if email:
                # Recherche de partenaires avec cet email
                partners = self.env['res.partner'].sudo().search([
                    '|',
                    ('email', '=ilike', email),
                    ('email', '=ilike', email.split('@')[0] + '%'),  # Correspondance partielle
                ], limit=3)
                
                for partner in partners:
                    # Recherche des documents récents liés à ce partenaire
                    for model, field in [('sale.order', 'partner_id'), ('project.project', 'partner_id')]:
                        if model in self.env:
                            records = self.env[model].sudo().search([
                                (field, '=', partner.id),
                            ], limit=2, order='create_date desc')
                            
                            for record in records:
                                suggestions.append({
                                    'model': model,
                                    'record_id': record.id,
                                    'score': email_entity.get('confidence', 0.5) * 0.7,
                                    'reason': _("Email %s associé à %s, qui est lié à %s") % (
                                        email, partner.display_name, record.display_name),
                                })
        
        # Recherche par mots-clés
        models_by_keyword = {
            'projet': 'project.project',
            'facture': 'account.move',
            'commande': 'sale.order',
            'devis': 'sale.order',
            'client': 'res.partner',
            'fournisseur': 'res.partner',
            'livraison': 'stock.picking',
            'paiement': 'account.payment',
        }
        
        for keyword_entity in entities.get('keywords', []):
            keyword = keyword_entity.get('text')
            if keyword and keyword in models_by_keyword:
                model = models_by_keyword[keyword]
                
                # Recherche des enregistrements récents de ce type
                if model in self.env:
                    records = self.env[model].sudo().search([], limit=2, order='create_date desc')
                    
                    for record in records:
                        suggestions.append({
                            'model': model,
                            'record_id': record.id,
                            'score': keyword_entity.get('confidence', 0.5) * 0.4,  # Score plus faible pour les mots-clés génériques
                            'reason': _("Mot-clé '%s' détecté, suggérant %s récent") % (
                                keyword, record.display_name),
                        })
        
        # Tri et limitation des suggestions
        suggestions.sort(key=lambda s: s.get('score', 0), reverse=True)
        return suggestions[:5]  # Limite à 5 suggestions
