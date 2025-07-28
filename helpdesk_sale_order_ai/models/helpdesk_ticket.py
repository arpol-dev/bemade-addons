# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import re
import shutil
from pathlib import Path

_logger = logging.getLogger(__name__)

# Import the client model to ensure it's loaded
from . import ai_openwebui_client


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # Computed field to determine if team uses AI sale orders
    team_use_ai_sale_orders = fields.Boolean(
        string='Team Uses AI Sale Orders',
        compute='_compute_team_use_ai_sale_orders',
        readonly=True,
    )
    
    ai_generated_products = fields.Text(
        string='AI Generated Products',
        readonly=True,
        help='Products suggested by AI based on ticket description',
    )
    
    @api.depends('team_id')
    def _compute_team_use_ai_sale_orders(self):
        for ticket in self:
            if ticket.team_id:
                ticket.team_use_ai_sale_orders = ticket.team_id._get_use_ai_sale_orders()
            else:
                ticket.team_use_ai_sale_orders = False
    
    def action_convert_to_sale_order(self):
        """Override to use AI if enabled"""
        self.ensure_one()
        
        # Check if AI sale orders are enabled for this team
        if self.team_use_ai_sale_orders:
            return self._ai_convert_to_sale_order()
        
        # Otherwise, use the standard method
        return super(HelpdeskTicket, self).action_convert_to_sale_order()
    
    def _ai_convert_to_sale_order(self):
        """Create a sale order using AI to suggest products based on ticket description"""
        self.ensure_one()

        values = self._get_sale_order_values()
        values["partner_id"] = self.partner_id.id
        
        # Add debug logging
        _logger.debug(f"Sale order values before create: {values}")
        _logger.debug(f"date_order type: {type(values.get('date_order'))}")
        
        # Ensure date_order is set and is a datetime object
        if 'date_order' not in values or not values['date_order']:
            from datetime import datetime
            values['date_order'] = datetime.now()
            _logger.debug(f"Setting default date_order: {values['date_order']}")
        
        # Fix empty string dates by converting them to None
        # This prevents PostgreSQL errors with empty string timestamps
        date_fields = ['date_order', 'commitment_date', 'validity_date']
        for field in date_fields:
            if field in values and values[field] == '':
                values[field] = None
                _logger.debug(f"Converting empty {field} to None")

        # Create the sale order
        sale_order = self.env['sale.order'].create(values)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form,list',
            'context': self.env.context,
        }

    def _get_sale_order_values(self) -> dict:
        """
        Generate sales order values using AI to analyze ticket content, chatter messages, and attachments.
        The AI will identify products from the content and match them to Odoo products using the helper methods.
        
        Returns:
            dict: Values for creating a sales order including order lines
        """
        self.ensure_one()
        _logger.info(f"Generating AI sales order values for ticket {self.id}")
        
        # Get the ticket data
        ticket_data = self._prepare_ai_prompt_data()
        description = ticket_data.get('ticket_description', '')
        chatter_messages = ticket_data.get('ticket_messages', '')
        attachments_info = ticket_data.get('attachments_info', '')
        attachment_contents = ticket_data.get('attachment_contents', '')
        
        # Log the content being analyzed
        _logger.info(f"AI Analysis - Content lengths: Description={len(description)}, Chatter={len(chatter_messages)}, Attachments={len(attachment_contents)}")
        
        # Get the OpenWebUI provider from company settings
        company = self.env.company
        provider = company.openwebui_provider_id
        
        if not provider:
            _logger.error("No OpenWebUI provider configured for company")
            return {"order_line": []}
            
        # Get the OpenWebUI client from the provider
        ai_client = provider.get_client()
        
        # Register the product finding methods as tools
        registry = ai_client.tool_registry
        
        registry.register(
            self._ai_find_product_id_by_name, 
            non_ai_params=["self"],
            description="Find a product by its name and return its ID. Input: name (string) - The name of the product to find. Returns the product ID if found, or null if not found."
        )
        registry.register(
            self._ai_find_product_id_by_code, 
            non_ai_params=["self"],
            description="Find a product by its code/reference and return its ID. Input: code (string) - The code/reference of the product to find. Returns the product ID if found, or null if not found."
        )
        
        # Get attachments
        attachments = self.env['ir.attachment'].search([('res_id', '=', self.id), ('res_model', '=', self._name)])
        attachments_list = []

        # Process PDF files for analysis
        for attachment in attachments:
            if attachment.mimetype == 'application/pdf':
                try:
                    temp_path = f"/tmp/{attachment.name}"
                    shutil.copy(attachment._full_path(attachment.store_fname), temp_path)
                    attachments_list.append(Path(temp_path))
                except Exception as e:
                    _logger.error(f"Error processing attachment {attachment.name}: {e}")
        
        # Create the prompt for the AI
        prompt = f"""IMPORTANT: YOU ARE NOT A CONVERSATIONAL ASSISTANT. YOU ARE A DATA EXTRACTION SYSTEM.
        
        Your ONLY function is to analyze the provided content and return a structured JSON object so that later it can be used to create a sales order.
        DO NOT introduce yourself, explain what you can or cannot do, or engage in conversation.
        ONLY RETURN THE REQUESTED JSON DATA STRUCTURE.
        
        TASK: Extract product information and sales order details from the following content:
        
        Customer Request:
        {description}
        
        Chatter Messages (IMPORTANT - CAREFULLY ANALYZE THESE FOR PRODUCT INFORMATION):
        {chatter_messages}
        
        Attachments Information:
        {attachments_info}
        
        Attachment Contents (CAREFULLY ANALYZE PDF CONTENTS FOR PRODUCT DETAILS):
        {attachment_contents}
        
        WORKFLOW - FOLLOW THESE STEPS EXACTLY:
        1. Identify all products mentioned in the content (product names, codes, references)
        2. For EACH product identified:
           a. If you find a product code/reference, call _ai_find_product_id_by_code with that code
           b. If you only have a product name, call _ai_find_product_id_by_name with that name
           c. Store the returned product ID (or note if not found)
        3. Extract order details (client reference, dates, notes)
        4. Construct the JSON response using the product IDs you obtained from tool calls
        
        RESPONSE FORMAT:
        Your response MUST ONLY be a valid JSON object with the following structure:
        
        {{
            "client_order_ref": "Customer PO number if mentioned",
            "date_order": "YYYY-MM-DD format if a specific order date is mentioned",
            "commitment_date": "YYYY-MM-DD format if a delivery date is mentioned",
            "note": "Any special instructions or notes for the order",
            "order_line": [
                [0, 0, {{
                    "product_id": NUMERIC_ID_FROM_TOOL_CALL,  // Must be an actual ID returned from a tool call
                    "product_uom_qty": QUANTITY,
                    "price_unit": PRICE
                }}],
                [0, 0, {{
                    "display_type": "line_note",
                    "name": "Unmatched product: Product description",
                    "product_uom_qty": 0.0
                }}]
            ]
        }}
        
        CRITICAL RULES:
        1. You MUST use the provided tools for EVERY product mentioned - DO NOT SKIP THIS STEP
        2. product_id MUST be a numeric ID returned by a tool call, NEVER make up IDs
        3. For products not found in the database, use the display_type: 'line_note' format
        4. Include as much detail as possible for unmatched products
        5. Return ONLY valid JSON with no text before or after
        6. DO NOT explain what you're doing or respond conversationally
        7. DO NOT say you can't create a sales order - your job is ONLY to return the JSON data
        IMPORTANT: You must invoke the tools directly using function calling, not just output text that looks like a tool call. Use the provided tools via function calling for _ai_find_product_id_by_code and _ai_find_product_id_by_name.
        """
        
        
        # Call the AI with tools
        try:
            _logger.info("Sending request to AI for sales order generation")
            # First, get the AI's analysis with tool calls to find product IDs
            response = ai_client.chat_with_tools(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction system with access to tools for finding product IDs in an Odoo database. YOU MUST USE THE TOOLS PROVIDED TO ACCURATELY MATCH PRODUCTS PROVIDED TO THE DATABASE. Your ONLY job is to extract product information and return a structured JSON object. DO NOT engage in conversation or explain what you can or cannot do. ONLY return the requested JSON data structure."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                tools=["_ai_find_product_id_by_name", "_ai_find_product_id_by_code"],
                tool_params={},
                max_tool_calls=25,
                files=attachments_list
            )
            _logger.info(f"Received AI response for ticket {self.id}")
            
        except Exception as e:
            _logger.error(f"Error in AI request: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "order_line": [],
                "note": f"AI Error: {str(e)}"
            }
        
        # Process the AI response
        _logger.debug(f"AI response type: {type(response)}")
        
        # The response from chat_with_tools should contain the content directly
        # If it's a dictionary, use it directly
        if isinstance(response, dict):
            _logger.info("AI returned dictionary response, using directly")
            return response
        
        # Handle string responses (extract JSON if possible)
        if isinstance(response, str):
            _logger.info("AI returned text response, attempting to extract JSON")
            try:
                # Look for JSON pattern in the text
                json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
                json_matches = re.findall(json_pattern, response)
                
                if json_matches:
                    response_data = json.loads(json_matches[0])
                    _logger.info("Successfully extracted JSON from text response")
                    return response_data
                elif response.strip().startswith('{') and response.strip().endswith('}'): 
                    response_data = json.loads(response.strip())
                    _logger.info("Successfully parsed direct JSON from text response")
                    return response_data
                else:
                    _logger.error("Could not extract JSON from text response")
                    return {
                        "order_line": [],
                        "note": f"AI returned invalid format: {response[:200]}..."
                    }
            except Exception as parse_error:
                _logger.error(f"Failed to extract JSON from text response: {parse_error}")
                return {
                    "order_line": [],
                    "note": f"AI parsing error: {str(parse_error)}"
                }
        
        # If we get here, the response is in an unexpected format
        _logger.error(f"Unexpected response format: {type(response)}")
        return {
            "order_line": [],
            "note": f"AI returned unexpected format: {type(response)}"
        }
        
    def _prepare_ai_prompt_data(self):
        """
        Extract and prepare all relevant data from the helpdesk ticket for AI analysis.
        This includes ticket description, chatter messages, and attachment contents.
        
        Returns:
            dict: Dictionary containing ticket data for AI analysis
        """
        self.ensure_one()
        _logger.info(f"Preparing AI prompt data for ticket {self.id}")
        
        result = {
            'ticket_description': '',
            'ticket_messages': '',
            'attachments_info': '',
            'attachment_contents': ''
        }
        
        # Get ticket description
        if self.description:
            result['ticket_description'] = self.description
        
        # Get chatter messages
        messages = []
        if self.message_ids:
            for message in self.message_ids:
                if message.body and not message.is_internal:
                    # Skip system messages and focus on actual conversation
                    if not message.author_id or message.author_id.name != 'OdooBot':
                        # Format: [Author] on [Date]: [Message]
                        author = message.author_id.name if message.author_id else 'System'
                        date = message.date.strftime('%Y-%m-%d %H:%M') if message.date else ''
                        # Clean HTML from message body
                        body = re.sub(r'<[^>]+>', ' ', message.body)
                        messages.append(f"[{author}] on {date}: {body}")
        
        result['ticket_messages'] = '\n\n'.join(messages)
        
        # Get attachments
        attachments = self.env['ir.attachment'].search([('res_id', '=', self.id), ('res_model', '=', self._name)])
        attachment_infos = []
        attachment_contents = []
        
        for attachment in attachments:
            # Add attachment metadata
            attachment_infos.append(f"File: {attachment.name} ({attachment.mimetype}, {attachment.file_size} bytes)")
            
            # Extract content from PDFs
            if attachment.mimetype == 'application/pdf':
                try:
                    # Create temporary file
                    temp_path = f"/tmp/{attachment.name}"
                    shutil.copy(attachment._full_path(attachment.store_fname), temp_path)
                    
                    # For PDF extraction, we'll just note the PDF file is present
                    # The actual extraction will be handled by the AI service which has built-in PDF processing
                    attachment_contents.append(f"PDF file: {attachment.name} (will be processed by AI)")
                    
                    # Note: If PDF text extraction is needed directly in Odoo, consider adding:
                    # - A dependency on pdf2text or PyPDF2 in the module manifest
                    # - Implementing the extraction logic here
                except Exception as e:
                    _logger.error(f"Error extracting content from PDF {attachment.name}: {e}")
        
        result['attachments_info'] = '\n'.join(attachment_infos)
        result['attachment_contents'] = '\n\n'.join(attachment_contents)
        
        return result
        
    def _prepare_order_line_values(self, product, quantity, description=""):
        """Prepare values for creating a sale order line"""
        # Create order line with price information
        line_values = {
            'product_id': product.id,
            'product_uom_qty': quantity,
            'name': description or product.name,
        }
        
        # We don't need to set the price here - Odoo will handle this automatically
        # when the sale order line is created with the product
        # Just log the product's list price for debugging
        _logger.info(f"Product {product.name} (ID: {product.id}) has list_price: {product.list_price}")
        
        # We intentionally don't set price_unit here to let Odoo's standard mechanisms handle it
        
        return line_values

    def _ai_find_product_id_by_name(self, product_name: str) -> int | None:
        """Use AI to find a product by name
        
        Args:
            product_name: The name of the product to find
        
        Returns:
            The ID of the product if found, or None if not found
        """
        
        return self.env['product.product'].search([
            ('name', 'ilike', product_name),
            ('sale_ok', '=', True)
        ], limit=1).id

    def _ai_find_product_id_by_code(self, product_reference: str) -> int | None:
        """Use AI to find a product by code
        
        Args:
            product_reference: The code of the product to find
        
        Returns:
            The ID of the product if found, or None if not found
        """

        return self.env['product.product'].search([
            ('default_code', 'ilike', product_reference),
            ('sale_ok', '=', True)
        ], limit=1).id
            