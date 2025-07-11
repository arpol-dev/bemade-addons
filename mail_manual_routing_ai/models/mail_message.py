# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailMessage(models.Model):
    _inherit = "mail.message"
    
    ai_suggestion_ids = fields.One2many('mail.message.ai.suggestion', 'message_id', string="Suggestions IA")
    ai_suggestion_count = fields.Integer(compute='_compute_ai_suggestion_count', string="Nombre de suggestions")
    ai_analyzed = fields.Boolean(string="Analysé par IA", default=False)
    ai_top_suggestion_id = fields.Many2one('mail.message.ai.suggestion', compute='_compute_top_suggestion')
    ai_analysis_result = fields.Text(string="Résultat d'analyse IA", readonly=True)
    ai_activity_id = fields.Many2one('mail.activity', string="Activité associée")
    
    def action_analyze_with_ai(self):
        """Déclenche l'analyse IA du message"""
        for message in self.filtered(lambda m: m.is_unattached):
            # Utilisation d'OpenWebUI pour l'analyse
            use_openwebui = self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.use_openwebui', False)
            if use_openwebui and use_openwebui == 'True':
                self.env['mail.message.ai.openwebui'].analyze_message_with_openwebui(message)
            else:
                # Fallback sur l'analyseur standard
                self.env['mail.message.ai.analyzer'].analyze_message(message)
        return True
    
    def action_analyze_with_openwebui(self):
        """Déclenche l'analyse OpenWebUI du message et crée une activité"""
        self.ensure_one()
        if not self.is_unattached:
            return False
            
        result = self.env['mail.message.ai.openwebui'].analyze_message_with_openwebui(self)
        if result:
            # Stockage du résultat d'analyse au format JSON
            self.ai_analysis_result = str(result)
            return True
        return False
    
    @api.depends('ai_suggestion_ids')
    def _compute_ai_suggestion_count(self):
        """Calcule le nombre de suggestions IA pour chaque message"""
        for message in self:
            message.ai_suggestion_count = len(message.ai_suggestion_ids)
    
    @api.depends('ai_suggestion_ids.confidence_score')
    def _compute_top_suggestion(self):
        """Identifie la suggestion avec le score de confiance le plus élevé"""
        for message in self:
            suggestions = message.ai_suggestion_ids.sorted(key=lambda s: s.confidence_score, reverse=True)
            message.ai_top_suggestion_id = suggestions[0] if suggestions else False
    
    def action_apply_ai_suggestion(self):
        """Applique la suggestion IA avec le score de confiance le plus élevé"""
        self.ensure_one()
        if self.ai_top_suggestion_id:
            return self.ai_top_suggestion_id.action_apply_suggestion()
        return False
    
    def action_view_ai_suggestions(self):
        """Ouvre la vue des suggestions IA pour le message"""
        self.ensure_one()
        return {
            'name': _('Suggestions IA'),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message.ai.suggestion',
            'view_mode': 'tree,form',
            'domain': [('message_id', '=', self.id)],
            'context': {'default_message_id': self.id},
        }
    
    @api.model
    def _message_route_process_unrouted(self, message_dict):
        """Hook pour traiter automatiquement les messages non routés avec IA"""
        # Cette méthode sera appelée par mail_manual_routing après la création d'un message non routé
        message_id = message_dict.get('id')
        if not message_id:
            return True
            
        message = self.browse(message_id)
        if not message.exists() or not message.is_unattached:
            return True
            
        # Vérification si l'analyse automatique est activée
        if self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.auto_analyze_enabled', False) and self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.auto_analyze_enabled') == 'True':
            # Utilisation d'OpenWebUI si configuré
            if self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.use_openwebui', False) and self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.use_openwebui') == 'True':
                self.env['mail.message.ai.openwebui'].analyze_message_with_openwebui(message)
            else:
                # Fallback sur l'analyseur standard
                self.env['mail.message.ai.analyzer'].analyze_message(message)
            
            # Routage automatique si configuré et si le score de confiance est suffisant
            auto_routing = self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.auto_routing_enabled', False)
            threshold_str = self.env['ir.config_parameter'].sudo().get_param('mail_manual_routing_ai.auto_routing_threshold', '0.95')
            threshold = float(threshold_str) if threshold_str else 0.95
            
            if (auto_routing == 'True' and message.ai_top_suggestion_id and 
                message.ai_top_suggestion_id.confidence_score >= threshold):
                message.ai_top_suggestion_id.action_apply_suggestion()
        
        return True
