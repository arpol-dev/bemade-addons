# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailMessageAISuggestion(models.Model):
    _name = "mail.message.ai.suggestion"
    _description = "Suggestions IA pour messages perdus"
    _order = "confidence_score desc, id desc"
    
    message_id = fields.Many2one('mail.message', string="Message", required=True, ondelete='cascade')
    suggested_model = fields.Char(string="Modèle suggéré")
    suggested_record_id = fields.Integer(string="ID d'enregistrement suggéré")
    suggested_record_name = fields.Char(string="Nom de l'enregistrement", compute="_compute_suggested_record_name", store=True)
    confidence_score = fields.Float(string="Score de confiance", help="Score de confiance de l'IA (0-1)")
    suggestion_reason = fields.Text(string="Explication", help="Explication de la suggestion par l'IA")
    is_applied = fields.Boolean(string="Appliqué", default=False)
    user_feedback = fields.Selection([
        ('positive', 'Correcte'),
        ('negative', 'Incorrecte'),
    ], string="Retour utilisateur")
    date_created = fields.Datetime(string="Date de création", default=fields.Datetime.now)
    
    @api.depends('suggested_model', 'suggested_record_id')
    def _compute_suggested_record_name(self):
        """Récupère le nom de l'enregistrement suggéré pour l'affichage"""
        for suggestion in self:
            if suggestion.suggested_model and suggestion.suggested_record_id:
                try:
                    record = self.env[suggestion.suggested_model].sudo().browse(suggestion.suggested_record_id)
                    if record.exists():
                        suggestion.suggested_record_name = record.display_name
                    else:
                        suggestion.suggested_record_name = _("Enregistrement non trouvé")
                except Exception:
                    suggestion.suggested_record_name = _("Modèle non valide")
            else:
                suggestion.suggested_record_name = False
    
    def name_get(self):
        """Personnalise l'affichage du nom des suggestions"""
        result = []
        for suggestion in self:
            name = f"{suggestion.suggested_model or '?'} - {suggestion.suggested_record_name or '?'} ({int(suggestion.confidence_score * 100)}%)"
            result.append((suggestion.id, name))
        return result
    
    def action_apply_suggestion(self):
        """Applique la suggestion en attachant le message à l'enregistrement suggéré"""
        self.ensure_one()
        if not self.suggested_model or not self.suggested_record_id:
            return False
        
        # Utilise le wizard de mail_manual_routing pour attacher le message
        wizard = self.env['mail.message.attach.wizard'].create({
            'message_ids': [(6, 0, [self.message_id.id])],
            'model': self.suggested_model,
            'res_id': self.suggested_record_id,
        })
        result = wizard.action_attach_mail_message()
        
        # Marque la suggestion comme appliquée et enregistre un feedback positif
        self.write({
            'is_applied': True,
            'user_feedback': 'positive',
        })
        
        return result
    
    def action_mark_feedback(self, feedback_type):
        """Enregistre le feedback de l'utilisateur sur la suggestion"""
        self.ensure_one()
        self.write({
            'user_feedback': feedback_type,
        })
        return True
