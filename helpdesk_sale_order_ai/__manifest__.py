# -*- coding: utf-8 -*-

{
    'name': 'Helpdesk Sale Order AI',
    'license': 'LGPL-3',
    'version': '18.0.0.1',
    'category': 'Sales/Sales',
    'summary': """Automatically create sales orders from helpdesk tickets using AI.""",
    'description': """
       Extends the Helpdesk Sale Order module to automatically create sales orders from helpdesk tickets using AI.
       
       This module adds AI capabilities to analyze ticket content and automatically generate appropriate sales orders
       with relevant products and services based on the ticket description.
    """,
    'author': 'Bemade',
    'maintainer': 'it@bemade.org',
    'depends': [
        'helpdesk_sale_order',
        'openwebui_connector',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/res_config_settings_views.xml',
        'views/ai_prompt_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
