# -*- coding: utf-8 -*-

from . import helpdesk_ticket
from . import helpdesk_team
from . import sale_order
from . import ai_openwebui_client  # Bridge model for OpenWebUI client
from . import ai_openwebui_prompt_template  # Bridge model for OpenWebUI prompt templates
from . import res_config_settings

# Import views after all models are loaded
from .. import views
