import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sOdooInstance(models.Model):
    _name = "k8s.odoo.instance"
    _description = "Kubernetes Odoo Instance"
    _inherit = ["mail.thread"]
    _order = "cluster_id, namespace, name"

    name = fields.Char(
        string="Instance Name",
        required=True,
        readonly=True,
        help="Name of the OdooInstance resource in Kubernetes",
    )

    cluster_id = fields.Many2one(
        "k8s.cluster",
        string="Cluster",
        required=True,
        readonly=True,
        ondelete="cascade",
    )

    namespace = fields.Char(
        string="Namespace",
        required=True,
        readonly=True,
        help="Kubernetes namespace containing this instance",
    )

    spec = fields.Text(
        string="Specification",
        readonly=True,
        help="Complete OdooInstance specification as JSON",
    )

    status = fields.Text(
        string="Status", readonly=True, help="Current OdooInstance status as JSON"
    )

    phase = fields.Selection(
        [
            ("Running", "Running"),
            ("Upgrading", "Upgrading"),
            ("Restoring", "Restoring"),
            ("Unknown", "Unknown"),
        ],
        string="Phase",
        default="Unknown",
        readonly=True,
        tracking=True,
    )

    url = fields.Char(
        string="URL", readonly=True, help="Access URL for this Odoo instance"
    )

    last_updated = fields.Datetime(
        string="Last Updated",
        readonly=True,
        help="Last time this record was synchronized from Kubernetes",
    )

    # Computed fields from spec
    image = fields.Char(
        string="Docker Image", compute="_compute_spec_fields", store=True
    )

    replicas = fields.Integer(
        string="Replicas", compute="_compute_spec_fields", store=True
    )

    ingress_hosts = fields.Text(
        string="Ingress Hosts", compute="_compute_spec_fields", store=True
    )

    @api.depends("spec")
    def _compute_spec_fields(self):
        """Extract commonly used fields from spec JSON"""
        for instance in self:
            if instance.spec:
                try:
                    spec_data = json.loads(instance.spec)
                    instance.image = spec_data.get("image", "")
                    instance.replicas = spec_data.get("replicas", 0)

                    # Extract ingress hosts
                    ingress = spec_data.get("ingress", {})
                    hosts = ingress.get("hosts", [])
                    instance.ingress_hosts = ", ".join(hosts) if hosts else ""

                except (json.JSONDecodeError, KeyError) as e:
                    _logger.warning(
                        f"Failed to parse spec for instance {instance.name}: {e}"
                    )
                    instance.image = ""
                    instance.replicas = 0
                    instance.ingress_hosts = ""
            else:
                instance.image = ""
                instance.replicas = 0
                instance.ingress_hosts = ""

    def name_get(self):
        """Custom name display"""
        result = []
        for instance in self:
            name = f"{instance.cluster_id.name}/{instance.namespace}/{instance.name}"
            result.append((instance.id, name))
        return result

    def action_open_url(self):
        """Open the Odoo instance URL in a new tab"""
        self.ensure_one()
        if not self.url:
            raise UserError(_("No URL available for this instance"))

        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    def action_view_spec(self):
        """Show the complete specification in a dialog"""
        self.ensure_one()

        if not self.spec:
            raise UserError(_("No specification data available"))

        try:
            # Pretty format the JSON
            spec_data = json.loads(self.spec)
            formatted_spec = json.dumps(spec_data, indent=2)
        except json.JSONDecodeError:
            formatted_spec = self.spec

        return {
            "name": _("Instance Specification"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.spec.viewer",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_title": f"Specification: {self.name}",
                "default_content": formatted_spec,
            },
        }

    def action_view_status(self):
        """Show the complete status in a dialog"""
        self.ensure_one()

        if not self.status:
            raise UserError(_("No status data available"))

        try:
            # Pretty format the JSON
            status_data = json.loads(self.status)
            formatted_status = json.dumps(status_data, indent=2)
        except json.JSONDecodeError:
            formatted_status = self.status

        return {
            "name": _("Instance Status"),
            "type": "ir.actions.act_window",
            "res_model": "k8s.spec.viewer",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_title": f"Status: {self.name}",
                "default_content": formatted_status,
            },
        }

    def action_refresh(self):
        """Refresh this instance from Kubernetes"""
        self.ensure_one()
        return self.cluster_id.sync_odoo_instances()


class K8sSpecViewer(models.TransientModel):
    """Transient model for displaying JSON content in a dialog"""

    _name = "k8s.spec.viewer"
    _description = "Kubernetes Spec/Status Viewer"

    title = fields.Char(string="Title", readonly=True)
    content = fields.Text(string="Content", readonly=True)
