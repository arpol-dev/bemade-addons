{
    'name': 'Odoo to Odoo Bemade Customer',
    'version': '18.0.2.0.0',
    'category': 'Technical',
    'summary': 'Configuration client Bemade pour synchronisation avec Odoo.bemade.org',
    'description': """
        Configuration pré-définie pour les clients Bemade synchronisant avec Odoo.bemade.org.
        Ce module est un wrapper minimal qui fournit la configuration par défaut
        pour la connexion sécurisée à l'instance Bemade principale.
    """,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'depends': [
        'base', 
        'odoo_to_odoo_sync'
    ],
    'data': [
        'data/ir_config_parameter_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
