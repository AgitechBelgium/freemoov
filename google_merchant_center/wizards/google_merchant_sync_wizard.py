# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GoogleMerchantSyncWizard(models.TransientModel):
    _name = 'google.merchant.sync.wizard'
    _description = 'Sync products to Google Merchant Center'

    sync_mode = fields.Selection(
        [
            ('all', 'All products in GMC scope'),
            ('pending', 'Only pending'),
        ],
        string='Sync mode',
        default='pending',
        required=True,
    )
    product_ids = fields.Many2many(
        'product.template',
        string='Products',
        help="Leave empty to use sync mode. Otherwise sync only selected products.",
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('done', 'Done'),
        ],
        default='draft',
    )
    result_message = fields.Html(string='Result', readonly=True)

    def action_sync(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('google_merchant_center.sync_enabled', 'False') != 'True':
            raise UserError(_('Google Merchant Center sync is disabled in Settings.'))
        if self.product_ids:
            products = self.product_ids
        elif self.sync_mode == 'pending':
            products = self.env['product.template'].search([('gmc_sync_status', '=', 'pending')])
        else:
            products = self.env['product.template'].search([
                ('is_published', '=', True),
                ('gmc_exclude', '=', False),
            ])
            products = products.filtered(lambda p: p._is_in_gmc_scope())
        success = 0
        errors = []
        for product in products:
            try:
                product.sudo().write({'gmc_sync_status': 'pending'})
                product._gmc_sync_push()
                if product.gmc_sync_status == 'synced':
                    success += 1
                else:
                    errors.append('%s: %s' % (product.name, product.gmc_sync_status))
            except Exception as e:
                errors.append('%s: %s' % (product.name, str(e)))
        msg = _('Synced %s product(s) successfully.') % success
        if errors:
            msg += '<br/><br/><strong>Errors or not synced:</strong><ul><li>%s</li></ul>' % '</li><li>'.join(errors[:20])
            if len(errors) > 20:
                msg += _('... and %s more.') % (len(errors) - 20)
        self.write({'state': 'done', 'result_message': msg})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
