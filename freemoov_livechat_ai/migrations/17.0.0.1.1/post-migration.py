"""Drop `delay_seconds`: a setting that was displayed, saved, and read by
nobody — the agent loop has never waited for anything.

A migration rather than the ordinary orphan cleanup: records declared under
`noupdate` are the ones Odoo never removes when their xml id leaves the data
files (`ir.model.data._process_end` skips them by construction), so the
parameter would have outlived its own field.
"""

PARAM_KEY = "freemoov_livechat_ai.delay_seconds"
PARAM_XMLID = "param_delay"


def migrate(cr, version):
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (PARAM_KEY,))
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
        ("freemoov_livechat_ai", PARAM_XMLID),
    )
