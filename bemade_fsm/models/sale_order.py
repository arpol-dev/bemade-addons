from odoo import fields, models, api, _, Command


class SaleOrder(models.Model):
    _inherit = "sale.order"

    valid_equipment_ids = fields.One2many(
        comodel_name="fsm.equipment",
        related="partner_id.commercial_partner_id.owned_equipment_ids",
    )

    default_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Default Equipment to Service",
        help="The default equipment to service for new sale order lines.",
        compute="_compute_default_equipment",
        inverse="_inverse_default_equipment",
        store=True,
    )

    summary_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Equipment Being Serviced",
        compute="_compute_summary_equipment_ids",
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_site_contacts_rel",
        compute="_compute_default_contacts",
        inverse="_inverse_default_contacts",
        store=True,
    )

    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_work_order_contacts_rel",
        compute="_compute_default_contacts",
        inverse="_inverse_default_contacts",
        string="Work Order Recipients",
        store=True,
    )

    visit_ids = fields.One2many(
        comodel_name="bemade_fsm.visit", inverse_name="sale_order_id", readonly=False
    )

    is_fsm = fields.Boolean(
        compute="_compute_is_fsm",
        string="Is FSM",
        store=True,
    )

    def get_relevant_order_lines(self, task_id):
        self.ensure_one()
        linked_lines = self.order_line.filtered(
            lambda line: line.task_id == task_id
            or line == task_id.visit_id.so_section_id
        )
        visit_lines = linked_lines.filtered(lambda line: line.visit_id)
        for line in visit_lines:
            linked_lines |= line.get_section_line_ids()
        return linked_lines

    @api.depends("order_line.equipment_ids")
    def _compute_summary_equipment_ids(self):
        for rec in self:
            rec.summary_equipment_ids = rec.order_line.mapped("equipment_ids")

    @api.onchange("partner_shipping_id")
    def _onchange_partner_shipping_id(self):
        res = super()._onchange_partner_shipping_id()
        self._compute_default_equipment()
        self._compute_default_contacts()
        return res

    @api.depends("partner_shipping_id")
    def _compute_default_contacts(self):
        for rec in self:
            rec.site_contacts = rec.partner_shipping_id.site_contacts
            rec.work_order_contacts = rec.partner_shipping_id.work_order_contacts

    def _inverse_default_contacts(self):
        pass

    @api.depends(
        "partner_id",
        "partner_shipping_id",
        "partner_shipping_id.equipment_ids",
        "partner_id.owned_equipment_ids",
    )
    def _compute_default_equipment(self):
        for rec in self:
            if rec.partner_shipping_id.equipment_ids:
                ids = rec.partner_shipping_id.equipment_ids
            else:
                ids = rec.partner_id.owned_equipment_ids
            rec.default_equipment_ids = ids if len(ids) < 4 else False

    def _inverse_default_equipment(self):
        pass

    def copy(self, default=None):
        rec = super().copy(default)
        rec.visit_ids = [Command.set(rec.order_line.visit_ids.ids)]
        return rec

    def _create_default_visit(self):
        """Called when an order is confirmed with lines that will create an FSM task,
        in order to make sure there is a visit line grouping all the service being done.
        """
        self.ensure_one()
        visit = self.env["bemade_fsm.visit"].create(
            {
                "label": _("Service Visit"),
                "sale_order_id": self.id,
            }
        )
        # Make sure it goes to the top of the list
        visit.so_section_id.sequence = 0

    def _create_or_organize_visits_if_needed(self):
        """Adds a visit line to the top of the order if there are not already visit
        lines for an order with lines that will create an FSM task."""
        for order in self.filtered("company_id.create_default_fsm_visit"):
            if not order.visit_ids and order.is_fsm:
                order._create_default_visit()
            if order.is_fsm:
                # Make sure that all the lines producing FSM tasks are under a visit
                visit_line_ids = (
                    order.mapped("visit_ids")
                    .mapped("so_section_id")
                    .mapped("section_line_ids")
                )
                if any(
                    [
                        True
                        for line in order.order_line.filtered(
                            lambda line: not line.display_type
                        )
                        if line not in visit_line_ids
                    ]
                ):
                    # If not, promote the first visit to the top of the order items list
                    for line in order.order_line:
                        line.sequence += 1
                    order.mapped("visit_ids").mapped("so_section_id")[0].sequence = 0

    @api.depends("order_line.is_fsm")
    def _compute_is_fsm(self):
        for rec in self:
            rec.is_fsm = any([line.is_fsm for line in rec.order_line])

    def action_confirm(self):
        self._create_or_organize_visits_if_needed()
        return super().action_confirm()

    def write(self, values):
        res = super().write(values)
        if "partner_shipping_id" in values:
            for rec in self:
                rec.tasks_ids.write({"partner_id": rec.partner_shipping_id.id})
        return res

    @api.onchange('sale_order_template_id')
    def _onchange_fsm_sale_order_template_id(self):
        """Ajoute le support des champs FSM lors de l'utilisation d'un modèle de devis.
        Cette méthode est appelée après le traitement standard du modèle de devis.
        """
        if not self.sale_order_template_id:
            return
            
        # Vérifier si le modèle a les attributs FSM (pour éviter les erreurs si module non installé)
        if hasattr(self.sale_order_template_id, 'is_fsm') and self.sale_order_template_id.is_fsm:
            # Copier les contacts du modèle de devis
            if hasattr(self.sale_order_template_id, 'site_contacts'):
                self.site_contacts = self.sale_order_template_id.site_contacts
                
            if hasattr(self.sale_order_template_id, 'work_order_contacts'):
                self.work_order_contacts = self.sale_order_template_id.work_order_contacts
            
            # Copier les équipements par défaut du modèle
            if hasattr(self.sale_order_template_id, 'default_equipment_ids') and self.sale_order_template_id.default_equipment_ids:
                self.default_equipment_ids = self.sale_order_template_id.default_equipment_ids
            
            # Traiter les templates de visite après que toutes les lignes ont été créées
            self._process_fsm_visit_templates()
        
    def _process_fsm_visit_templates(self):
        """Créer des visites à partir des templates de visite du modèle de devis."""
        if not self.sale_order_template_id or not hasattr(self.sale_order_template_id, 'visit_template_ids'):
            return
            
        for visit_template in self.sale_order_template_id.visit_template_ids:
            # Créer une nouvelle visite pour chaque template
            visit = self.env["bemade_fsm.visit"].create({
                "label": visit_template.name,
                "sale_order_id": self.id,
            })
            
            # Dans le contexte d'un modèle de commande, nous devons associer les lignes aux visites
            # d'une façon différente, puisque le lien direct entre les lignes de commande 
            # et les lignes de modèle n'est pas disponible
            
            # Si nous avons une section définie dans le template, nous associons la visite
            # à la première section correspondante de la commande
            if visit_template.so_section_template_id:
                # Trouver une ligne de section avec un nom similaire
                for line in self.order_line.filtered(lambda l: l.display_type == 'line_section'):
                    if line.name == visit_template.so_section_template_id.name:
                        visit.so_section_id = line
                        break
                        
            # Pour les produits, associer au mieux les équipements par correspondance
            # avec le nom ou la description des produits
            for line in self.order_line.filtered(lambda l: not l.display_type):
                # Associer les lignes à la visite si c'est pertinent
                # La logique exacte dépendra de l'implémentation de votre système
                if visit.so_section_id and line.sequence > visit.so_section_id.sequence:
                    # Si la ligne suit la section de la visite, l'associer à cette visite
                    line.visit_id = visit.id
                    
                    # Appliquer les équipements du modèle de devis par défaut
                    if self.default_equipment_ids:
                        line.equipment_ids = self.default_equipment_ids
