# -*- coding: utf-8 -*-
{
    'name': 'Kubernetes Odoo Manager',
    'version': '1.0.0',
    'category': 'Administration',
    'summary': 'Manage Odoo instances running on Kubernetes',
    'author': 'Bemade Inc.',
    'website': 'https://bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/k8s_odoo_manager_security.xml',
        'security/ir.model.access.csv',
        'views/k8s_cluster_views.xml',
        'views/k8s_odoo_instance_views.xml',
        'views/k8s_odoo_manager_menus.xml',
        'data/k8s_odoo_manager_data.xml',
        'wizards/wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bemade_k8s_odoo_manager/static/src/js/instance_dashboard.js',
            'bemade_k8s_odoo_manager/static/src/scss/instance_dashboard.scss',
            'bemade_k8s_odoo_manager/static/src/xml/instance_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'description': """
Kubernetes Odoo Manager
======================

This module provides an interface for managing Odoo instances running on Kubernetes clusters.

Features
--------

* **Kubernetes Connection**:
  - Connect to a Kubernetes cluster using kubeconfig file authentication
  - Securely store and manage kubeconfig credentials

* **Odoo Instance Management**:
  - Create, update, and delete Odoo instances
  - Scale instances up or down
  - Configure resources (CPU, memory, storage)
  - Manage domain names and TLS certificates
  - Set up custom configuration options

* **Upgrade Management**:
  - Schedule and execute module upgrades
  - Track upgrade history

Technical Information
--------------------

This module interfaces with the Kubernetes API to manage Odoo instances using the Odoo Operator
custom resource definition (CRD). It provides a user-friendly interface for operations that would
otherwise require command-line tools or direct API access.

The module is designed to work with the Bemade Odoo Operator for Kubernetes, which handles the
actual deployment and management of Odoo instances on the cluster.
    """,
}
