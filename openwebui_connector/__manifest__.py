# -*- coding: utf-8 -*-
{
    'name': 'OpenWebUI Connector',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Connect to OpenWebUI and other AI services',
    'description': """
OpenWebUI Connector
===============
This module provides integration with OpenWebUI and other AI services.
It allows other modules to use AI capabilities through a standardized interface.
    """,
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'maintainer': 'it@bemade.org',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/ai_prompt_template_data.xml',
        'views/res_config_settings_views.xml',
        'views/ai_prompt_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['requests'],
    },
}
