{
    "name": "Freemoov POS-FSM Qty Delivered Fix",
    "version": "17.0.1.0.0",
    "summary": "Prevent qty_delivered double-count when a FSM-fulfilled SO is paid via POS",
    "category": "Customizations",
    "depends": ["pos_sale", "industry_fsm_stock"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/qty_delivered_reconcile_views.xml",
        "wizard/menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
