# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

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
    
    def action_confirm(self):
        """Override to delete missing products message when sale order is confirmed"""
        # Call the original method first
        result = super(SaleOrder, self).action_confirm()
        
        # Delete missing products message if exists
        if self.has_missing_products:
            self._delete_missing_products_message()
            
            # Reset missing products flags
            self.write({
                'missing_product_count': 0,
                'has_missing_products': False
            })
            
        return result
    
    def _delete_missing_products_message(self):
        """Delete the missing products message from the chatter"""
        # Find the message with the unique identifier
        domain = [
            ('res_id', '=', self.id),
            ('model', '=', 'sale.order'),
            ('body', 'ilike', '%<!-- MISSING_PRODUCTS_MESSAGE -->%'),
        ]
        
        messages = self.env['mail.message'].sudo().search(domain)
        
        if messages:
            _logger.info(f"Found {len(messages)} missing products message(s) for sale order {self.id} with IDs: {messages.ids}")
            try:
                # Make sure we're actually deleting the message
                message_ids = messages.ids  # Store IDs before deletion
                messages.sudo().unlink()
                _logger.info(f"Successfully deleted missing products message(s) with IDs: {message_ids} for sale order {self.id}")
            except Exception as e:
                _logger.error(f"Error deleting missing products message: {e}")
        else:
            _logger.warning(f"No missing products message found for sale order {self.id} - check HTML comment marker")
            
            # Debug: Try a broader search to see if there are any messages at all
            all_messages = self.env['mail.message'].sudo().search([
                ('res_id', '=', self.id),
                ('model', '=', 'sale.order'),
            ], limit=5)
            
            if all_messages:
                _logger.info(f"Found {len(all_messages)} recent messages for this sale order. First message body sample: {all_messages[0].body[:100] if all_messages[0].body else 'Empty'}...")
            else:
                _logger.info(f"No messages found at all for sale order {self.id}")


