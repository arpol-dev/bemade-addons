# -*- coding: utf-8 -*-
{
    "name": "IA pour messages perdus",
    "version": "17.0.1.0.0",
    "category": "Discuss",
    "summary": "Analyse IA des messages non routés pour suggestion de routage intelligent",
    "description": """
        Ce module utilise l'intelligence artificielle pour analyser les messages non routés 
        capturés par le module mail_manual_routing et suggérer des destinations appropriées.
        
        Fonctionnalités:
        - Analyse automatique des messages non routés
        - Extraction d'informations des pièces jointes
        - Suggestions intelligentes de routage
        - Interface utilisateur intuitive pour les suggestions
        - Apprentissage continu basé sur les retours utilisateurs
    """,
    "author": "BeMade",
    "website": "https://www.bemade.org",
    "depends": [
        "mail_manual_routing",
        "base",  # En attendant un module hypothétique base_ai
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_message_view.xml",
        "views/res_config_settings_view.xml",
        "views/mail_message_ai_suggestion_view.xml",
        "views/menu.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
