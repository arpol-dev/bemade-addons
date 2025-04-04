# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import kubernetes.client
from kubernetes.client.rest import ApiException
import logging
import json
import re
import yaml
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class K8sOdooInstance(models.Model):
    _name = "k8s.odoo.instance"
    _description = "Kubernetes Odoo Instance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Name", required=True, tracking=True, help="Name of the Odoo instance"
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        string="Kubernetes Cluster",
        required=True,
        tracking=True,
        ondelete="cascade",
        help="The Kubernetes cluster where this instance is running",
    )
    namespace = fields.Char(
        string="Namespace",
        required=True,
        tracking=True,
        help="The Kubernetes namespace where this instance is deployed",
    )
    description = fields.Text(
        string="Description",
        tracking=True,
        help="Description of the instance and its purpose",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        help="Whether this instance is active in the system",
    )

    # URLs
    odoo_url = fields.Char(string="Odoo URL", compute="_compute_odoo_url", store=True)

    # Related records
    upgrade_ids = fields.One2many("k8s.odoo.upgrade", "instance_id", string="Upgrades")

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS FROM KUBERNETES
    # -------------------------------------------------------------------------

    # Flag to indicate if reading from Kubernetes failed
    k8s_read_failed = fields.Boolean(
        string="Kubernetes Read Failed",
        compute="_compute_k8s_config",
        store=False,
        help="Indicates that reading the configuration from Kubernetes failed",
    )

    # Docker image configuration from Kubernetes
    k8s_image = fields.Char(
        string="Current Image",
        compute="_compute_k8s_config",
        store=False,
        help="Current Docker image used in Kubernetes",
    )
    k8s_image_pull_secret = fields.Char(
        string="Current Pull Secret",
        compute="_compute_k8s_config",
        store=False,
        help="Current Kubernetes secret containing Docker registry credentials",
    )

    # Resource configuration from Kubernetes
    k8s_cpu_request = fields.Char(
        string="Current CPU Request",
        compute="_compute_k8s_config",
        store=False,
        help="CPU request for each Odoo pod (e.g., 200m, 1)",
    )
    k8s_memory_request = fields.Char(
        string="Current Memory Request",
        compute="_compute_k8s_config",
        store=False,
        help="Memory request for each Odoo pod (e.g., 250Mi, 1Gi)",
    )
    k8s_cpu_limit = fields.Char(
        string="Current CPU Limit",
        compute="_compute_k8s_config",
        store=False,
        help="CPU limit for each Odoo pod (e.g., 2000m, 2)",
    )
    k8s_memory_limit = fields.Char(
        string="Current Memory Limit",
        compute="_compute_k8s_config",
        store=False,
        help="Memory limit for each Odoo pod (e.g., 2Gi, 4Gi)",
    )

    # Filestore configuration from Kubernetes
    k8s_filestore_size = fields.Char(
        string="Current Filestore Size",
        compute="_compute_k8s_config",
        store=False,
        help="Current size of the persistent volume for the filestore",
    )
    k8s_filestore_storage_class = fields.Char(
        string="Current Storage Class",
        compute="_compute_k8s_config",
        store=False,
        help="Current storage class used for the filestore persistent volume",
    )

    # Ingress configuration from Kubernetes
    k8s_host_names = fields.Text(
        string="Current Host Names",
        compute="_compute_k8s_config",
        store=False,
        help="Current comma-separated list of host names for accessing the Odoo instance",
    )
    k8s_tls_issuer = fields.Char(
        string="Current TLS Issuer",
        compute="_compute_k8s_config",
        store=False,
        help="Current cert-manager issuer used for TLS certificates",
    )

    # Odoo configuration from Kubernetes
    k8s_config_options = fields.Text(
        string="Current Configuration",
        compute="_compute_k8s_config",
        store=False,
        help="Current Odoo configuration options in YAML format",
    )

    # Kubernetes state fields
    k8s_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("running", "Running"),
            ("error", "Error"),
            ("upgrading", "Upgrading"),
        ],
        string="Kubernetes Status",
        compute="_compute_k8s_state",
        store=False,
    )

    # Upgrade tracking fields
    upgrade_job_name = fields.Char(
        string="Upgrade Job", compute="_compute_k8s_state", store=False
    )
    upgrade_modules = fields.Char(
        string="Modules to Upgrade", compute="_compute_k8s_state", store=False
    )
    upgrade_database = fields.Char(
        string="Database to Upgrade", compute="_compute_k8s_state", store=False
    )
    k8s_status_message = fields.Text(
        string="Kubernetes Status Message", compute="_compute_k8s_state", store=False
    )
    k8s_exists = fields.Boolean(
        string="Exists in Kubernetes", compute="_compute_k8s_state", store=False
    )
    k8s_pods_count = fields.Integer(
        string="Pod Count", compute="_compute_k8s_state", store=False
    )
    k8s_ready_pods_count = fields.Integer(
        string="Ready Pods", compute="_compute_k8s_state", store=False
    )

    # -------------------------------------------------------------------------
    # STORED FIELDS SET BY USER
    # -------------------------------------------------------------------------

    # Docker image configuration set by user
    image = fields.Char(
        string="Desired Image",
        help="Docker image to use for the Odoo instance",
    )
    image_pull_secret = fields.Char(
        string="Desired Pull Secret",
        help="Kubernetes secret containing Docker registry credentials",
    )

    # Resource configuration set by user
    cpu_request = fields.Char(
        string="Desired CPU Request",
        help="CPU request for each Odoo pod (e.g., 200m, 1)",
    )
    memory_request = fields.Char(
        string="Desired Memory Request",
        help="Memory request for each Odoo pod (e.g., 250Mi, 1Gi)",
    )
    cpu_limit = fields.Char(
        string="Desired CPU Limit",
        help="CPU limit for each Odoo pod (e.g., 2000m, 2)",
    )
    memory_limit = fields.Char(
        string="Desired Memory Limit",
        help="Memory limit for each Odoo pod (e.g., 2Gi, 4Gi)",
    )

    # Filestore configuration set by user
    filestore_size = fields.Char(
        string="Desired Filestore Size",
        help="Size of the persistent volume for the filestore",
    )
    filestore_storage_class = fields.Char(
        string="Desired Storage Class",
        help="Storage class used for the filestore persistent volume",
    )

    # Ingress configuration set by user
    host_names = fields.Text(
        string="Desired Host Names",
        help="Comma-separated list of host names for accessing the Odoo instance",
    )
    tls_issuer = fields.Char(
        string="Desired TLS Issuer",
        tracking=True,
        help="The cert-manager issuer to use for TLS certificates",
    )

    # Odoo configuration set by user
    config_options = fields.Text(
        string="Desired Configuration",
        help="Additional Odoo configuration options in YAML format",
    )

    # Admin password for deployment and updates
    master_password = fields.Char(
        string="Admin Password",
        help="Master password for the Odoo instance. This will be used for deployment and updates.",
        copy=False,  # Don't copy when duplicating records
    )

    # Status fields
    # Stored fields for Kubernetes state
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("running", "Running"),
            ("error", "Error"),
            ("upgrading", "Upgrading"),
        ],
        string="Status",
        default="draft",
        readonly=True,
        tracking=True,
        store=True,
    )
    status_message = fields.Text(string="Status Message", readonly=True, store=True)
    last_status_check = fields.Datetime(
        string="Last Status Check", readonly=True, store=True
    )

    @api.model
    def create(self, vals):
        """Override create to set default values from the cluster"""
        # If cluster_id is set but tls_issuer is not, get the default from the cluster
        if vals.get("cluster_id") and not vals.get("tls_issuer"):
            cluster = self.env["k8s.cluster"].browse(vals["cluster_id"])
            vals["tls_issuer"] = cluster.default_tls_issuer

        return super(K8sOdooInstance, self).create(vals)

    # Computed fields for real-time Kubernetes state
    k8s_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("running", "Running"),
            ("error", "Error"),
            ("upgrading", "Upgrading"),
        ],
        string="Kubernetes Status",
        compute="_compute_k8s_state",
        store=False,
    )
    k8s_status_message = fields.Text(
        string="Kubernetes Status Message", compute="_compute_k8s_state", store=False
    )
    k8s_exists = fields.Boolean(
        string="Exists in Kubernetes", compute="_compute_k8s_state", store=False
    )
    k8s_pods_count = fields.Integer(
        string="Pod Count", compute="_compute_k8s_state", store=False
    )
    k8s_ready_pods_count = fields.Integer(
        string="Ready Pods", compute="_compute_k8s_state", store=False
    )

    # URLs
    odoo_url = fields.Char(string="Odoo URL", compute="_compute_odoo_url", store=True)

    # Related records
    upgrade_ids = fields.One2many("k8s.odoo.upgrade", "instance_id", string="Upgrades")

    @api.depends("name", "namespace", "cluster_id")
    def _compute_k8s_config(self):
        """Compute all configuration fields from the Kubernetes OdooInstance resource"""
        for record in self:
            # Reset the read failed flag
            record.k8s_read_failed = False

            # Skip if required fields are missing
            if not record.name or not record.namespace or not record.cluster_id:
                continue

            # Initialize k8s fields with empty values
            record.k8s_image = ""
            record.k8s_image_pull_secret = ""
            record.k8s_cpu_request = ""
            record.k8s_memory_request = ""
            record.k8s_cpu_limit = ""
            record.k8s_memory_limit = ""
            record.k8s_filestore_size = ""
            record.k8s_filestore_storage_class = ""
            record.k8s_host_names = ""
            record.k8s_tls_issuer = ""
            record.k8s_config_options = ""

            # Only initialize desired state fields if they're empty for new records in draft state
            if record.status == "draft":
                if not record.image:
                    record.image = (
                        "docker.bemade.org/bemade/bemade-odoo-empty-18.0:latest"
                    )
                if not record.image_pull_secret:
                    record.image_pull_secret = "docker.bemade.org"
                if not record.cpu_request:
                    record.cpu_request = "200m"
                if not record.memory_request:
                    record.memory_request = "250Mi"
                if not record.cpu_limit:
                    record.cpu_limit = "2000m"
                if not record.memory_limit:
                    record.memory_limit = "2Gi"
                if not record.filestore_size:
                    record.filestore_size = "2Gi"
                if not record.filestore_storage_class:
                    record.filestore_storage_class = "standard"
                if not record.tls_issuer and record.cluster_id:
                    record.tls_issuer = record.cluster_id.default_tls_issuer

            try:
                # Get the Kubernetes client
                api_client = record.cluster_id.get_k8s_client()
                custom_api = kubernetes.client.CustomObjectsApi(api_client)

                # Get the OdooInstance custom resource
                try:
                    instance = custom_api.get_namespaced_custom_object(
                        group="bemade.org",
                        version="v1",
                        namespace=record.namespace,
                        plural="odooinstances",
                        name=record.name,
                    )

                    # Extract configuration values from the OdooInstance resource
                    spec = instance.get("spec", {})

                    # Image configuration
                    if "image" in spec:
                        record.k8s_image = spec["image"]
                    if "imagePullSecrets" in spec and spec["imagePullSecrets"]:
                        record.k8s_image_pull_secret = spec["imagePullSecrets"][0][
                            "name"
                        ]

                    # Resource configuration
                    resources = spec.get("resources", {})
                    if resources:
                        requests = resources.get("requests", {})
                        limits = resources.get("limits", {})

                        if "cpu" in requests:
                            record.k8s_cpu_request = requests["cpu"]
                        if "memory" in requests:
                            record.k8s_memory_request = requests["memory"]
                        if "cpu" in limits:
                            record.k8s_cpu_limit = limits["cpu"]
                        if "memory" in limits:
                            record.k8s_memory_limit = limits["memory"]

                    # Filestore configuration
                    if "filestore" in spec:
                        filestore = spec["filestore"]
                        if "size" in filestore:
                            record.k8s_filestore_size = filestore["size"]
                        if "storageClass" in filestore:
                            record.k8s_filestore_storage_class = filestore[
                                "storageClass"
                            ]

                    # Ingress configuration
                    if "ingress" in spec:
                        ingress = spec["ingress"]
                        if "hosts" in ingress:
                            record.k8s_host_names = ", ".join(ingress["hosts"])
                        if "tlsIssuer" in ingress:
                            record.k8s_tls_issuer = ingress["tlsIssuer"]

                    # Odoo configuration
                    if "config" in spec:
                        record.k8s_config_options = yaml.safe_dump(spec["config"])

                    # Initialize desired state fields if they're empty (for new records)
                    if record.status == "draft":
                        if not record.image:
                            record.image = record.k8s_image
                        if not record.image_pull_secret:
                            record.image_pull_secret = record.k8s_image_pull_secret
                        if not record.cpu_request:
                            record.cpu_request = record.k8s_cpu_request
                        if not record.memory_request:
                            record.memory_request = record.k8s_memory_request
                        if not record.cpu_limit:
                            record.cpu_limit = record.k8s_cpu_limit
                        if not record.memory_limit:
                            record.memory_limit = record.k8s_memory_limit
                        if not record.filestore_size:
                            record.filestore_size = record.k8s_filestore_size
                        if not record.filestore_storage_class:
                            record.filestore_storage_class = (
                                record.k8s_filestore_storage_class
                            )
                        if not record.host_names:
                            record.host_names = record.k8s_host_names
                        if not record.tls_issuer:
                            record.tls_issuer = record.k8s_tls_issuer
                        if not record.config_options:
                            record.config_options = record.k8s_config_options

                except ApiException as e:
                    record.k8s_read_failed = True
                    if e.status != 404:  # Ignore 404 errors
                        _logger.error(f"Error fetching OdooInstance {record.name}: {e}")

            except Exception as e:
                record.k8s_read_failed = True
                _logger.error(
                    f"Error computing Kubernetes config for {record.name}: {e}"
                )

    @api.depends("host_names")
    def _compute_odoo_url(self):
        for instance in self:
            if instance.host_names:
                # Use the first host name as the primary URL
                hosts = [h.strip() for h in instance.host_names.split(",")]
                if hosts:
                    instance.odoo_url = f"https://{hosts[0]}"
                else:
                    instance.odoo_url = False
            else:
                instance.odoo_url = False

    @api.constrains("name", "namespace")
    def _check_name_namespace(self):
        for instance in self:
            if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", instance.name):
                raise ValidationError(
                    _(
                        "Instance name must consist of lowercase alphanumeric characters or '-', and must start and end with an alphanumeric character."
                    )
                )

            if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", instance.namespace):
                raise ValidationError(
                    _(
                        "Namespace must consist of lowercase alphanumeric characters or '-', and must start and end with an alphanumeric character."
                    )
                )

    @api.constrains("config_options")
    def _check_config_options(self):
        for instance in self:
            if instance.config_options:
                try:
                    yaml.safe_load(instance.config_options)
                except Exception as e:
                    raise ValidationError(
                        _("Invalid YAML format in configuration options: %s") % str(e)
                    )

    def _prepare_odoo_instance_spec(self):
        """Prepare the OdooInstance spec for Kubernetes

        This method prepares the spec for both instance creation and updates.

        Returns:
            dict: The spec for the OdooInstance custom resource
        """
        # Prepare host names
        host_names = []
        if self.host_names:
            host_names = [h.strip() for h in self.host_names.split(",")]

        # Parse config options
        config_options = {}
        if self.config_options:
            config_options = yaml.safe_load(self.config_options)

        # Create the base spec
        spec = {
            "image": self.image,
            "resources": {
                "requests": {
                    "cpu": self.cpu_request,
                    "memory": self.memory_request,
                },
                "limits": {"cpu": self.cpu_limit, "memory": self.memory_limit},
            },
            "filestore": {
                "size": self.filestore_size,
                "storageClass": self.filestore_storage_class,
            },
            "ingress": {"hosts": host_names, "tlsIssuer": self.tls_issuer},
            "config": config_options,
        }

        # Add admin password if provided
        if self.master_password:
            spec["adminPassword"] = self.master_password

        # Add image pull secret if specified
        if self.image_pull_secret:
            spec["imagePullSecrets"] = [{"name": self.image_pull_secret}]

        return spec

    def action_deploy(self):
        """Deploy the Odoo instance to Kubernetes using the stored master password"""
        self.ensure_one()

        if self.status not in ("draft", "error"):
            raise UserError(_("You can only deploy instances in draft or error state."))

        if not self.master_password:
            raise UserError(
                _("Please set the admin password before deploying the instance.")
            )

        try:
            # Get the Kubernetes client
            api_client = self.cluster_id.get_k8s_client()
            custom_api = self.cluster_id._get_custom_objects_api()

            # Create the OdooInstance custom resource
            odoo_instance = {
                "apiVersion": "bemade.org/v1",
                "kind": "OdooInstance",
                "metadata": {"name": self.name, "namespace": self.namespace},
                "spec": self._prepare_odoo_instance_spec(),
            }

            # Create the OdooInstance in Kubernetes
            custom_api.create_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                body=odoo_instance,
            )

            # Update the status and clear the master password
            self.write(
                {
                    "status": "pending",
                    "status_message": _("Instance deployment initiated"),
                    "last_status_check": fields.Datetime.now(),
                    "master_password": False,  # Clear the password after deployment
                }
            )

            # Schedule a status check
            self.env.ref(
                "bemade_k8s_odoo_manager.ir_cron_check_instance_status"
            ).method_direct_trigger()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deployment Started"),
                    "message": _(
                        "Odoo instance deployment has been initiated. It may take a few minutes to complete."
                    ),
                    "sticky": False,
                    "type": "success",
                },
            }

        except ApiException as e:
            error_message = f"API Error: {e.reason}"
            self.write(
                {
                    "status": "error",
                    "status_message": error_message,
                    "last_status_check": fields.Datetime.now(),
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deployment Failed"),
                    "message": error_message,
                    "sticky": False,
                    "type": "danger",
                },
            }

        except Exception as e:
            error_message = f"Error: {str(e)}"
            self.write(
                {
                    "status": "error",
                    "status_message": error_message,
                    "last_status_check": fields.Datetime.now(),
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deployment Failed"),
                    "message": error_message,
                    "sticky": False,
                    "type": "danger",
                },
            }

    def action_refresh_status(self):
        """Manually refresh the status of the instance"""
        self.ensure_one()

        # First compute the current Kubernetes state
        self._compute_k8s_state()
        # Also compute the current Kubernetes configuration
        self._compute_k8s_config()

        # Then update the stored fields with the computed values
        self.write(
            {
                "status": self.k8s_status,
                "status_message": self.k8s_status_message,
                "last_status_check": fields.Datetime.now(),
            }
        )

        # Determine notification type based on status
        notification_type = "info"
        if self.k8s_status == "running":
            notification_type = "success"
        elif self.k8s_status == "error":
            notification_type = "danger"
        elif self.k8s_status == "upgrading":
            notification_type = "warning"

        # Prepare a detailed message
        message = _("Status refreshed from Kubernetes: %s") % self.k8s_status_message
        if self.k8s_exists:
            message += _(". Pods: %s/%s ready") % (
                self.k8s_ready_pods_count,
                self.k8s_pods_count,
            )

        # Return a notification to the user
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Kubernetes Status: %s") % self.k8s_status.capitalize(),
                "message": message,
                "sticky": False,
                "type": notification_type,
            },
        }

    def has_config_changes(self):
        """Check if there are any configuration changes to apply"""
        self.ensure_one()

        # Make sure we have the latest Kubernetes configuration
        self._compute_k8s_config()

        # If reading from Kubernetes failed, we can't determine changes
        if self.k8s_read_failed:
            return False

        # Check for differences between desired and current state
        return (
            self.image != self.k8s_image
            or self.image_pull_secret != self.k8s_image_pull_secret
            or self.cpu_request != self.k8s_cpu_request
            or self.memory_request != self.k8s_memory_request
            or self.cpu_limit != self.k8s_cpu_limit
            or self.memory_limit != self.k8s_memory_limit
            or self.filestore_size != self.k8s_filestore_size
            or self.filestore_storage_class != self.k8s_filestore_storage_class
            or self.host_names != self.k8s_host_names
            or self.tls_issuer != self.k8s_tls_issuer
            or self.config_options != self.k8s_config_options
        )

    def get_config_changes(self):
        """Get a dictionary of configuration changes"""
        self.ensure_one()

        # Make sure we have the latest Kubernetes configuration
        self._compute_k8s_config()

        changes = {}

        if self.image != self.k8s_image:
            changes["image"] = {"current": self.k8s_image, "desired": self.image}

        if self.image_pull_secret != self.k8s_image_pull_secret:
            changes["image_pull_secret"] = {
                "current": self.k8s_image_pull_secret,
                "desired": self.image_pull_secret,
            }

        if self.cpu_request != self.k8s_cpu_request:
            changes["cpu_request"] = {
                "current": self.k8s_cpu_request,
                "desired": self.cpu_request,
            }

        if self.memory_request != self.k8s_memory_request:
            changes["memory_request"] = {
                "current": self.k8s_memory_request,
                "desired": self.memory_request,
            }

        if self.cpu_limit != self.k8s_cpu_limit:
            changes["cpu_limit"] = {
                "current": self.k8s_cpu_limit,
                "desired": self.cpu_limit,
            }

        if self.memory_limit != self.k8s_memory_limit:
            changes["memory_limit"] = {
                "current": self.k8s_memory_limit,
                "desired": self.memory_limit,
            }

        if self.filestore_size != self.k8s_filestore_size:
            changes["filestore_size"] = {
                "current": self.k8s_filestore_size,
                "desired": self.filestore_size,
            }

        if self.filestore_storage_class != self.k8s_filestore_storage_class:
            changes["filestore_storage_class"] = {
                "current": self.k8s_filestore_storage_class,
                "desired": self.filestore_storage_class,
            }

        if self.host_names != self.k8s_host_names:
            changes["host_names"] = {
                "current": self.k8s_host_names,
                "desired": self.host_names,
            }

        if self.tls_issuer != self.k8s_tls_issuer:
            changes["tls_issuer"] = {
                "current": self.k8s_tls_issuer,
                "desired": self.tls_issuer,
            }

        if self.config_options != self.k8s_config_options:
            changes["config_options"] = {
                "current": self.k8s_config_options,
                "desired": self.config_options,
            }

        return changes

    def action_apply_changes(self):
        """Apply configuration changes to Kubernetes"""
        self.ensure_one()

        # Make sure we have the latest Kubernetes configuration
        self._compute_k8s_config()

        # Check if reading from Kubernetes failed
        if self.k8s_read_failed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cannot Apply Changes"),
                    "message": _(
                        "Unable to read current configuration from Kubernetes. Please check your connection and try again."
                    ),
                    "sticky": True,
                    "type": "danger",
                },
            }

        if not self.has_config_changes():
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Changes"),
                    "message": _("There are no configuration changes to apply."),
                    "sticky": False,
                    "type": "info",
                },
            }

        # Get the Kubernetes client
        api_client = self.cluster_id.get_k8s_client()
        custom_api = kubernetes.client.CustomObjectsApi(api_client)

        try:
            # Get the current OdooInstance resource
            instance = custom_api.get_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
            )

            # Replace the spec with our desired values
            instance["spec"] = self._prepare_odoo_instance_spec()

            # Update the OdooInstance resource
            custom_api.replace_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
                body=instance,
            )

            # Update the status and clear the master password
            self.write(
                {
                    "status": "upgrading",
                    "status_message": _("Configuration changes are being applied"),
                    "last_status_check": fields.Datetime.now(),
                    "master_password": False,  # Clear the password after applying changes
                }
            )

            # Return a success notification
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Changes Applied"),
                    "message": _(
                        "Configuration changes are being applied to the Kubernetes instance."
                    ),
                    "sticky": False,
                    "type": "success",
                },
            }

        except ApiException as e:
            # Return an error notification
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error"),
                    "message": _("Failed to apply changes: %s") % str(e),
                    "sticky": True,
                    "type": "danger",
                },
            }

    def action_view_upgrades(self):
        """View upgrades related to this instance"""
        self.ensure_one()

        return {
            "name": _("Upgrades"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.odoo.upgrade",
            "view_mode": "tree,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {
                "default_instance_id": self.id,
            },
        }

    def _check_instance_status(self):
        """Check the status of the Odoo instance in Kubernetes and update stored fields"""
        self.ensure_one()

        # First compute the current Kubernetes state
        self._compute_k8s_state()

        # Then update the stored fields with the computed values
        self.write(
            {
                "status": self.k8s_status,
                "status_message": self.k8s_status_message,
                "last_status_check": fields.Datetime.now(),
            }
        )

    @api.depends("name", "namespace", "cluster_id")
    def _compute_k8s_state(self):
        """Compute the current state from Kubernetes"""
        for record in self:
            # Initialize with default/fallback values
            k8s_status = record.status
            k8s_status_message = record.status_message or ""
            k8s_exists = False
            k8s_pods_count = 0
            k8s_ready_pods_count = 0

            # Skip if in draft state or no cluster configured
            if record.status == "draft" or not record.cluster_id:
                record.k8s_status = k8s_status
                record.k8s_status_message = k8s_status_message
                record.k8s_exists = k8s_exists
                record.k8s_pods_count = k8s_pods_count
                record.k8s_ready_pods_count = k8s_ready_pods_count
                continue

            try:
                # Get the Kubernetes client
                api_client = record.cluster_id.get_k8s_client()
                custom_api = kubernetes.client.CustomObjectsApi(api_client)
                core_api = kubernetes.client.CoreV1Api(api_client)

                # Get the OdooInstance custom resource
                try:
                    instance = custom_api.get_namespaced_custom_object(
                        group="bemade.org",
                        version="v1",
                        namespace=record.namespace,
                        plural="odooinstances",
                        name=record.name,
                    )
                    k8s_exists = True
                except ApiException as e:
                    if e.status == 404:
                        k8s_status = "draft"
                        k8s_status_message = _("Instance not found in Kubernetes")
                        record.k8s_status = k8s_status
                        record.k8s_status_message = k8s_status_message
                        record.k8s_exists = k8s_exists
                        record.k8s_pods_count = k8s_pods_count
                        record.k8s_ready_pods_count = k8s_ready_pods_count
                        continue
                    else:
                        raise

                # Check if there's an upgrade job running
                upgrade_job = None
                try:
                    # Look for a job with the name pattern 'odoo-upgrade-{instance_name}-*'
                    job_prefix = f"odoo-upgrade-{record.name}-"
                    jobs = custom_api.list_namespaced_custom_object(
                        group="batch",
                        version="v1",
                        namespace=record.namespace,
                        plural="jobs",
                        label_selector=f"app=odoo-upgrade,instance={record.name}",
                    )

                    # Get all matching jobs and sort by creation timestamp (newest first)
                    matching_jobs = []
                    for job in jobs.get("items", []):
                        job_name = job["metadata"]["name"]
                        if job_name.startswith(job_prefix):
                            # Extract creation timestamp for sorting
                            creation_time = job["metadata"].get("creationTimestamp", "")
                            matching_jobs.append((creation_time, job))

                    # Sort jobs by creation timestamp (newest first)
                    if matching_jobs:
                        matching_jobs.sort(key=lambda x: x[0], reverse=True)
                        # Use the most recent job
                        upgrade_job = matching_jobs[0][1]
                except ApiException:
                    # Ignore errors when checking for upgrade jobs
                    pass

                # Check the status of the deployment
                deployment_name = f"odoo-{record.name}"
                try:
                    deployment = core_api.read_namespaced_deployment(
                        name=deployment_name, namespace=record.namespace
                    )
                    available_replicas = deployment.status.available_replicas or 0
                    ready_replicas = deployment.status.ready_replicas or 0
                    replicas = deployment.status.replicas or 0

                    k8s_pods_count = replicas
                    k8s_ready_pods_count = ready_replicas

                    # If an upgrade job is running, it takes precedence over deployment status
                    if upgrade_job:
                        job_status = upgrade_job.get("status", {})
                        job_succeeded = job_status.get("succeeded", 0)
                        job_failed = job_status.get("failed", 0)

                        if job_succeeded > 0:
                            # Upgrade completed successfully
                            k8s_status = "running"
                            k8s_status_message = _("Upgrade completed successfully")
                        elif job_failed > 0:
                            # Upgrade failed
                            k8s_status = "error"
                            k8s_status_message = _("Upgrade failed")
                        else:
                            # Upgrade in progress
                            k8s_status = "upgrading"
                            k8s_status_message = _("Upgrade in progress")
                    elif available_replicas == replicas and ready_replicas == replicas:
                        k8s_status = "running"
                        k8s_status_message = _("Instance is running")
                    else:
                        k8s_status = "pending"
                        k8s_status_message = _(
                            f"Instance is starting up. Ready: {ready_replicas}/{replicas}"
                        )
                except ApiException as e:
                    if e.status == 404:
                        k8s_status = "pending"
                        k8s_status_message = _(
                            "Deployment not found. Instance is being created."
                        )
                    else:
                        raise

            except ApiException as e:
                k8s_status = "error"
                k8s_status_message = f"API Error: {e.reason}"
            except Exception as e:
                k8s_status = "error"
                k8s_status_message = f"Error: {str(e)}"

            record.k8s_status = k8s_status
            record.k8s_status_message = k8s_status_message
            record.k8s_exists = k8s_exists
            record.k8s_pods_count = k8s_pods_count
            record.k8s_ready_pods_count = k8s_ready_pods_count

    def action_delete_kubernetes(self):
        """Delete the Odoo instance from Kubernetes"""
        self.ensure_one()

        if self.status == "draft":
            raise UserError(_("This instance has not been deployed to Kubernetes."))

        try:
            # Get the Kubernetes client
            api_client = self.cluster_id.get_k8s_client()
            custom_api = kubernetes.client.CustomObjectsApi(api_client)

            # Delete the OdooInstance custom resource
            custom_api.delete_namespaced_custom_object(
                group="bemade.org",
                version="v1",
                namespace=self.namespace,
                plural="odooinstances",
                name=self.name,
            )

            # Update the status
            self.write(
                {
                    "status": "draft",
                    "status_message": _("Instance deleted from Kubernetes"),
                    "last_status_check": fields.Datetime.now(),
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deletion Successful"),
                    "message": _("Odoo instance has been deleted from Kubernetes."),
                    "sticky": False,
                    "type": "success",
                },
            }

        except ApiException as e:
            if e.status == 404:
                # If the instance doesn't exist, mark it as draft
                self.write(
                    {
                        "status": "draft",
                        "status_message": _("Instance not found in Kubernetes"),
                        "last_status_check": fields.Datetime.now(),
                    }
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Instance Not Found"),
                        "message": _(
                            "The Odoo instance was not found in Kubernetes. It may have been deleted already."
                        ),
                        "sticky": False,
                        "type": "warning",
                    },
                }
            else:
                error_message = f"API Error: {e.reason}"
                self.write(
                    {
                        "status": "error",
                        "status_message": error_message,
                        "last_status_check": fields.Datetime.now(),
                    }
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Deletion Failed"),
                        "message": error_message,
                        "sticky": False,
                        "type": "danger",
                    },
                }

        except Exception as e:
            error_message = f"Error: {str(e)}"
            self.write(
                {
                    "status": "error",
                    "status_message": error_message,
                    "last_status_check": fields.Datetime.now(),
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deletion Failed"),
                    "message": error_message,
                    "sticky": False,
                    "type": "danger",
                },
            }

    def action_check_status(self):
        """Check the status of the Odoo instance in Kubernetes"""
        self.ensure_one()

        if self.status == "draft":
            raise UserError(_("This instance has not been deployed to Kubernetes."))

        # Compute the current Kubernetes state
        self._compute_k8s_state()

        # Update the stored fields with the computed values
        self.write(
            {
                "status": self.k8s_status,
                "status_message": self.k8s_status_message,
                "last_status_check": fields.Datetime.now(),
            }
        )

        # Determine notification type based on status
        notification_type = "info"
        if self.k8s_status == "running":
            notification_type = "success"
        elif self.k8s_status == "error":
            notification_type = "danger"
        elif self.k8s_status == "upgrading":
            notification_type = "warning"

        # Prepare a detailed message
        message = self.k8s_status_message
        if self.k8s_exists:
            message += _("\nPods: %s/%s ready") % (
                self.k8s_ready_pods_count,
                self.k8s_pods_count,
            )

        # Return a notification to the user
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Kubernetes Status: %s") % self.k8s_status.capitalize(),
                "message": message,
                "sticky": False,
                "type": notification_type,
            },
        }

    def action_schedule_upgrade(self):
        """Schedule an upgrade for this Odoo instance (redirects to simple upgrade)"""
        return self.action_simple_upgrade()

    def action_simple_upgrade(self):
        """Trigger a simple upgrade for this Odoo instance"""
        self.ensure_one()

        return {
            "name": _("Upgrade Odoo Instance"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.odoo.upgrade.simple.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
            },
        }

    def action_open_instance(self):
        """Open the Odoo instance in a new browser tab"""
        self.ensure_one()

        if not self.odoo_url:
            raise UserError(_("No URL available for this instance."))

        return {
            "type": "ir.actions.act_url",
            "url": self.odoo_url,
            "target": "new",
        }

    @api.model
    def _cron_check_instance_status(self):
        """Cron job to check the status of all instances"""
        instances = self.search([])
        for instance in instances:
            try:
                # Compute the current Kubernetes state
                instance._compute_k8s_state()

                # For non-draft instances, update the stored status fields
                if instance.status != "draft" or instance.k8s_exists:
                    instance.write(
                        {
                            "status": instance.k8s_status,
                            "status_message": instance.k8s_status_message,
                            "last_status_check": fields.Datetime.now(),
                        }
                    )

                # Also compute the configuration fields to ensure they're up to date
                instance._compute_k8s_config()

            except Exception as e:
                _logger.error(
                    f"Error checking status for instance {instance.name}: {str(e)}"
                )
                # Continue with the next instance
                continue
