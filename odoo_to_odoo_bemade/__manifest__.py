{
    'name': 'Odoo to Odoo Bemade',
    'version': '18.0.2.0.0',
    'category': 'Technical',
    'summary': 'Configuration Bemade pour synchronisation avec instances Odoo',
    'description': """
        Configuration pré-définie Bemade pour la synchronisation avec instances Odoo.
        Ce module est un wrapper minimal qui fournit la configuration par défaut
        pour les instances Bemade.
    """,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'depends': [
        'base',
        'project',
        'odoo_to_odoo_sync'
    ],
    'data': [
        'data/ir_config_parameter_data.xml',
        'views/menus.xml',
        'views/odoo_to_bemade_instance_views.xml',
        # Load project view extensions and wizard UI
        'views/project_views.xml',
        'wizards/assign_project_wizard_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
