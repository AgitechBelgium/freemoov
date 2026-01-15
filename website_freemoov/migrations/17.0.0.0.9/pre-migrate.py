# -*- coding: utf-8 -*-
"""
Pre-migration script to force update of badge_extra_price template override.
This ensures the template changes are applied on Odoo.sh after upgrade.
"""

def migrate(cr, version):
    """
    Delete the old badge_extra_price_fix view to force recreation with new content.
    """
    if not version:
        return
    
    # Delete the old view to force Odoo to recreate it from XML
    cr.execute("""
        DELETE FROM ir_ui_view 
        WHERE key = 'website_freemoov.badge_extra_price_fix'
    """)
    
    # Also try with the full external ID
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE module = 'website_freemoov' 
        AND name = 'badge_extra_price_fix'
    """)
