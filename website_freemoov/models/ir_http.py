# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    _FM_MAINT_WHITELIST_PREFIXES = (
        "/web/",
        "/website/assets",
        "/website/translations",
        "/longpolling",
        "/bus/",
        "/web_editor/",
        "/web_tour/",
        "/saas_worker/",
    )
    _FM_MAINT_WHITELIST_EXACT = frozenset({
        "/web",
        "/robots.txt",
        "/favicon.ico",
        "/sitemap.xml",
    })

    @classmethod
    def _dispatch(cls, endpoint):
        if cls._fm_maintenance_should_intercept():
            return cls._fm_maintenance_response()
        return super()._dispatch(endpoint)

    @classmethod
    def _fm_maintenance_should_intercept(cls):
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param("website_freemoov.maintenance_mode_active") != "True":
            return False

        path = request.httprequest.path or "/"
        if path in cls._FM_MAINT_WHITELIST_EXACT:
            return False
        for prefix in cls._FM_MAINT_WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return False

        user = request.env.user
        if user and not user._is_public() and user.has_group("base.group_user"):
            return False

        return True

    @classmethod
    def _fm_maintenance_response(cls):
        icp = request.env["ir.config_parameter"].sudo()
        values = {
            "maintenance_message": icp.get_param("website_freemoov.maintenance_message") or "",
            "maintenance_start": icp.get_param("website_freemoov.maintenance_start_datetime") or "",
        }
        rendered = request.env["ir.ui.view"].sudo()._render_template(
            "website_freemoov.maintenance_page", values
        )
        html = "<!DOCTYPE html>\n" + str(rendered)
        return request.make_response(
            html,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                ("Retry-After", "3600"),
                ("Cache-Control", "no-store, no-cache, must-revalidate"),
                ("Pragma", "no-cache"),
            ],
            status=503,
        )
