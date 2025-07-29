# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import re
import shutil
from pathlib import Path

_logger = logging.getLogger(__name__)


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
            ticket.team_use_ai_sale_orders = ticket.team_id._get_use_ai_sale_orders() if ticket.team_id else False
    
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
        
        # Ensure date_order is set and is a datetime object
        if 'date_order' not in values or not values['date_order']:
            from datetime import datetime
            values['date_order'] = datetime.now()
        
        # Fix empty string dates by converting them to None
        # This prevents PostgreSQL errors with empty string timestamps
        date_fields = ['date_order', 'commitment_date', 'validity_date']
        for field in date_fields:
            if field in values and values[field] == '':
                values[field] = None

        # Extract unfound products before creating the sale order
        unfound_products = []
        if 'unfound_products' in values:
            unfound_products = values.pop('unfound_products')
            _logger.debug(f"Found {len(unfound_products)} unfound products")

        # Create the sale order
        sale_order = self.env['sale.order'].create(values)
        
        # Link the ticket to the sale order
        sale_order.ticket_id = self.id
        
        # Post original email contents and document information to the chatter
        self._post_source_information_message(sale_order)
        
        # Post message about unfound products if any
        if unfound_products:
            self._post_unfound_products_message(sale_order, unfound_products)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form,list',
            'context': self.env.context,
        }

    def _post_source_information_message(self, sale_order):
        """
        Post a chatter message on the sale order with the original email contents and document information.
        This message will NOT be deleted when the sale order is confirmed, providing permanent context.
        Also attaches the original attachments from the helpdesk ticket to the sale order message.
        
        Args:
            sale_order: The sale order record
        """
        # Get ticket data that was used for AI analysis
        ticket_data = self._prepare_ai_prompt_data()
        description = ticket_data.get('ticket_description', '')
        chatter_messages = ticket_data.get('ticket_messages', '')
        
        # Escape HTML special characters to prevent rendering issues
        import html
        description = html.escape(description)
        chatter_messages = html.escape(chatter_messages)
        
        # Create the message content
        message_body = f"""<div>
<p><strong>🔍 Source Information from Helpdesk Ticket #{self.id}</strong></p>
<p>This sale order was created from helpdesk ticket <a href='/web#id={self.id}&model=helpdesk.ticket&view_type=form'>{self.name}</a></p>
<!-- SOURCE_INFORMATION_MESSAGE -->
"""
        
        # Add original description if available
        if description:
            message_body += f"""<div style='margin-top: 15px;'>
<p><strong>Original Ticket Description:</strong></p>
<pre style='white-space: pre-wrap; background-color: #f8f9fa; padding: 10px; border-radius: 4px;'>{description}</pre>
</div>"""
        
        # Add chatter messages if available (limited to avoid huge messages)
        if chatter_messages:
            # Limit the size of chatter messages to avoid huge messages
            max_chars = 2000
            if len(chatter_messages) > max_chars:
                chatter_messages = chatter_messages[:max_chars] + "... (truncated)"
                
            message_body += f"""<div style='margin-top: 15px;'>
<p><strong>Relevant Chatter Messages:</strong></p>
<pre style='white-space: pre-wrap; background-color: #f8f9fa; padding: 10px; border-radius: 4px;'>{chatter_messages}</pre>
</div>"""
        
        # Get the original attachments from the helpdesk ticket
        attachments = self.env['ir.attachment'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', self._name)
        ])
        
        # Add attachment information to the message
        if attachments:
            message_body += f"""<div style='margin-top: 15px;'>
<p><strong>Attachments:</strong> {len(attachments)} file(s) attached to this message</p>
</div>"""
        
        # Close the main div
        message_body += "</div>"
        
        try:
            _logger.debug(f"Attempting to post source information message for sale order {sale_order.id}")
            
            # Prepare attachment IDs to forward with the message
            attachment_ids = attachments.ids if attachments else []
            _logger.debug(f"Forwarding {len(attachment_ids)} attachments from ticket {self.id} to sale order {sale_order.id}")
            
            # Post the message with attachments
            result = sale_order.message_post(
                body=message_body,
                subject="Source Information",
                body_is_html=True,
                attachment_ids=attachment_ids
            )
            
            _logger.debug(f"Message post result: {result}")
            _logger.debug(f"Successfully posted source information message for sale order {sale_order.id}")
        except Exception as e:
            _logger.error(f"Error posting source information message: {e}")
    
    def _post_unfound_products_message(self, sale_order, unfound_products):
        """
        Post a chatter message on the sale order with information about unfound products.
        This message will be deleted when the sale order is confirmed.
        
        Args:
            sale_order: The sale order record
            unfound_products: List of dictionaries with unfound product information
        """
        if not unfound_products:
            return
            
        # Count unfound products
        missing_count = len(unfound_products)
        
        # Create the message content
        message_body = f"""<p><strong>⚠️ {missing_count} product(s) could not be found in the database:</strong></p>
<ul>
"""
        
        # Add each unfound product to the message
        for product in unfound_products:
            name = product.get('name', 'Unknown')
            quantity = product.get('quantity', 'Unknown')
            reference = product.get('reference', '')
            description = product.get('description', '')
            
            product_info = f"<li><strong>{name}</strong>"
            if reference:
                product_info += f" (Ref: {reference})"
            if quantity != 'Unknown':
                product_info += f" - Quantity: {quantity}"
            product_info += "</li>"
            
            # Add description as a separate indented paragraph with better formatting
            if description:
                product_info += f"""<ul><li style="list-style-type: none; margin-left: -20px;"><em>Description: {description}</em></li></ul>"""
            
            message_body += product_info
            
        message_body += """</ul>
<p><em>This message will be automatically deleted when the sale order is confirmed.</em></p>
<!-- MISSING_PRODUCTS_MESSAGE -->"""  # Special marker for deletion
        
        try:
            # Post the message
            sale_order.message_post(body=message_body, subject="Products Not Found", body_is_html=True)
            
            # Update the sale order flags
            sale_order.write({
                'missing_product_count': missing_count,
                'has_missing_products': True
            })
            
            _logger.debug(f"Posted unfound products message for sale order {sale_order.id} with {missing_count} products")
        except Exception as e:
            _logger.error(f"Error posting unfound products message: {e}")
    
    def _get_sale_order_values(self) -> dict:
        """
        Generate sales order values using AI to analyze ticket content, chatter messages, and attachments.
        The AI will identify products from the content and match them to Odoo products.
        
        Returns:
            dict: Values for creating a sales order including order lines
        """
        self.ensure_one()
        _logger.debug(f"Generating AI sales order values for ticket {self.id}")
        
        # Get the ticket data
        ticket_data = self._prepare_ai_prompt_data()
        description = ticket_data.get('ticket_description', '')
        chatter_messages = ticket_data.get('ticket_messages', '')
        attachments_info = ticket_data.get('attachments_info', '')
        attachment_contents = ticket_data.get('attachment_contents', '')
        
        # Log the content being analyzed
        _logger.debug(f"AI Analysis - Content lengths: Description={len(description)}, Chatter={len(chatter_messages)}, Attachments={len(attachment_contents)}")
        
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
        
        # Process PDF attachments for analysis
        attachments_list = []
        attachments = self.env['ir.attachment'].search([('res_id', '=', self.id), ('res_model', '=', self._name)])
        
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
        
        Attachment Contents (CRITICALLY IMPORTANT - ANALYZE PDF CONTENTS FOR ALL PRODUCT DETAILS):
        {attachment_contents}
        
        WORKFLOW - FOLLOW THESE STEPS EXACTLY:
        1. Identify ONLY ACTUAL PRODUCTS mentioned in the content (product names, codes, references) from BOTH chatter messages AND PDF attachments
        2. For EACH product identified (from BOTH sources):
           a. If you find a product code/reference, call _ai_find_product_id_by_code with that code
           b. If you only have a product name, call _ai_find_product_id_by_name with that name
           c. If the product is not found in the database, use the display_type: 'line_note' format with this EXACT format: "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE if available)"
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
                    "name": "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE)",
                    "product_uom_qty": 0.0
                }}]
            ],
            "unfound_products": [  // IMPORTANT: Include this array with any products that could not be found in the database
                {{
                    "name": "Product name",
                    "quantity": QUANTITY,
                    "reference": "REFERENCE if available",
                    "description": "Additional description if available"
                }}
            ]
        }}
        
        CRITICAL RULES FOR IDENTIFYING PRODUCTS:
        1. A product MUST have AT LEAST ONE of the following to be considered a valid product:
           - A quantity AND a price
           - A specific product code/reference
           - A clearly identifiable product name with quantity
        2. DO NOT identify random descriptions, paragraphs, or sections of text as products
        3. Be aware that some items may have very long descriptions - this doesn't make them separate products
        4. If a product contains subproducts (e.g., a kit or bundle), only identify the MAIN product, not each subproduct
        5. If uncertain whether something is a product or just a description, look for quantity and price indicators
        6. VERY IMPORTANT: Read product descriptions carefully as they often contain critical information to help identify the correct product
        7. For unfound products, capture as much of the description as possible - this helps users identify what the product actually is
        
        CRITICAL RULES FOR RESPONSE:
        1. You MUST use the provided tools for EVERY valid product mentioned in BOTH chatter messages AND PDF attachments
        2. product_id MUST be a numeric ID returned by a tool call, NEVER make up IDs
        3. For products not found in the database, use the display_type: 'line_note' format with this EXACT format: "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE if available)"
        4. Include as much detail as possible for unmatched products including quantity, reference, and description if available
        5. Return ONLY valid JSON with no text before or after
        6. DO NOT explain what you're doing or respond conversationally
        7. DO NOT say you can't create a sales order - your job is ONLY to return the JSON data
        IMPORTANT: You must invoke the tools directly using function calling, not just output text that looks like a tool call. Use the provided tools via function calling for _ai_find_product_id_by_code and _ai_find_product_id_by_name.
        """
        
        
        # Call the AI with tools
        try:
            _logger.debug("Sending request to AI for sales order generation")
            # First, get the AI's analysis with tool calls to find product IDs
            response = ai_client.chat_with_tools(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction system with access to tools for finding product IDs in an Odoo database. YOU MUST USE THE TOOLS PROVIDED TO ACCURATELY MATCH PRODUCTS PROVIDED TO THE DATABASE. Your ONLY job is to extract product information and return a structured JSON object. DO NOT engage in conversation or explain what you can or cannot do. ONLY return the requested JSON data structure. CRITICALLY IMPORTANT: You MUST identify ONLY ACTUAL PRODUCTS mentioned in BOTH chatter messages AND PDF attachments. A valid product MUST have a quantity AND either a price or product code. DO NOT identify random descriptions or paragraphs as products. VERY IMPORTANT: Read product descriptions carefully as they often contain critical information to help identify the correct product. For ANY product that cannot be found in the database, you MUST include it as a line note with display_type: 'line_note' in your response, and include as much description as possible."
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
            _logger.debug(f"Received AI response for ticket {self.id}")
            
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
        
        # If it's a dictionary, use it directly
        if isinstance(response, dict):
            _logger.debug("AI returned dictionary response, using directly")
            response['unfound_products'] = self._extract_unfound_products(response)
            return response
        
        # Handle string responses (extract JSON if possible)
        if isinstance(response, str):
            _logger.debug("AI returned text response, attempting to extract JSON")
            try:
                # Look for JSON pattern in the text
                json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
                json_matches = re.findall(json_pattern, response)
                
                if json_matches:
                    response_data = json.loads(json_matches[0])
                    response_data['unfound_products'] = self._extract_unfound_products(response_data)
                    return response_data
                elif response.strip().startswith('{') and response.strip().endswith('}'): 
                    response_data = json.loads(response.strip())
                    response_data['unfound_products'] = self._extract_unfound_products(response_data)
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
        _logger.debug(f"Preparing AI prompt data for ticket {self.id}")
        
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
            
            # Add PDF content reference
            if attachment.mimetype == 'application/pdf':
                attachment_contents.append(f"IMPORTANT PDF CONTENT: {attachment.name} - The AI must analyze this PDF for ALL product mentions and include ANY products found as either matched products or unmatched line notes")
        
        result['attachments_info'] = '\n'.join(attachment_infos)
        result['attachment_contents'] = '\n\n'.join(attachment_contents)
        
        return result
        
    def _prepare_order_line_values(self, product, quantity, description=""):
        """Prepare values for creating a sale order line"""
        return {
            'product_id': product.id,
            'product_uom_qty': quantity,
            'name': description or product.name,
        }

    def _ai_find_product_id_by_name(self, product_name: str) -> int | None:
        """Find a product by name
        
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
        """Find a product by code
        
        Args:
            product_reference: The code of the product to find
        
        Returns:
            The ID of the product if found, or None if not found
        """
        return self.env['product.product'].search([
            ('default_code', 'ilike', product_reference),
            ('sale_ok', '=', True)
        ], limit=1).id
    
    def _extract_unfound_products(self, response_data):
        """
        Extract information about products that could not be found in the database.
        This method analyzes the AI response to identify products that couldn't be matched.
        
        Args:
            response_data: The AI response data (dictionary)
            
        Returns:
            List of dictionaries with information about unfound products
        """
        unfound_products = []
        
        # Check if response has data
        if not response_data:
            return unfound_products
            
        # First check if there's a dedicated unfound_products array in the response
        if 'unfound_products' in response_data and isinstance(response_data['unfound_products'], list):
            _logger.debug(f"Found unfound_products array in AI response with {len(response_data['unfound_products'])} items")
            for product in response_data['unfound_products']:
                if isinstance(product, dict):
                    product_info = {}
                    
                    # Extract product information from the unfound_products array
                    if 'name' in product:
                        product_info['name'] = product['name']
                    
                    if 'quantity' in product:
                        product_info['quantity'] = float(product['quantity'])
                    
                    if 'reference' in product:
                        product_info['reference'] = product['reference']
                        
                    if product_info and 'name' in product_info:
                        unfound_products.append(product_info)
        
        # Also check for line notes in the order lines (for backward compatibility)
        if 'order_line' in response_data:
            for line in response_data.get('order_line', []):
                # Line format is typically [0, 0, {...}]
                if len(line) >= 3 and isinstance(line[2], dict):
                    line_data = line[2]
                    
                    # Check if this is a line note for an unfound product
                    if line_data.get('display_type') == 'line_note' and 'name' in line_data:
                        name = line_data.get('name', '')
                        
                        # Extract product information from the note
                        if 'Unmatched product:' in name or 'Product not found:' in name:
                            # Parse the product information
                            product_info = {}
                            
                            # Try to extract product name
                            product_name_match = re.search(r'(?:Unmatched product:|Product not found:)\s*([^\(\)\[\],]+)', name)
                            if product_name_match:
                                product_info['name'] = product_name_match.group(1).strip()
                            else:
                                product_info['name'] = name.replace('Unmatched product:', '').replace('Product not found:', '').strip()
                            
                            # Try to extract quantity
                            quantity_match = re.search(r'(?:qty|quantity|Qty|Quantity)[:\s]*(\d+(?:\.\d+)?)', name)
                            if quantity_match:
                                product_info['quantity'] = float(quantity_match.group(1))
                            
                            # Try to extract reference/code
                            ref_match = re.search(r'(?:ref|reference|code)[:\s]*([\w-]+)', name, re.IGNORECASE)
                            if ref_match:
                                product_info['reference'] = ref_match.group(1)
                        
                            # Any remaining text is considered description
                            if 'description' not in product_info:
                                product_info['description'] = ''
                            product_info['description'] += ' ' + name if product_info['description'] else name
                            
                            # Add to the list of unfound products
                            if product_info:
                                unfound_products.append(product_info)
        
        # Return the extracted unfound products
        _logger.debug(f"Extracted {len(unfound_products)} unfound products from AI response")
        return unfound_products