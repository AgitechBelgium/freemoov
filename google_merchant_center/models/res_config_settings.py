# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gmc_merchant_id = fields.Char(
        string='Merchant Account ID',
        config_parameter='google_merchant_center.merchant_id',
        default='5345092695',
    )
    gmc_data_source_id = fields.Char(
        string='Data Source ID',
        config_parameter='google_merchant_center.data_source_id',
        default='10624847602',
    )
    gmc_service_account_json = fields.Binary(
        string='Service Account JSON Key',
        attachment=True,
    )
    gmc_service_account_filename = fields.Char(
        string='JSON Key Filename',
    )
    gmc_feed_label = fields.Char(
        string='Feed Label',
        config_parameter='google_merchant_center.feed_label',
        default='BE',
    )
    gmc_content_language = fields.Char(
        string='Content Language',
        config_parameter='google_merchant_center.content_language',
        default='fr',
    )
    gmc_base_url = fields.Char(
        string='Base URL (website)',
        config_parameter='google_merchant_center.base_url',
        default='https://freemoov.com',
    )
    gmc_sync_enabled = fields.Boolean(
        string='Sync Enabled',
        config_parameter='google_merchant_center.sync_enabled',
        default=False,
    )
    gmc_dry_run = fields.Boolean(
        string='Dry Run Mode',
        config_parameter='google_merchant_center.dry_run',
        default=True,
        help='When active, sync operations are logged but NOT sent to Google. '
             'Use this to verify data before going live.',
    )
    gmc_cron_interval = fields.Integer(
        string='Cron Interval (minutes)',
        config_parameter='google_merchant_center.cron_interval',
        default=15,
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            gmc_merchant_id=ICP.get_param('google_merchant_center.merchant_id', '5345092695'),
            gmc_data_source_id=ICP.get_param('google_merchant_center.data_source_id', '10624847602'),
            gmc_feed_label=ICP.get_param('google_merchant_center.feed_label', 'BE'),
            gmc_content_language=ICP.get_param('google_merchant_center.content_language', 'fr'),
            gmc_base_url=ICP.get_param('google_merchant_center.base_url', 'https://freemoov.com'),
            gmc_sync_enabled=ICP.get_param('google_merchant_center.sync_enabled', 'False') == 'True',
            gmc_dry_run=ICP.get_param('google_merchant_center.dry_run', 'True') == 'True',
            gmc_cron_interval=int(ICP.get_param('google_merchant_center.cron_interval', '15')),
        )
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.config.settings'),
            ('name', 'ilike', 'gmc_service_account'),
        ], order='id desc', limit=1)
        if attachment:
            res['gmc_service_account_json'] = attachment.datas
            res['gmc_service_account_filename'] = attachment.name
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('google_merchant_center.merchant_id', self.gmc_merchant_id or '5345092695')
        ICP.set_param('google_merchant_center.data_source_id', self.gmc_data_source_id or '10624847602')
        ICP.set_param('google_merchant_center.feed_label', self.gmc_feed_label or 'BE')
        ICP.set_param('google_merchant_center.content_language', self.gmc_content_language or 'fr')
        ICP.set_param('google_merchant_center.base_url', self.gmc_base_url or 'https://freemoov.com')
        ICP.set_param('google_merchant_center.sync_enabled', str(self.gmc_sync_enabled))
        ICP.set_param('google_merchant_center.dry_run', str(self.gmc_dry_run))
        ICP.set_param('google_merchant_center.cron_interval', str(self.gmc_cron_interval))
        if self.gmc_service_account_json:
            name = self.gmc_service_account_filename or 'gmc_service_account.json'
            self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'res.config.settings'),
                ('name', 'ilike', 'gmc_service_account'),
            ]).unlink()
            self.env['ir.attachment'].sudo().create({
                'name': name,
                'datas': self.gmc_service_account_json,
                'res_model': 'res.config.settings',
                'res_id': 0,
                'type': 'binary',
            })

    @api.model
    def get_gmc_credentials_json(self):
        """Return service account JSON dict for API client, or None."""
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.config.settings'),
            ('name', 'ilike', 'gmc_service_account'),
        ], order='id desc', limit=1)
        if not attachment or not attachment.datas:
            return None
        import base64
        import json
        try:
            return json.loads(base64.b64decode(attachment.datas).decode('utf-8'))
        except Exception:
            return None
