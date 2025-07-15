# -*- coding: utf-8 -*-

from . import helpdesk_ticket
from . import helpdesk_team
from . import sale_order
# Using centralized openwebui.openwebui.client model from openwebui_connector
from . import res_config_settings
# Using centralized openwebui.prompt.template model from openwebui_connector

# Import views after all models are loaded
from .. import views
