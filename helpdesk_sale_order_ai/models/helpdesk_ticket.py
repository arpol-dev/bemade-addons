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


        # Create the sale order
        sale_order = self.env['sale.order'].create(values)
        
        # Link the ticket to the sale order
        sale_order.ticket_id = self.id
        
        # Post original email contents and document information to the chatter
        self._post_source_information_message(sale_order)
        


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
        # STEP 1: Extract potential products from ticket content and attachments
        _logger.debug("Step 1: Extracting potential products from ticket content and attachments")
        potential_products = self._ai_extract_potential_products(ticket_data)
        _logger.debug(f"Step 1 result - Potential products: {potential_products}")
        
        # If no potential products found, return empty order
        if not potential_products:
            _logger.warning("No potential products found in ticket content")
            return {
                "order_line": [],
                "note": "No products identified in ticket content"
            }
        
        # STEP 2: Match extracted products to database products using tools
        _logger.debug("Step 2: Matching extracted products to database products")
        matched_products = self._ai_match_products_to_database(potential_products)
        _logger.debug(f"Step 2 result - Matched products: {matched_products}")
        
        # If no matched products, return empty order
        if not matched_products:
            _logger.warning("No products could be matched to database")
            return {
                "order_line": [],
                "note": "No products could be matched to database"
            }
        
        # STEP 3: Format the matched products into final JSON structure
        _logger.debug("Step 3: Formatting matched products into final sales order structure")
        final_order = self._ai_format_final_sale_order(matched_products, ticket_data)
        _logger.debug(f"Step 3 result - Final order: {final_order}")
        
        # Return the final formatted sales order
        return final_order
        
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
            # Add text file content reference
            elif attachment.mimetype == 'text/plain':
                attachment_contents.append(f"IMPORTANT TEXT CONTENT: {attachment.name} - The AI must analyze this text file for ALL product mentions and include ANY products found as either matched products or unmatched line notes")
        
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
    
    def _ai_extract_potential_products(self, ticket_data: dict) -> list:
        """
        First AI call: Extract potential products from ticket content and attachments.
        Only this step will have access to the files/attachments.
        
        Args:
            ticket_data (dict): Dictionary containing ticket description, messages, and attachment info
            
        Returns:
            list: List of potential products identified by the AI
        """
        self.ensure_one()
        _logger.debug("Starting Step 1: Extracting potential products")
        
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
            return []
            
        # Get the OpenWebUI client from the provider
        ai_client = provider.get_client()
        
        # Process PDF and text attachments for analysis
        attachments_list = []
        attachments = self.env['ir.attachment'].search([('res_id', '=', self.id), ('res_model', '=', self._name)])
        
        # Upload PDF and text attachments to OpenWebUI
        uploaded_files = []
        for attachment in attachments:
            if attachment.mimetype in ['application/pdf', 'text/plain']:
                try:
                    temp_path = Path(f"/tmp/{attachment.name}")
                    shutil.copy(attachment._full_path(attachment.store_fname), str(temp_path))
                    # Upload the file to OpenWebUI and get a FileObject with id
                    file_object = ai_client.files.from_path(temp_path)
                    uploaded_files.append(file_object)
                    # Clean up temporary file
                    temp_path.unlink(missing_ok=True)
                except Exception as e:
                    _logger.error(f"Error processing attachment {attachment.name}: {e}")
                    import traceback
                    _logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Create the prompt for the AI to extract potential products
        prompt = f"""IMPORTANT: YOU ARE NOT A CONVERSATIONAL ASSISTANT. YOU ARE A DATA EXTRACTION SYSTEM.
        
        Your ONLY function is to analyze the provided content and return a list of potential products.
        DO NOT introduce yourself, explain what you can or cannot do, or engage in conversation.
        ONLY RETURN THE REQUESTED JSON DATA STRUCTURE.
        
        TASK: Extract ALL potential products mentioned in the following content:
        
        Customer Request:
        {description}
        
        Chatter Messages (IMPORTANT - CAREFULLY ANALYZE THESE FOR PRODUCT INFORMATION):
        {chatter_messages}
        
        Attachments Information:
        {attachments_info}
        
        Attachment Contents (CRITICALLY IMPORTANT - ANALYZE PDF AND TEXT CONTENTS FOR ALL PRODUCT DETAILS):
        {attachment_contents}
        
        WORKFLOW - FOLLOW THESE STEPS EXACTLY:
        1. Identify ALL potential products mentioned in the content (product names, codes, references) from BOTH chatter messages AND attachments
        2. For EACH potential product identified:
           a. Extract the product name
           b. Extract the product's default code
           c. Extract any quantity information
           d. Extract any price information
           e. Extract any additional description
        3. Return a structured JSON list of all potential products
        
        RESPONSE FORMAT:
        Your response MUST ONLY be a valid JSON array with the following structure:
        
        [
            {{
                "name": "Product name",
                "default_code": "Product default code",
                "quantity": "Quantity if mentioned (number or text)",
                "price": "Price if mentioned"
            }},
            ...
        ]
        
        CRITICAL RULES FOR IDENTIFYING PRODUCTS:
        1. A potential product is ANYTHING that could be a product - be liberal in identification
        2. If a product's default code is explicitly mentioned (often in brackets or as a standalone identifier), put it in the "default_code" field
        3. If only a product name is mentioned, put it in the "name" field
        4. DO NOT include descriptions in the "name" field - only use actual product names or references
        5. DO NOT include a "description" field - it's not needed for product matching
        6. DO NOT filter or validate products at this stage - that will happen later
        7. Return ONLY valid JSON with no text before or after
        8. DO NOT explain what you're doing or respond conversationally
        
        IMPORTANT: Include EVERYTHING that might be a product, even if uncertain.
        """
        
        # Call the AI to extract potential products
        try:
            _logger.debug("Sending request to AI for product extraction")
            response = ai_client.chat.completions.create(
                model=provider.default_model_id.technical_name if provider.default_model_id else None,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction system. Your ONLY job is to extract ALL potential products mentioned in the provided content and return them in a structured JSON format. Be liberal in identifying potential products - include anything that might be a product."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False,
                files=uploaded_files
            )
            _logger.debug(f"Received AI response for product extraction")
            
        except Exception as e:
            _logger.error(f"Error in AI product extraction request: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        
        # Process the AI response
        _logger.debug(f"AI product extraction response type: {type(response)}")
        
        # Add detailed logging of the response content
        try:
            response_content = response.choices[0].message.content if hasattr(response, 'choices') else str(response)
            _logger.debug(f"AI product extraction response content: {response_content[:1000]}...")
        except:
            _logger.debug("Could not serialize AI product extraction response for logging")
        
        # Extract the content from the response
        response_content = response.choices[0].message.content if hasattr(response, 'choices') else str(response)
        
        # Handle string responses (extract JSON if possible)
        if isinstance(response_content, str):
            _logger.debug("AI returned text response, attempting to extract JSON")
            try:
                # Look for JSON pattern in the text
                json_pattern = r'```(?:json)?\s*(\[[\s\S]*?\]|{[\s\S]*?})\s*```'
                json_matches = re.findall(json_pattern, response_content)
                
                if json_matches:
                    response_data = json.loads(json_matches[0])
                    return response_data if isinstance(response_data, list) else [response_data]
                elif response_content.strip().startswith('[') and response_content.strip().endswith(']'): 
                    response_data = json.loads(response_content.strip())
                    return response_data if isinstance(response_data, list) else [response_data]
                elif response_content.strip().startswith('{') and response_content.strip().endswith('}'): 
                    response_data = json.loads(response_content.strip())
                    return [response_data]
                else:
                    _logger.error("Could not extract JSON from text response")
                    return []
            except Exception as parse_error:
                _logger.error(f"Failed to extract JSON from text response: {parse_error}")
                return []
        
        # If we get here, the response is in an unexpected format
        _logger.error(f"Unexpected response format: {type(response_content)}")
        return []
    
    def _ai_match_products_to_database(self, potential_products: list) -> list:
        """
        Second AI call: Match extracted products to database products using tools.
        This step will not have access to files/attachments.
        
        Args:
            potential_products (list): List of potential products from the first step
            
        Returns:
            list: List of matched products with database IDs or unmatched product notes
        """
        self.ensure_one()
        _logger.debug("Starting Step 2: Matching products to database")
        _logger.debug(f"Input products to match: {potential_products}")
        
        # Get the OpenWebUI provider from company settings
        company = self.env.company
        provider = company.openwebui_provider_id
        
        if not provider:
            _logger.error("No OpenWebUI provider configured for company")
            return []
            
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
        
        # Create the prompt for the AI to match products
        products_json = json.dumps(potential_products, indent=2)
        
        prompt = f"""IMPORTANT: YOU ARE NOT A CONVERSATIONAL ASSISTANT. YOU ARE A DATA PROCESSING SYSTEM.
        
        Your ONLY function is to match the provided potential products to actual database products using the available tools.
        DO NOT introduce yourself, explain what you can or cannot do, or engage in conversation.
        ONLY RETURN THE REQUESTED JSON DATA STRUCTURE.
        
        TASK: Match the following potential products to actual database products:
        
        Potential Products:
        {products_json}
        
        WORKFLOW - FOLLOW THESE STEPS EXACTLY: 
        1. For EACH potential product:
           a. If the product has a code/reference, call _ai_find_product_id_by_code with that code
           b. If the product has a name, call _ai_find_product_id_by_name with that name
           c. If the product is not found in the database, create a line note entry
        2. Return a structured JSON list of matched products and line notes
        
        RESPONSE FORMAT:
        Your response MUST ONLY be a valid JSON array with the following structure:
        
        [
            {{
                "product_id": NUMERIC_ID_FROM_TOOL_CALL,  // Must be an actual ID returned from a tool call
                "product_uom_qty": QUANTITY,
                "price_unit": PRICE,
                "name": "Product name (for reference)"
            }},
            {{
                "display_type": "line_note",
                "name": "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE if available)",
                "product_uom_qty": 0.0
            }},
            ...
        ]
        
        CRITICAL RULES FOR MATCHING:
        1. You MUST use the provided tools for EVERY potential product
        2. product_id MUST be a numeric ID returned by a tool call, NEVER make up IDs
        3. For products not found in the database, use the display_type: 'line_note' format with this EXACT format: "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE if available)"
        4. Include as much detail as possible for unmatched products including quantity, reference, and description if available
        5. Return ONLY valid JSON with no text before or after
        6. DO NOT explain what you're doing or respond conversationally
        
        IMPORTANT: You must invoke the tools directly using function calling, not just output text that looks like a tool call.
        """
        
        # Call the AI with tools to match products
        try:
            _logger.debug("Sending request to AI for product matching")
            response = ai_client.chat_with_tools(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data processing system with access to tools for finding product IDs in an Odoo database. Your ONLY job is to match the provided potential products to actual database products using the available tools. For ANY product that cannot be found in the database, you MUST include it as a line note with display_type: 'line_note' in your response."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                tools=["_ai_find_product_id_by_name", "_ai_find_product_id_by_code"],
                tool_params={},
                max_tool_calls=25
            )
            _logger.debug(f"Received AI response for product matching")
            
        except Exception as e:
            _logger.error(f"Error in AI product matching request: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        
        # Process the AI response
        _logger.debug(f"AI product matching response type: {type(response)}")
        
        # Add detailed logging of the response content
        try:
            _logger.debug(f"AI product matching response content: {json.dumps(response, indent=2)[:1000]}...")
        except:
            _logger.debug("Could not serialize AI product matching response for logging")
        
        # If it's a dictionary, use it directly
        if isinstance(response, dict):
            _logger.debug("AI returned dictionary response, using directly")
            # Check if it's a single object that should be in a list
            if 'product_id' in response or 'display_type' in response:
                return [response]
            return response
        
        # Handle string responses (extract JSON if possible)
        if isinstance(response, str):
            _logger.debug("AI returned text response, attempting to extract JSON")
            try:
                # Look for JSON pattern in the text
                json_pattern = r'```(?:json)?\s*(\[[\s\S]*?\]|{[\s\S]*?})\s*```'
                json_matches = re.findall(json_pattern, response)
                
                if json_matches:
                    response_data = json.loads(json_matches[0])
                    return response_data if isinstance(response_data, list) else [response_data]
                if response.strip().startswith('[') and response.strip().endswith(']'): 
                    response_data = json.loads(response.strip())
                    return [response_data]
                elif response.strip().startswith('{') and response.strip().endswith('}'): 
                    response_data = json.loads(response.strip())
                    return [response_data]
                else:
                    _logger.error("Could not extract JSON from text response")
                    return []
            except Exception as parse_error:
                _logger.error(f"Failed to extract JSON from text response: {parse_error}")
                return []
        
        # If it's already a list, return it
        if isinstance(response, list):
            return response
        
        # If we get here, the response is in an unexpected format
        _logger.error(f"Unexpected response format: {type(response)}")
        return []
    
    def _ai_format_final_sale_order(self, matched_products: list, ticket_data: dict) -> dict:
        """
        Third AI call: Format the matched products into final JSON structure.
        This step will not have access to files/attachments.
        
        Args:
            matched_products (list): List of matched products from the second step
            ticket_data (dict): Original ticket data for extracting order details
            
        Returns:
            dict: Final sales order values in the required format
        """
        self.ensure_one()
        _logger.debug("Starting Step 3: Formatting final sales order")
        _logger.debug(f"Input matched products: {matched_products}")
        
        # Get the OpenWebUI provider from company settings
        company = self.env.company
        provider = company.openwebui_provider_id
        
        if not provider:
            _logger.error("No OpenWebUI provider configured for company")
            return {"order_line": []}
            
        # Get the OpenWebUI client from the provider
        ai_client = provider.get_client()
        
        # Create the prompt for the AI to format the final sales order
        matched_products_json = json.dumps(matched_products, indent=2)
        description = ticket_data.get('ticket_description', '')
        chatter_messages = ticket_data.get('ticket_messages', '')
        
        prompt = f"""IMPORTANT: YOU ARE NOT A CONVERSATIONAL ASSISTANT. YOU ARE A DATA FORMATTING SYSTEM.
        
        Your ONLY function is to format the provided matched products into a structured sales order JSON.
        DO NOT introduce yourself, explain what you can or cannot do, or engage in conversation.
        ONLY RETURN THE REQUESTED JSON DATA STRUCTURE.
        
        TASK: Format the following matched products into a complete sales order structure:
        
        Matched Products:
        {matched_products_json}
        
        Additional Context:
        Customer Request:
        {description}
        
        Chatter Messages:
        {chatter_messages}
        
        WORKFLOW - FOLLOW THESE STEPS EXACTLY:
        1. Extract order details (client reference, dates, notes) from the context
        2. Format the matched products into the required sales order line structure
        3. Construct the complete JSON response
        
        RESPONSE FORMAT:
        Your response MUST ONLY be a valid JSON object with the following structure:
        
        {{
            "client_order_ref": "Customer PO number if mentioned",
            "date_order": "YYYY-MM-DD format if a specific order date is mentioned",
            "commitment_date": "YYYY-MM-DD format if a delivery date is mentioned",
            "note": "Any special instructions or notes for the order",
            "order_line": [
                [0, 0, {{
                    "product_id": NUMERIC_ID_FROM_TOOL_CALL,
                    "product_uom_qty": QUANTITY,
                    "price_unit": PRICE
                }}],
                [0, 0, {{
                    "display_type": "line_note",
                    "name": "Unmatched product: Product name (qty: QUANTITY) (ref: REFERENCE if available)",
                    "product_uom_qty": 0.0
                }}],
                ...
            ]
        }}
        
        CRITICAL RULES FOR FORMATTING:
        1. The order_line array MUST contain arrays in the format [0, 0, {{...}}]
        2. Matched products with product_id should be formatted as [0, 0, {{"product_id": ID, "product_uom_qty": QTY, "price_unit": PRICE}}]
        3. Unmatched products with display_type should be formatted as [0, 0, {{"display_type": "line_note", "name": "...", "product_uom_qty": 0.0}}]
        4. Extract any client reference, dates, or notes from the context
        5. Return ONLY valid JSON with no text before or after
        6. DO NOT explain what you're doing or respond conversationally
        
        IMPORTANT: Ensure the final structure matches exactly what's required for Odoo sales order creation.
        """
        
        # Call the AI to format the final sales order
        try:
            _logger.debug("Sending request to AI for final sales order formatting")
            response = ai_client.chat.completions.create(
                model=provider.default_model_id.technical_name if provider.default_model_id else None,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data formatting system. Your ONLY job is to format the provided matched products into a structured sales order JSON that matches exactly what's required for Odoo sales order creation."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            _logger.debug(f"Received AI response for final sales order formatting")
            
        except Exception as e:
            _logger.error(f"Error in AI final formatting request: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "order_line": [],
                "note": f"AI Error: {str(e)}"
            }
        
        # Process the AI response
        _logger.debug(f"AI final formatting response type: {type(response)}")
        
        # Add detailed logging of the response content
        try:
            response_content = response.choices[0].message.content if hasattr(response, 'choices') else str(response)
            _logger.debug(f"AI final formatting response content: {response_content[:1000]}...")
        except:
            _logger.debug("Could not serialize AI final formatting response for logging")
        
        # Extract the content from the response
        response_content = response.choices[0].message.content if hasattr(response, 'choices') else str(response)
        
        # Handle string responses (extract JSON if possible)
        if isinstance(response_content, str):
            _logger.debug("AI returned text response, attempting to extract JSON")
            try:
                # Look for JSON pattern in the text
                json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
                json_matches = re.findall(json_pattern, response_content)
                
                if json_matches:
                    response_data = json.loads(json_matches[0])
                    return response_data
                elif response_content.strip().startswith('{') and response_content.strip().endswith('}'): 
                    response_data = json.loads(response_content.strip())
                    return response_data
                else:
                    _logger.error("Could not extract JSON from text response")
                    return {
                        "order_line": [],
                        "note": f"AI returned invalid format: {response_content[:200]}..."
                    }
            except Exception as parse_error:
                _logger.error(f"Failed to extract JSON from text response: {parse_error}")
                return {
                    "order_line": [],
                    "note": f"AI parsing error: {str(parse_error)}"
                }
        
        # If it's a dictionary, use it directly
        if isinstance(response_content, dict):
            _logger.debug("AI returned dictionary response, using directly")
            return response_content
        
        # If we get here, the response is in an unexpected format
        _logger.error(f"Unexpected response format: {type(response_content)}")
        return {
            "order_line": [],
            "note": f"AI returned unexpected format: {type(response_content)}"
        }
    
 