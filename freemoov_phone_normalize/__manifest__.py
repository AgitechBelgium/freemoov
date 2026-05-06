{
    "name": "Freemoov Phone Normalize",
    "version": "17.0.1.0.0",
    "summary": "E.164 phone normalization + country inference for partners",
    "category": "Customizations",
    "depends": ["contacts", "phone_validation"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/phone_normalize_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
