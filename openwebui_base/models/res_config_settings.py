from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    openwebui_provider_id = fields.Many2one(
        comodel_name="openwebui.provider",
        related="company_id.openwebui_provider_id",
        readonly=False,
        company_dependent=True,
    )

    openwebui_default_model_id = fields.Many2one(
        comodel_name="openwebui.model",
        related="company_id.openwebui_default_model_id",
        readonly=False,
        company_dependent=True,
    )
    
    use_ai_sale_orders = fields.Boolean(
        string='Use AI for Sale Orders',
        help='If checked, the system will use AI to automatically generate sale orders from ticket descriptions.',
    )
    
    @api.model
    def get_values(self):
        """Get values for the settings form"""
        res = super(ResConfigSettings, self).get_values()
        
        # Get the AI sale orders setting from the system parameter
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        param_value = IrConfigParam.get_param('helpdesk_sale_order_ai.use_ai_sale_orders', 'True')
        res['use_ai_sale_orders'] = param_value.lower() == 'true' if isinstance(param_value, str) else bool(param_value)
        
        return res
    
    def set_values(self):
        """Set values from the settings form"""
        super(ResConfigSettings, self).set_values()
        
        # Save the AI sale orders setting to the system parameter
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        IrConfigParam.set_param('helpdesk_sale_order_ai.use_ai_sale_orders', str(self.use_ai_sale_orders))
