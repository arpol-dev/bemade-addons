# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_auto_analyze_enabled = fields.Boolean(
        string="Analyse automatique des messages perdus",
        config_parameter="mail_manual_routing_ai.auto_analyze_enabled",
        default=True,
        help="Analyser automatiquement les messages perdus avec l'IA"
    )
    
    ai_auto_routing_enabled = fields.Boolean(
        string="Routage automatique",
        config_parameter="mail_manual_routing_ai.auto_routing_enabled",
        default=False,
        help="Router automatiquement les messages selon les suggestions de l'IA si le score de confiance est suffisant"
    )
    
    ai_auto_routing_threshold = fields.Float(
        string="Seuil de confiance pour routage automatique",
        config_parameter="mail_manual_routing_ai.auto_routing_threshold",
        default=0.95,
        help="Score de confiance minimum pour le routage automatique (0-1)"
    )
    
    ai_models_allowed = fields.Char(
        string="Modèles autorisés pour le routage IA",
        config_parameter="mail_manual_routing_ai.models_allowed",
        default="sale.order,project.project,project.task,res.partner",
        help="Liste de modèles séparés par des virgules autorisés pour le routage IA"
    )
    
    ai_learning_enabled = fields.Boolean(
        string="Apprentissage continu",
        config_parameter="mail_manual_routing_ai.learning_enabled",
        default=True,
        help="Utiliser les retours utilisateurs pour améliorer les futures suggestions"
    )
    
    # Paramètres OpenWebUI
    ai_use_openwebui = fields.Boolean(
        string="Utiliser OpenWebUI",
        config_parameter='mail_manual_routing_ai.use_openwebui'
    )
    
    ai_openwebui_endpoint = fields.Char(
        string="URL de l'API OpenWebUI",
        config_parameter="mail_manual_routing_ai.openwebui_endpoint",
        default="http://localhost:3000/api/chat",
        help="URL de l'API OpenWebUI pour l'analyse des messages"
    )
    
    ai_openwebui_api_key = fields.Char(
        string="Clé API OpenWebUI",
        config_parameter="mail_manual_routing_ai.openwebui_api_key",
        default="",
        help="Clé API pour l'authentification avec OpenWebUI"
    )
    
    ai_responsible_user_id = fields.Many2one(
        'res.users',
        string="Utilisateur responsable des messages perdus",
        config_parameter="mail_manual_routing_ai.responsible_user_id",
        default=lambda self: self.env.ref('base.user_admin').id,
        help="Utilisateur qui recevra les activités pour les messages perdus analysés"
    )
