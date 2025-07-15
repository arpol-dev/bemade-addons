# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import re

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
        
        _logger.info("Starting AI conversion to sale order for ticket %s", self.id)
        
        # Always generate fresh AI suggestions
        _logger.info("Generating fresh AI suggestions for ticket %s", self.id)
        result = self._generate_ai_product_suggestions()
        _logger.info("AI suggestion generation result for ticket %s: %s", self.id, result)
            
        # Get base values for sale order (partner, pricelist, etc.)
        partner_id = self.partner_id.id
        partner_invoice_id = self.partner_id.address_get(['invoice'])['invoice']
        partner_shipping_id = self.partner_id.address_get(['delivery'])['delivery']
        
        # Parse AI suggestions to get order lines and sale order fields
        ai_data = {'order_lines': [], 'sale_order_fields': {}}
        if self.ai_generated_products:
            _logger.info("AI suggestions found for ticket %s, parsing them now: %s", self.id, self.ai_generated_products[:200])
            ai_data = self._parse_ai_product_suggestions()
            _logger.info("Parsed AI data: %s", ai_data)
        
        # Prepare sale order values
        so_values = {
            'partner_id': partner_id,
            'partner_invoice_id': partner_invoice_id,
            'partner_shipping_id': partner_shipping_id,
            'ticket_id': self.id,
            'origin': self.name,
            'note': self.description,
        }
        
        # Add AI-extracted fields to sale order values if available
        if ai_data.get('sale_order_fields'):
            so_fields = ai_data['sale_order_fields']
            
            # Client order reference (PO number)
            if so_fields.get('client_order_ref'):
                so_values['client_order_ref'] = so_fields['client_order_ref']
                _logger.info(f"Setting client_order_ref to: {so_fields['client_order_ref']}")
            
            # Order date
            if so_fields.get('date_order'):
                try:
                    # Validate date format
                    from datetime import datetime
                    date_order = datetime.strptime(so_fields['date_order'], '%Y-%m-%d')
                    so_values['date_order'] = date_order
                    _logger.info(f"Setting date_order to: {so_fields['date_order']}")
                except (ValueError, TypeError) as e:
                    _logger.warning(f"Invalid date_order format: {so_fields['date_order']}, error: {e}")
            
            # Commitment date (delivery date)
            if so_fields.get('commitment_date'):
                try:
                    # Validate date format
                    from datetime import datetime
                    commitment_date = datetime.strptime(so_fields['commitment_date'], '%Y-%m-%d')
                    so_values['commitment_date'] = commitment_date
                    _logger.info(f"Setting commitment_date to: {so_fields['commitment_date']}")
                except (ValueError, TypeError) as e:
                    _logger.warning(f"Invalid commitment_date format: {so_fields['commitment_date']}, error: {e}")
            
            # Note (special instructions)
            if so_fields.get('note'):
                # Append to existing note if any
                existing_note = so_values.get('note', '')
                if existing_note:
                    so_values['note'] = f"{existing_note}\n\n{so_fields['note']}"
                else:
                    so_values['note'] = so_fields['note']
                _logger.info(f"Setting note to: {so_values['note'][:100]}...")
            
            # Payment terms
            if so_fields.get('payment_term_id'):
                # Try to find matching payment term
                payment_term_name = so_fields['payment_term_id']
                payment_term = self.env['account.payment.term'].search(
                    ['|', ('name', '=', payment_term_name), ('name', 'ilike', payment_term_name)], limit=1)
                if payment_term:
                    so_values['payment_term_id'] = payment_term.id
                    _logger.info(f"Setting payment_term_id to: {payment_term.name} (ID: {payment_term.id})")
                else:
                    _logger.warning(f"Payment term not found: {payment_term_name}")
        
        # Create the sale order
        sale_order = self.env['sale.order'].create(so_values)
        _logger.info(f"Created sale order with ID {sale_order.id}")
        
        # Add order lines to the sale order
        order_lines = ai_data.get('order_lines', [])
        _logger.info("Adding %d order lines to sale order %s", len(order_lines), sale_order.id)
        
        for line in order_lines:
            # Each line is a tuple (0, 0, values_dict)
            # Extract the values dict
            line_values = line[2]
            _logger.info("Creating order line with values: %s", line_values)
            # Create a new order line that will trigger price computation
            # Include the price_unit from the parsed data if available
            initial_values = {
                'order_id': sale_order.id,
                'product_id': line_values.get('product_id'),
                'product_uom_qty': line_values.get('product_uom_qty'),
                'name': line_values.get('name'),
            }
            
            # Get the price that was calculated in _create_product_order_line
            calculated_price = line_values.get('price_unit')
            if calculated_price is not None:
                _logger.info(f"Using pre-calculated price: {calculated_price} for product ID: {line_values.get('product_id')}")
                initial_values['price_unit'] = calculated_price
                
            order_line = self.env['sale.order.line'].new(initial_values)
            
            # Trigger standard Odoo onchange to compute prices
            try:
                # This is the main onchange that should set the price based on product and pricelist
                order_line._onchange_product_id()
                
                # Log the computed price for debugging
                _logger.info(f"Standard Odoo price computation: {order_line.price_unit} for product {order_line.product_id.name}")
                
                # If price is still 0 and product has a list price, use that as fallback
                if order_line.price_unit == 0 and order_line.product_id.list_price > 0:
                    order_line.price_unit = order_line.product_id.list_price
                    _logger.info(f"Price was 0, using product list price: {order_line.price_unit}")
            except Exception as e:
                _logger.error(f"Error in standard price computation: {str(e)}")
                # Continue with creation even if price computation fails
            
            # Create a clean dict with only the necessary values
            order_line_values = {
                'order_id': sale_order.id,
                'product_id': order_line.product_id.id,
                'product_uom_qty': order_line.product_uom_qty,
                'name': order_line.name,
                'price_unit': order_line.price_unit,
            }
            
            # Add product_uom if it exists
            if order_line.product_uom:
                order_line_values['product_uom'] = order_line.product_uom.id
            
            # Create the actual order line with computed prices
            self.env['sale.order.line'].create(order_line_values)
        
        # Link the sale order to the ticket
        self.write({
            'sale_order_id': sale_order.id,
        })
        
        # Return the action to view the created sale order
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form,list',
            'context': self.env.context,
        }
    
    def _generate_ai_product_suggestions(self):
        """Use AI to generate product suggestions based on ticket description, chatter messages and attachments"""
        self.ensure_one()
        
        _logger.info("Generating AI product suggestions for ticket %s", self.id)
        
        # Get the ticket description
        description = self.description or ""
        
        # If description is empty, try to use the name
        if not description.strip():
            description = self.name or ""
        
        # Get chatter messages
        chatter_messages = ""
        if self.message_ids:
            for message in self.message_ids:
                if message.body and not message.is_internal:
                    # Extract text from HTML
                    body_text = re.sub(r'<[^>]+>', ' ', message.body)
                    chatter_messages += f"Message from {message.author_id.name or 'Unknown'}: {body_text}\n\n"
        
        # Get attachments
        attachments_info = ""
        attachment_contents = ""
        if self.message_ids:
            for message in self.message_ids:
                if message.attachment_ids:
                    for attachment in message.attachment_ids:
                        attachments_info += f"Attachment: {attachment.name} ({attachment.mimetype})\n"
                        
                        # Extract text from PDF attachments
                        if attachment.mimetype == 'application/pdf' and attachment.datas:
                            try:
                                import base64
                                import io
                                
                                # Try to use PyPDF2 if available
                                try:
                                    from PyPDF2 import PdfReader
                                    
                                    pdf_data = base64.b64decode(attachment.datas)
                                    pdf_file = io.BytesIO(pdf_data)
                                    pdf_reader = PdfReader(pdf_file)
                                    
                                    pdf_text = ""
                                    for page_num in range(len(pdf_reader.pages)):  # Process all pages
                                        page = pdf_reader.pages[page_num]
                                        pdf_text += page.extract_text() + "\n"
                                    
                                    attachment_contents += f"Content from {attachment.name}:\n{pdf_text}\n\n"  # Include full text
                                except ImportError:
                                    _logger.warning("PyPDF2 not available, skipping PDF text extraction")
                            except Exception as e:
                                _logger.error(f"Error extracting text from PDF: {str(e)}")
        
        # If everything is empty, show error
        if not description.strip() and not chatter_messages.strip() and not attachment_contents.strip():
            _logger.error("No content available for AI analysis")
            return False
        
        # Create the prompt for the AI
        prompt = f"""You are an expert sales assistant for a pneumatic automation company. 
        Your task is to analyze the customer request and suggest appropriate products or services.
        
        Customer Request:
        {description}
        
        Chatter Messages:
        {chatter_messages}
        
        Attachments Information:
        {attachments_info}
        
        Attachment Contents:
        {attachment_contents}
        
        Based on this information, please perform two tasks:
        
        1. Map the following Odoo sale order fields from the information provided:
           - client_order_ref: Customer's reference/PO number
           - date_order: Order date (in YYYY-MM-DD format)
           - commitment_date: Delivery date (in YYYY-MM-DD format)
           - note: Any special instructions or notes
           - payment_term_id: Payment terms (e.g., "Net 30", "2% 10 Net 30")
        
        2. Suggest products or services that would meet the customer's needs.
        
        IMPORTANT: Your response MUST be in valid JSON format as shown below. Do not include any explanatory text outside the JSON structure.
        
        ```json
        {{
          "sale_order_fields": {{
            "client_order_ref": "Customer PO number",
            "date_order": "YYYY-MM-DD",
            "commitment_date": "YYYY-MM-DD",
            "note": "Special instructions",
            "payment_term_id": "Payment terms"
          }},
          "products": [
            {{ "name": "Product Name", "quantity": 2, "description": "Product description" }},
            {{ "name": "Another Product", "quantity": 1, "description": "Another description" }}
          ]
        }}
        ```
        
        Only include fields and products that are clearly identified from the provided information.
        If you're not sure about a field or product, leave it blank or don't include it.
        If you cannot identify any products, return an empty products array but still include any sale_order_fields you can identify.
        
        Remember: Your entire response must be valid JSON wrapped in code blocks. No other text.
        """
        
        try:
            # Get the OpenWebUI client
            client = self.env['openai.openwebui.client']
            
            # Create the messages for the AI
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            
            # Call the OpenWebUI API
            _logger.info("Calling OpenWebUI API for ticket %s", self.id)
            response = client.chat_completion(messages)
            
            if response:
                _logger.info("Received AI response for ticket %s: %s", self.id, response[:100])
                
                # Store the AI-generated products
                self.ai_generated_products = response
                
                return True
            else:
                _logger.error("Empty response from OpenWebUI API for ticket %s", self.id)
                return False
        except Exception as e:
            _logger.error("Error generating AI product suggestions for ticket %s: %s", self.id, str(e))
            import traceback
            _logger.error("Traceback: %s", traceback.format_exc())
            return False
    
    # Note: This method is kept for compatibility but is no longer used
    # The _ai_convert_to_sale_order method now creates the sale order directly
    def _generate_ai_so_values(self):
        """Generate sale order values with AI-suggested products"""
        # Start with the base SO values from the parent method
        return self._generate_so_values()
    
    def _parse_ai_product_suggestions(self):
        """Parse the AI-generated product suggestions into sale order lines and fields"""
        result = {
            'order_lines': [],
            'sale_order_fields': {}
        }
        
        if not self.ai_generated_products:
            _logger.warning("No AI generated products found for ticket %s", self.id)
            return result['order_lines']
        
        # Log the AI response for debugging
        _logger.info("Parsing AI product suggestions for ticket %s: %s", self.id, self.ai_generated_products[:300])
        
        # First, try to extract JSON from the response using multiple patterns
        # Pattern 1: Standard code block with json tag
        json_pattern1 = r'```(?:json)?\s*({[\s\S]*?})\s*```'
        # Pattern 2: Just find any JSON-like structure with sale_order_fields or products
        json_pattern2 = r'({[\s\S]*?"(?:sale_order_fields|products)"[\s\S]*?})'
        # Pattern 3: Find any JSON-like structure (most permissive)
        json_pattern3 = r'({\s*"[^"]+"\s*:.*})'  # Any JSON object with at least one key
        
        json_matches = re.findall(json_pattern1, self.ai_generated_products)
        
        if not json_matches:
            _logger.info("No JSON found with pattern 1, trying pattern 2")
            json_matches = re.findall(json_pattern2, self.ai_generated_products)
            
        if not json_matches:
            _logger.info("No JSON found with pattern 2, trying pattern 3")
            json_matches = re.findall(json_pattern3, self.ai_generated_products)
            
        if json_matches:
            # Try to parse the JSON
            try:
                # Clean up the JSON string before parsing
                json_str = json_matches[0]
                # Remove any trailing commas before closing brackets (common JSON error)
                json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
                
                json_data = json.loads(json_str)
                _logger.info(f"Successfully parsed JSON data: {json_data}")
                
                # Extract sale order fields
                if 'sale_order_fields' in json_data:
                    result['sale_order_fields'] = json_data['sale_order_fields']
                    _logger.info(f"Extracted sale order fields: {result['sale_order_fields']}")
                # Direct fields at root level (fallback)
                elif any(key in json_data for key in ['client_order_ref', 'date_order', 'commitment_date', 'note', 'payment_term_id']):
                    so_fields = {}
                    for field in ['client_order_ref', 'date_order', 'commitment_date', 'note', 'payment_term_id']:
                        if field in json_data:
                            so_fields[field] = json_data[field]
                    result['sale_order_fields'] = so_fields
                    _logger.info(f"Extracted sale order fields from root level: {result['sale_order_fields']}")
                
                # Extract products - check multiple possible keys
                product_key = None
                for key in ['products', 'product_suggestions', 'order_lines', 'items']:
                    if key in json_data and isinstance(json_data[key], list):
                        product_key = key
                        break
                        
                if product_key:
                    for product in json_data[product_key]:
                        if not isinstance(product, dict):
                            continue
                            
                        product_name = product.get('name')
                        if not product_name:
                            continue
                            
                        quantity = product.get('quantity', 1.0)
                        try:
                            quantity = float(quantity)
                        except (ValueError, TypeError):
                            quantity = 1.0
                            
                        description = product.get('description', '')
                        
                        _logger.info(f"Processing product from JSON: {product_name}, qty={quantity}, desc={description}")
                        
                        order_line = self._create_product_order_line(product_name, quantity, description)
                        if order_line:
                            result['order_lines'].append(order_line)
                    
                    _logger.info(f"Parsed {len(result['order_lines'])} order lines from JSON")
                    return result
            except json.JSONDecodeError as e:
                _logger.error(f"Failed to parse JSON: {e}")
                
                # Try to extract just the sale order fields using regex as a last resort
                try:
                    # Look for client_order_ref pattern
                    po_pattern = r'(?:client_order_ref|PO number|purchase order)[\s"]*[:=]\s*["]*([^"\n,}]+)'
                    po_match = re.search(po_pattern, self.ai_generated_products, re.IGNORECASE)
                    if po_match:
                        result['sale_order_fields']['client_order_ref'] = po_match.group(1).strip()
                        
                    # Look for dates
                    date_pattern = r'(?:date_order|order date)[\s"]*[:=]\s*["]*([0-9]{4}-[0-9]{2}-[0-9]{2})'
                    date_match = re.search(date_pattern, self.ai_generated_products, re.IGNORECASE)
                    if date_match:
                        result['sale_order_fields']['date_order'] = date_match.group(1)
                        
                    # Look for commitment date
                    commit_pattern = r'(?:commitment_date|delivery date)[\s"]*[:=]\s*["]*([0-9]{4}-[0-9]{2}-[0-9]{2})'
                    commit_match = re.search(commit_pattern, self.ai_generated_products, re.IGNORECASE)
                    if commit_match:
                        result['sale_order_fields']['commitment_date'] = commit_match.group(1)
                        
                    # Look for payment terms
                    payment_pattern = r'(?:payment_term_id|payment terms)[\s"]*[:=]\s*["]*([^"\n,}]+)'
                    payment_match = re.search(payment_pattern, self.ai_generated_products, re.IGNORECASE)
                    if payment_match:
                        result['sale_order_fields']['payment_term_id'] = payment_match.group(1).strip()
                        
                    if result['sale_order_fields']:
                        _logger.info(f"Extracted sale order fields using regex: {result['sale_order_fields']}")
                except Exception as regex_error:
                    _logger.error(f"Error in regex extraction fallback: {regex_error}")
        
        # If JSON parsing failed, fall back to the old parsing methods
        _logger.info("Falling back to legacy parsing methods")
        
        # Try to extract reference number using regex before falling back to line-by-line parsing
        ref_patterns = [
            r'(?:reference|ticket|po|purchase order)[\s\-]*(?:number|#)?[\s\-:]*([\d\-]+)',
            r'(?:client_order_ref|order ref)[\s"]*[:=]\s*["]*([^"\n,}]+)'
        ]
        
        for pattern in ref_patterns:
            ref_match = re.search(pattern, self.ai_generated_products, re.IGNORECASE)
            if ref_match:
                ref_number = ref_match.group(1).strip()
                _logger.info(f"Found reference number using regex: {ref_number}")
                result['sale_order_fields']['client_order_ref'] = ref_number
                break
        order_lines = []
        
        # Try to parse the AI response in different formats
        # First, look for a table format with | separators
        table_pattern = r"([^|\n]+)\s*\|\s*(\d*\.?\d*)\s*\|\s*([^|\n]*)"
        table_matches = re.findall(table_pattern, self.ai_generated_products)
        
        if table_matches:
            # Process table format
            _logger.info(f"Found table format with {len(table_matches)} matches")
            for match in table_matches:
                product_name = match[0].strip()
                if not product_name or product_name.lower() in ['product/service name', 'product', 'service', 'item']:
                    continue
                    
                # Parse quantity
                quantity = 1.0
                if match[1].strip():
                    try:
                        quantity = float(match[1].strip())
                    except ValueError:
                        quantity = 1.0
                
                # Get description
                description = match[2].strip() if match[2].strip() else product_name
                
                # Add the order line
                order_line = self._create_product_order_line(product_name, quantity, description)
                if order_line:
                    order_lines.append(order_line)
        else:
            # Try to parse line by line for products and quantities
            # Look for patterns like "2x Product Name" or "Product Name (qty: 3)" or "Product Name - 4 units"
            lines = self.ai_generated_products.strip().split('\n')
            _logger.info(f"Parsing line by line, found {len(lines)} lines")
            
            # Skip header lines and empty lines
            processed_lines = []
            for line in lines:
                line = line.strip()
                # Skip empty lines, headers, and other non-product lines
                if (not line or 
                    line.startswith('#') or 
                    line.lower().startswith('product') or
                    line.lower() == 'format your response as' or
                    line.lower() == 'for example:'):
                    continue
                
                # Remove bullet points and other common prefixes
                line = re.sub(r'^[-*\u2022]\s*', '', line)
                processed_lines.append(line)
            
            for line in processed_lines:
                _logger.info(f"Processing line: {line}")
                
                # Try to extract quantity, product name, part number, and description
                # Format examples:
                # - 2x Air Compressor Filter P-AC500: 5 micron, high-efficiency
                # - 1x Preventive Maintenance Service: Annual service package
                # - 3x Pneumatic Valves PV-230: 3/4" NPT connection, 150 PSI
                
                # Pattern for the format specified in the prompt template
                detailed_pattern = r"(\d+)x\s+([^:]+?)(?:\s+([A-Z0-9][A-Z0-9-]+))?\s*:?\s*(.*)"
                match = re.search(detailed_pattern, line, re.IGNORECASE)
                
                if match:
                    quantity = float(match.group(1))
                    product_name = match.group(2).strip()
                    part_number = match.group(3) if match.group(3) else ''
                    specs = match.group(4).strip() if match.group(4) else ''
                    
                    # Combine part number with product name if available
                    if part_number:
                        full_product_name = f"{product_name} {part_number}"
                    else:
                        full_product_name = product_name
                    
                    # Use specifications as description if available
                    description = specs if specs else product_name
                    
                    _logger.info(f"Matched detailed pattern: qty={quantity}, product={full_product_name}, desc={description}")
                    
                    order_line = self._create_product_order_line(full_product_name, quantity, description)
                    if order_line:
                        order_lines.append(order_line)
                    continue
                
                # Try other common patterns if the detailed pattern didn't match
                qty_patterns = [
                    r"(\d+(?:\.\d+)?)\s*x\s*([^\d\n]+)",  # "2x Product Name" or "2.5x Product Name"
                    r"([^\d\n]+)\s*\(\s*qty\s*:\s*(\d+(?:\.\d+)?)\s*\)",  # "Product Name (qty: 3)"
                    r"([^\d\n]+)\s*-\s*(\d+(?:\.\d+)?)\s*units?",  # "Product Name - 4 units"
                    r"([^\d\n]+)\s*:\s*(\d+(?:\.\d+)?)",  # "Product Name: 2"
                    r"quantity\s*:\s*(\d+(?:\.\d+)?)\s*,?\s*([^,]+)",  # "Quantity: 2, Product Name"
                ]
                
                product_name = None
                quantity = 1.0
                description = ""
                
                for pattern in qty_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        if pattern == qty_patterns[0]:  # "2x Product Name"
                            try:
                                quantity = float(match.group(1))
                                product_name = match.group(2).strip()
                            except (ValueError, IndexError):
                                continue
                        else:  # Other patterns
                            try:
                                product_name = match.group(1).strip()
                                quantity = float(match.group(2))
                            except (ValueError, IndexError):
                                continue
                        
                        # Try to extract description after the product name
                        desc_match = re.search(r"[^:]+:(.+)$", line)
                        if desc_match:
                            description = desc_match.group(1).strip()
                        
                        _logger.info(f"Matched pattern {pattern}: qty={quantity}, product={product_name}, desc={description}")
                        break
                
                # If no pattern matched, use the whole line as product name
                if not product_name:
                    # Check if there's a colon that might separate product name from description
                    if ':' in line:
                        parts = line.split(':', 1)
                        product_name = parts[0].strip()
                        description = parts[1].strip() if len(parts) > 1 else ''
                    else:
                        product_name = line
                        description = ''
                    
                    _logger.info(f"No pattern match, using line as product: {product_name}, desc={description}")
                
                # Add the order line
                order_line = self._create_product_order_line(product_name, quantity, description)
                if order_line:
                    order_lines.append(order_line)
        
        result['order_lines'] = order_lines
        _logger.info(f"Parsed {len(order_lines)} order lines from AI suggestions")
        return result
    
    def _create_product_order_line(self, product_name, quantity, description=""):
        """Create a sale order line for a product"""
        if not product_name:
            return False
        
        # Search for matching product - try exact match first
        product = self.env['product.product'].search([
            ('name', '=', product_name),
            ('sale_ok', '=', True)
        ], limit=1)
        
        # If no exact match, try partial match
        if not product:
            product = self.env['product.product'].search([
                ('name', 'ilike', product_name),
                ('sale_ok', '=', True)
            ], limit=1)
        
        # If still no product found, try matching by default_code (SKU/part number)
        if not product and any(c.isdigit() for c in product_name):  # Check if product name contains numbers (likely a part number)
            # Extract potential part numbers
            part_numbers = re.findall(r'[A-Z0-9][A-Z0-9-]+', product_name)
            for part in part_numbers:
                product = self.env['product.product'].search([
                    ('default_code', '=', part),
                    ('sale_ok', '=', True)
                ], limit=1)
                if product:
                    break
        
        # If no product found, log it and return False
        if not product:
            _logger.info(f"No matching product found for: {product_name}")
            return False
        
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
        
        return (0, 0, line_values)
