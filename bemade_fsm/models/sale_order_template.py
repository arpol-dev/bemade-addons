# -*- coding: utf-8 -*-
from odoo import fields, models, api


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"
    
    # Champs pour les équipements
    default_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Default Equipment to Service",
        help="The default equipment to service for template lines.",
    )
    
    # Contacts du site et destinataires des ordres de travail
    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_template_site_contacts_rel",
        string="Site Contacts",
    )
    
    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_template_work_order_contacts_rel",
        string="Work Order Recipients",
    )
    
    # Visites
    visit_template_ids = fields.One2many(
        comodel_name="bemade_fsm.visit.template", 
        inverse_name="sale_order_template_id", 
        string="Visit Templates",
        copy=True,
    )
    
    is_fsm = fields.Boolean(
        string="Is FSM",
        compute="_compute_is_fsm",
        store=True,
    )
    
    @api.depends("sale_order_template_line_ids.product_id.is_field_service")
    def _compute_is_fsm(self):
        for rec in self:
            rec.is_fsm = any([line.product_id.is_field_service for line in rec.sale_order_template_line_ids if not line.display_type])


class SaleOrderTemplateLine(models.Model):
    _inherit = "sale.order.template.line"
    
    equipment_ids = fields.Many2many(
        string="Equipment to Service",
        comodel_name="fsm.equipment",
        relation="bemade_fsm_equipment_sale_template_line_rel",
        column1="sale_template_line_id",
        column2="equipment_id",
    )
    
    visit_template_id = fields.Many2one(
        comodel_name="bemade_fsm.visit.template", 
        string="Visit Template",
    )

class BemadeFsmVisitTemplate(models.Model):
    _name = "bemade_fsm.visit.template"
    _description = "Template for FSM Visits"
    
    name = fields.Char(string="Label", required=True)
    sale_order_template_id = fields.Many2one(
        comodel_name="sale.order.template", 
        string="Quotation Template",
        ondelete="cascade",
    )
    
    so_section_template_id = fields.Many2one(
        comodel_name="sale.order.template.line",
        string="Section Line",
    )
