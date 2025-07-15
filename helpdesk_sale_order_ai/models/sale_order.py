# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # Add missing_product_count field to avoid view errors
    # This is needed because some views expect this field
    missing_product_count = fields.Integer(
        string='Missing Products Count',
        default=0,
        help='Number of products that could not be found in the database'
    )
    
    # Add has_missing_products field to avoid view errors
    has_missing_products = fields.Boolean(
        string='Has Missing Products',
        default=False,
        help='Whether this sale order has products that could not be found in the database'
    )
    
    # Add ticket_id field to link sale orders to helpdesk tickets
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Helpdesk Ticket',
        readonly=True,
        copy=False,
        help='Helpdesk ticket from which this sale order was created'
    )
