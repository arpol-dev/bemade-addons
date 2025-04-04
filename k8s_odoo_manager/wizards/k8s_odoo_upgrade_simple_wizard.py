# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from kubernetes.client.rest import ApiException

_logger = logging.getLogger(__name__)

class K8sOdooUpgradeSimpleWizard(models.TransientModel):
    _name = 'k8s.odoo.upgrade.simple.wizard'
    _description = 'Simple Odoo Upgrade Wizard'

    instance_id = fields.Many2one(
        'k8s.odoo.instance',
        string='Odoo Instance',
        required=True,
        readonly=True
    )
    
    database = fields.Char(
        string='Database',
        required=True,
        help='Database name to upgrade'
    )
    
    modules = fields.Char(
        string='Modules',
        required=True,
        help='Comma-separated list of modules to upgrade'
    )
    
    scheduled_time = fields.Datetime(
        string='Scheduled Time',
        help='When to run the upgrade (leave empty to run immediately)'
    )
    
    admin_password = fields.Char(
        string='Admin Password',
        required=True,
        help='Admin password for the Odoo instance'
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            instance = self.env['k8s.odoo.instance'].browse(active_id)
            res['instance_id'] = instance.id
            # Try to get the database name from the instance
            if instance.k8s_config_options:
                import yaml
                try:
                    config = yaml.safe_load(instance.k8s_config_options)
                    if config and isinstance(config, dict) and 'db_name' in config:
                        res['database'] = config['db_name']
                except Exception as e:
                    _logger.warning(f"Could not parse config options: {e}")
        return res
    
    def action_trigger_upgrade(self):
        """Trigger the upgrade in Kubernetes"""
        self.ensure_one()
        instance = self.instance_id
        
        try:
            # Get the Kubernetes client
            api_client = instance.cluster_id.get_k8s_client()
            custom_api = instance.cluster_id._get_custom_objects_api()
            
            # Get the OdooInstance custom resource
            try:
                current_instance = custom_api.get_namespaced_custom_object(
                    group="bemade.org",
                    version="v1",
                    namespace=instance.namespace,
                    plural="odooinstances",
                    name=instance.name,
                )
            except ApiException as e:
                if e.status == 404:
                    raise UserError(
                        _(
                            "The Odoo instance does not exist in Kubernetes."
                        )
                    )
                else:
                    raise
            
            # Set the admin password for the upgrade
            current_instance["spec"]["adminPassword"] = self.admin_password
            
            # Prepare the upgrade spec
            upgrade_spec = {
                "database": self.database,
                "modules": [m.strip() for m in self.modules.split(',') if m.strip()]
            }
            
            # Add scheduled time if provided
            if self.scheduled_time:
                upgrade_spec["time"] = self.scheduled_time.isoformat()
            
            # Add the upgrade spec to trigger the operator's upgrade process
            current_instance["spec"]["upgrade"] = upgrade_spec
            
            # Update the OdooInstance in Kubernetes
            custom_api.patch_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=instance.namespace,
                plural="odooinstances",
                name=instance.name,
                body=current_instance,
            )
            
            # Schedule a status check
            self.env.ref(
                "bemade_k8s_odoo_manager.ir_cron_check_instance_status"
            ).method_direct_trigger()
            
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Upgrade Triggered"),
                    "message": _("The upgrade process has been initiated."),
                    "sticky": False,
                    "type": "success",
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            _logger.error(error_message)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error"),
                    "message": error_message,
                    "sticky": True,
                    "type": "danger",
                },
            }
