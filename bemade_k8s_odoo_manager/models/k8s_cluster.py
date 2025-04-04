# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging
import tempfile
import os
import re
import kubernetes.client
import kubernetes.config
from kubernetes.client.rest import ApiException

_logger = logging.getLogger(__name__)

class K8sCluster(models.Model):
    _name = 'k8s.cluster'
    _description = 'Kubernetes Cluster'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Name of the Kubernetes cluster'
    )
    description = fields.Text(
        string='Description',
        tracking=True,
        help='Description of the cluster and its purpose'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this cluster configuration is active'
    )
    kubeconfig_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Kubeconfig File',
        required=True,
        ondelete='restrict',
        domain="[('res_model', '=', 'k8s.cluster'), ('res_field', '=', 'kubeconfig_data')]",
        help='The kubeconfig file for connecting to the cluster'
    )
    kubeconfig_data = fields.Binary(
        string='Kubeconfig Data',
        attachment=True,
        required=True,
        help='The kubeconfig file content'
    )
    kubeconfig_filename = fields.Char(string='Kubeconfig Filename')
    
    namespace = fields.Char(
        string='Default Namespace',
        default='default',
        required=True,
        help='The default namespace to use for operations'
    )
    
    default_tls_issuer = fields.Char(
        string='Default TLS Issuer',
        default='letsencrypt-prod',
        required=True,
        help='The default cert-manager issuer to use for TLS certificates'
    )
    
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('connected', 'Connected'),
        ('failed', 'Connection Failed')
    ], string='Connection Status', default='not_tested', readonly=True)
    
    connection_error = fields.Text(string='Connection Error', readonly=True)
    last_connection_test = fields.Datetime(string='Last Connection Test', readonly=True)
    
    cluster_version = fields.Char(string='Kubernetes Version', readonly=True)
    node_count = fields.Integer(string='Node Count', readonly=True)
    
    # Related records
    instance_count = fields.Integer(
        string='Instance Count',
        compute='_compute_instance_count',
        help='Number of Odoo instances running on this cluster'
    )
    instance_ids = fields.One2many(
        'k8s.odoo.instance',
        'cluster_id',
        string='Odoo Instances'
    )
    
    @api.depends('instance_ids')
    def _compute_instance_count(self):
        for cluster in self:
            cluster.instance_count = len(cluster.instance_ids)
    
    @api.constrains('namespace')
    def _check_namespace(self):
        for cluster in self:
            if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', cluster.namespace):
                raise ValidationError(_("Namespace must consist of lowercase alphanumeric characters or '-', and must start and end with an alphanumeric character."))
    
    def action_test_connection(self):
        """Test the connection to the Kubernetes cluster"""
        self.ensure_one()
        
        try:
            # Create a temporary file for the kubeconfig if needed
            temp_files = []
            
            # Configure the Kubernetes client using kubeconfig
            if not self.kubeconfig_data:
                raise UserError(_('Kubeconfig file is required.'))
            
            # Create a temporary file for the kubeconfig
            kubeconfig_fd, kubeconfig_path = tempfile.mkstemp()
            temp_files.append(kubeconfig_path)
            with os.fdopen(kubeconfig_fd, 'wb') as f:
                f.write(base64.b64decode(self.kubeconfig_data))
            
            # Load the kubeconfig
            kubernetes.config.load_kube_config(config_file=kubeconfig_path)
            
            # Create API clients
            core_api = kubernetes.client.CoreV1Api()
            version_api = kubernetes.client.VersionApi()
            
            # Test the connection by getting the cluster version
            version_info = version_api.get_code()
            
            # Get the node count
            nodes = core_api.list_node()
            node_count = len(nodes.items)
            
            # Update the cluster information
            self.write({
                'connection_status': 'connected',
                'connection_error': False,
                'last_connection_test': fields.Datetime.now(),
                'cluster_version': f"{version_info.major}.{version_info.minor}",
                'node_count': node_count,
            })
            
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except (OSError, IOError):
                    pass
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Successful'),
                    'message': _('Successfully connected to Kubernetes cluster %s (version %s) with %s nodes.') % (
                        self.name, self.cluster_version, self.node_count
                    ),
                    'sticky': False,
                    'type': 'success',
                }
            }
            
        except ApiException as e:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except (OSError, IOError):
                    pass
            
            error_message = f"API Error: {e.reason}"
            self.write({
                'connection_status': 'failed',
                'connection_error': error_message,
                'last_connection_test': fields.Datetime.now(),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Failed'),
                    'message': error_message,
                    'sticky': False,
                    'type': 'danger',
                }
            }
            
        except Exception as e:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except (OSError, IOError):
                    pass
            
            error_message = f"Error: {str(e)}"
            self.write({
                'connection_status': 'failed',
                'connection_error': error_message,
                'last_connection_test': fields.Datetime.now(),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Failed'),
                    'message': error_message,
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    def get_k8s_client(self):
        """Get a configured Kubernetes client for this cluster"""
        self.ensure_one()
        
        # Create a temporary file for the kubeconfig if needed
        temp_files = []
        
        try:
            # Configure the Kubernetes client using kubeconfig
            if not self.kubeconfig_data:
                raise UserError(_('Kubeconfig file is required.'))
            
            # Create a temporary file for the kubeconfig
            kubeconfig_fd, kubeconfig_path = tempfile.mkstemp()
            temp_files.append(kubeconfig_path)
            with os.fdopen(kubeconfig_fd, 'wb') as f:
                f.write(base64.b64decode(self.kubeconfig_data))
            
            # Load the kubeconfig
            kubernetes.config.load_kube_config(config_file=kubeconfig_path)
            
            # Create and return the API client
            return kubernetes.client.ApiClient()
            
        except Exception as e:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except (OSError, IOError):
                    pass
            
            raise UserError(_("Failed to configure Kubernetes client: %s") % str(e))
    
    def action_view_instances(self):
        """View Odoo instances running on this cluster"""
        self.ensure_one()
        
        return {
            'name': _('Odoo Instances'),
            'type': 'ir.actions.act_window',
            'res_model': 'k8s.odoo.instance',
            'view_mode': 'tree,form',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('k8s.cluster') or _('New')
            
            # Create attachment for kubeconfig
            if 'kubeconfig_data' in vals and vals.get('kubeconfig_data'):
                attachment_vals = {
                    'name': vals.get('kubeconfig_filename', 'kubeconfig'),
                    'type': 'binary',
                    'datas': vals['kubeconfig_data'],
                    'res_model': 'k8s.cluster',
                    'res_field': 'kubeconfig_data',
                }
                attachment = self.env['ir.attachment'].create(attachment_vals)
                vals['kubeconfig_attachment_id'] = attachment.id
                
        return super().create(vals_list)
        
    def write(self, vals):
        # Update attachment if kubeconfig changes
        if 'kubeconfig_data' in vals and vals.get('kubeconfig_data'):
            for record in self:
                # Delete old attachment if it exists
                if record.kubeconfig_attachment_id:
                    record.kubeconfig_attachment_id.unlink()
                
                # Create new attachment
                attachment_vals = {
                    'name': vals.get('kubeconfig_filename', record.kubeconfig_filename or 'kubeconfig'),
                    'type': 'binary',
                    'datas': vals['kubeconfig_data'],
                    'res_model': 'k8s.cluster',
                    'res_field': 'kubeconfig_data',
                }
                attachment = self.env['ir.attachment'].create(attachment_vals)
                vals['kubeconfig_attachment_id'] = attachment.id
                
        return super().write(vals)
        
    def unlink(self):
        # Delete attachments when records are deleted
        attachments = self.mapped('kubeconfig_attachment_id')
        result = super().unlink()
        if result and attachments:
            attachments.unlink()
        return result
