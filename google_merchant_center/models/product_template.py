# -*- coding: utf-8 -*-
import json
import logging
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GMC_SYNC_FIELDS = [
    'name', 'list_price', 'compare_list_price', 'description_sale',
    'description', 'image_1920', 'is_published', 'website_published',
    'weight', 'default_code', 'gmc_exclude', 'gmc_google_category',
    'gmc_condition',
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gmc_sync_status = fields.Selection(
        [
            ('not_synced', 'Not Synced'),
            ('pending', 'Pending'),
            ('synced', 'Synced'),
            ('error', 'Error'),
        ],
        string='GMC Sync Status',
        default='not_synced',
        copy=False,
    )
    gmc_last_sync_date = fields.Datetime(string='GMC Last Sync', copy=False)
    gmc_exclude = fields.Boolean(string='Exclude from GMC', default=False)
    gmc_google_category = fields.Char(
        string='Google Product Category (override)',
        help='Override the category sent to Google. Leave empty to use automatic mapping.',
    )
    gmc_condition = fields.Selection(
        [
            ('new', 'New'),
            ('refurbished', 'Refurbished'),
            ('used', 'Used'),
        ],
        string='GMC Condition',
        default='new',
    )
    gmc_offer_id = fields.Char(
        string='GMC Offer ID (override)', copy=False,
        help='If set, this value is used as the offer_id sent to Google. '
             'Use this to preserve existing product history in Merchant Center.',
    )
    gmc_error_count = fields.Integer(
        string='GMC Error Count', default=0, copy=False,
        help='Number of consecutive sync errors. Products with >5 errors are skipped by the cron.',
    )

    def _get_gmc_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'google_merchant_center.base_url', 'https://freemoov.com'
        ).rstrip('/')

    def _get_gmc_availability(self):
        """Return IN_STOCK, OUT_OF_STOCK, PREORDER or BACKORDER."""
        if self.detailed_type != 'product':
            return 'IN_STOCK'
        if self.allow_out_of_stock_order:
            return 'IN_STOCK'
        try:
            website = self.env['website'].get_current_website()
            avail = self.get_stock_availability(website)
            if avail.get('is_dropship') or avail.get('allow_out_of_stock'):
                return 'IN_STOCK'
            return 'OUT_OF_STOCK' if (avail.get('qty_avail') or 0) <= 0 else 'IN_STOCK'
        except Exception:
            return 'IN_STOCK'

    def _prepare_gmc_product_input(self):
        """Build dict for GoogleMerchantService.insert_product using the SEO optimizer."""
        from ..services.gmc_feed_optimizer import prepare_product_data

        ICP = self.env['ir.config_parameter'].sudo()
        base_url = self._get_gmc_base_url()
        feed_label = ICP.get_param('google_merchant_center.feed_label', 'BE')
        content_language = ICP.get_param('google_merchant_center.content_language', 'fr')

        data = prepare_product_data(
            self,
            base_url=base_url,
            content_language=content_language,
            feed_label=feed_label,
        )

        if self.gmc_google_category:
            data['google_product_category'] = self.gmc_google_category

        data['availability'] = self._get_gmc_availability()
        return data

    def _get_gmc_category_names(self):
        """All category names for this product (including parents), lowercased."""
        names = set()
        for cat in self.public_categ_ids:
            c = cat
            while c:
                if c.name:
                    names.add(c.name.lower())
                c = c.parent_id
        return names

    def _is_gmc_product_type_allowed(self):
        """All products except scooters/motos and gyroroues (vehicle policy)."""
        from ..services.gmc_feed_optimizer import is_in_feed_scope
        return is_in_feed_scope(self)

    def _is_in_gmc_scope(self):
        """True if product should be synced (published + in GMC-enabled category, not excluded)."""
        if self.gmc_exclude or not self.is_published:
            return False
        if not self._is_gmc_product_type_allowed():
            return False
        for cat in self.public_categ_ids:
            if cat.gmc_enabled:
                return True
            parent = cat
            while parent.parent_id:
                parent = parent.parent_id
                if parent.gmc_enabled:
                    return True
        return False

    def _is_gmc_dry_run(self):
        """Check if dry-run mode is active (no actual API calls)."""
        ICP = self.env['ir.config_parameter'].sudo()
        return ICP.get_param('google_merchant_center.dry_run', 'True') == 'True'

    def _get_gmc_service(self):
        """Return GoogleMerchantService instance or None."""
        from ..services.google_merchant_service import GoogleMerchantService
        Config = self.env['res.config.settings']
        credentials = Config.get_gmc_credentials_json()
        if not credentials:
            return None
        ICP = self.env['ir.config_parameter'].sudo()
        merchant_id = ICP.get_param('google_merchant_center.merchant_id', '5345092695')
        data_source_id = ICP.get_param('google_merchant_center.data_source_id', '10624847602')
        return GoogleMerchantService(merchant_id, data_source_id, credentials)

    def _gmc_sync_push(self):
        """Push this product to GMC (insert/upsert). Log result."""
        if not self._is_in_gmc_scope():
            return
        product_data = self._prepare_gmc_product_input()
        Log = self.env['google.merchant.log'].sudo()

        if self._is_gmc_dry_run():
            Log.create({
                'product_id': self.id,
                'operation': 'insert',
                'status': 'success',
                'gmc_product_id': 'DRY-RUN',
                'request_data': json.dumps(product_data, ensure_ascii=False, default=str)[:5000],
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'synced',
                'gmc_last_sync_date': fields.Datetime.now(),
                'gmc_error_count': 0,
            })
            _logger.info('GMC DRY-RUN: would sync product %s [%s]', self.id, product_data.get('title', '')[:60])
            return

        service = self._get_gmc_service()
        if not service:
            Log.create({
                'product_id': self.id,
                'operation': 'insert',
                'status': 'error',
                'error_message': 'No GMC credentials configured',
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'error',
            })
            return

        ok, result = service.insert_product_with_retry(product_data)
        if ok:
            gmc_id = getattr(result, 'name', None) or str(result)
            Log.create({
                'product_id': self.id,
                'operation': 'insert',
                'status': 'success',
                'gmc_product_id': gmc_id,
                'request_data': json.dumps(product_data, ensure_ascii=False, default=str)[:5000],
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'synced',
                'gmc_last_sync_date': fields.Datetime.now(),
                'gmc_error_count': 0,
            })
        else:
            Log.create({
                'product_id': self.id,
                'operation': 'insert',
                'status': 'error',
                'error_message': result or 'Unknown error',
                'request_data': json.dumps(product_data, ensure_ascii=False, default=str)[:5000],
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'error',
                'gmc_error_count': (self.gmc_error_count or 0) + 1,
            })

    def _gmc_sync_delete(self):
        """Remove this product from GMC."""
        Log = self.env['google.merchant.log'].sudo()

        if self._is_gmc_dry_run():
            Log.create({
                'product_id': self.id,
                'operation': 'delete',
                'status': 'success',
                'gmc_product_id': 'DRY-RUN',
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'not_synced',
                'gmc_last_sync_date': False,
            })
            _logger.info('GMC DRY-RUN: would delete product %s', self.id)
            return

        service = self._get_gmc_service()
        if not service:
            return
        product_data = self._prepare_gmc_product_input()
        offer_id = product_data.get('offer_id')
        content_language = product_data.get('content_language', 'fr')
        feed_label = product_data.get('feed_label', 'BE')
        ok, err = service.delete_product(offer_id, content_language, feed_label)
        if ok:
            Log.create({
                'product_id': self.id,
                'operation': 'delete',
                'status': 'success',
            })
            self.sudo().with_context(gmc_skip_write_trigger=True).write({
                'gmc_sync_status': 'not_synced',
                'gmc_last_sync_date': False,
            })
        else:
            Log.create({
                'product_id': self.id,
                'operation': 'delete',
                'status': 'error',
                'error_message': err or 'Unknown error',
            })

    @api.model
    def _cron_gmc_sync(self):
        """Cron: sync pending, new in scope, and delete unpublished."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('google_merchant_center.sync_enabled', 'False') != 'True':
            return

        # 1) Pending products (skip those with too many errors)
        pending = self.search([
            ('gmc_sync_status', '=', 'pending'),
            ('gmc_error_count', '<', 6),
        ], limit=100)
        for product in pending:
            try:
                product._gmc_sync_push()
            except Exception as e:
                _logger.warning('GMC cron sync error for product %s: %s', product.id, e)
                product.sudo().with_context(gmc_skip_write_trigger=True).write({
                    'gmc_sync_status': 'error',
                    'gmc_error_count': (product.gmc_error_count or 0) + 1,
                })
                self.env['google.merchant.log'].sudo().create({
                    'product_id': product.id,
                    'operation': 'insert',
                    'status': 'error',
                    'error_message': str(e)[:2000],
                })
            self.env.cr.commit()

        # 2) New in scope (published, not_synced, low error count)
        in_scope = self.search([
            ('gmc_sync_status', '=', 'not_synced'),
            ('is_published', '=', True),
            ('gmc_exclude', '=', False),
            ('gmc_error_count', '<', 6),
        ], limit=50)
        for product in in_scope:
            if product._is_in_gmc_scope():
                try:
                    product._gmc_sync_push()
                except Exception as e:
                    _logger.warning('GMC cron sync error for product %s: %s', product.id, e)
                    product.sudo().with_context(gmc_skip_write_trigger=True).write({
                        'gmc_sync_status': 'error',
                        'gmc_error_count': (product.gmc_error_count or 0) + 1,
                    })
                    self.env['google.merchant.log'].sudo().create({
                        'product_id': product.id,
                        'operation': 'insert',
                        'status': 'error',
                        'error_message': str(e)[:2000],
                    })
                self.env.cr.commit()

        # 3) Delete: was synced but now unpublished or excluded
        to_delete = self.search([
            ('gmc_sync_status', '=', 'synced'),
            '|', ('is_published', '=', False), ('gmc_exclude', '=', True),
        ], limit=50)
        for product in to_delete:
            try:
                product._gmc_sync_delete()
            except Exception as e:
                _logger.warning('GMC cron delete error for product %s: %s', product.id, e)
            self.env.cr.commit()

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if not self.env.context.get('gmc_skip_write_trigger'):
            track = [k for k in GMC_SYNC_FIELDS if k in vals]
            if track:
                for product in self:
                    if product._is_in_gmc_scope():
                        product.sudo().with_context(gmc_skip_write_trigger=True).write({
                            'gmc_sync_status': 'pending',
                        })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductTemplate, self).create(vals_list)
        for product in products:
            if product._is_in_gmc_scope():
                product.sudo().with_context(gmc_skip_write_trigger=True).write({
                    'gmc_sync_status': 'pending',
                })
        return products

    def unlink(self):
        for product in self:
            if product.gmc_sync_status == 'synced':
                try:
                    product._gmc_sync_delete()
                except Exception:
                    pass
        return super(ProductTemplate, self).unlink()

    def action_gmc_sync_now(self):
        """Button: force sync this product to GMC."""
        self.ensure_one()
        if not self._is_in_gmc_scope() and not self.gmc_exclude:
            raise UserError(_('Product is not in GMC scope (published + in a GMC-enabled category).'))
        self.sudo().with_context(gmc_skip_write_trigger=True).write({
            'gmc_sync_status': 'pending',
            'gmc_error_count': 0,
        })
        self._gmc_sync_push()
        return True

    def action_gmc_reset_errors(self):
        """Button: reset error count to allow re-sync."""
        self.sudo().with_context(gmc_skip_write_trigger=True).write({
            'gmc_sync_status': 'not_synced',
            'gmc_error_count': 0,
        })
