# -*- coding: utf-8 -*-
"""
Pre-migration script to force update of product_slider and product_grid templates.
These templates were using _get_combination_info(pricelist=...) which no longer exists in Odoo 17.
"""

def migrate(cr, version):
    """
    Delete the old product_slider and product_grid views to force recreation with new content.
    """
    if not version:
        return
    
    # Delete the old views to force Odoo to recreate them from XML
    templates_to_delete = [
        'ust_common_features.product_slider',
        'ust_common_features.product_grid',
        'ust_common_features.product_list',
        'ust_common_features.ust_allin_one_slider_configure_option',
    ]
    
    for template in templates_to_delete:
        cr.execute("""
            DELETE FROM ir_ui_view 
            WHERE key = %s
        """, (template,))
        
        # Also delete from ir_model_data
        module, name = template.split('.', 1)
        cr.execute("""
            DELETE FROM ir_model_data 
            WHERE module = %s 
            AND name = %s
        """, (module, name))
