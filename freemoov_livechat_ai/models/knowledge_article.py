from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class KnowledgeArticle(models.Model):
    _name = 'freemoov.ai.knowledge.article'
    _description = 'Connaissance validée pour l’assistant'
    _rec_name = 'title'
    _order = 'key, revision desc'

    key = fields.Char(required=True, index=True)
    revision = fields.Integer(required=True, default=1)
    website_id = fields.Many2one('website', required=True, ondelete='cascade', index=True)
    lang = fields.Char(required=True, default='fr')
    topic = fields.Char()
    title = fields.Char(required=True)
    aliases = fields.Text()
    answer = fields.Text(required=True)
    source_kind = fields.Selection([('public_url', 'Page publique'), ('client_decision', 'Décision validée')], required=True)
    source_ref = fields.Char(required=True)
    source_revision = fields.Char()
    public_url = fields.Char()
    effective_from = fields.Date()
    effective_until = fields.Date()
    state = fields.Selection([('draft', 'Brouillon'), ('published', 'Publié'), ('archived', 'Archivé')], default='draft', required=True, readonly=True)
    validated_by = fields.Many2one('res.users', readonly=True)
    validated_at = fields.Datetime(readonly=True)
    internal_note = fields.Text()

    _sql_constraints = [('knowledge_revision_unique', 'unique(website_id,lang,key,revision)', 'Cette révision existe déjà.')]

    def init(self):
        # SQL remains authoritative if concurrent transactions have stale snapshots.
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS fm_knowledge_one_published
            ON freemoov_ai_knowledge_article (website_id, lang, key)
            WHERE state = 'published'""")

    def _check_manager(self):
        if not (self.env.su or self.env.user.has_group('base.group_system') or
                self.env.user.has_group('freemoov_livechat_ai.group_knowledge_manager')):
            raise AccessError('Gestion des connaissances non autorisée.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' or vals.get('validated_by') or vals.get('validated_at'):
                raise UserError('Utilisez l’action Publier pour valider une révision.')
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        if {'state', 'validated_by', 'validated_at'} & vals.keys():
            raise UserError('Utilisez les actions de publication.')
        if any(row.state != 'draft' for row in self):
            raise UserError('Créez une nouvelle révision pour modifier une connaissance publiée.')
        return super().write(vals)

    def unlink(self):
        self._check_manager()
        if any(row.state != 'draft' for row in self):
            raise UserError('Archivez les connaissances publiées ; leur historique doit être conservé.')
        return super().unlink()

    @api.constrains('answer', 'title', 'key', 'revision', 'public_url', 'source_kind', 'effective_from', 'effective_until')
    def _validate_content(self):
        for row in self:
            if not row.answer.strip() or not row.title.strip() or not row.key.strip() or row.revision < 1:
                raise ValidationError('Titre, réponse, clé et révision valides obligatoires.')
            if len(row.answer) > 1500:
                raise ValidationError('Découpez la réponse en articles de 1500 caractères maximum.')
            if row.effective_from and row.effective_until and row.effective_from > row.effective_until:
                raise ValidationError('Période de validité incorrecte.')
            if row.source_kind == 'public_url' and not row.public_url:
                raise ValidationError('URL publique requise.')
            if row.public_url:
                try:
                    url = urlsplit(row.public_url)
                    valid = (url.scheme == 'https' and url.hostname in ('www.freemoov.com', 'freemoov.com')
                             and not url.username and not url.password and url.port in (None, 443))
                except ValueError:
                    valid = False
                if not valid:
                    raise ValidationError('Seules les pages HTTPS Freemoov sont autorisées.')

    def _lock_key(self):
        self.ensure_one()
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ['fm-knowledge:%s:%s:%s' % (self.website_id.id, self.lang, self.key)])

    def action_publish(self):
        self._check_manager()
        for row in self.sorted('id'):
            row._lock_key()
            if row.state != 'draft':
                raise UserError('Seul un brouillon peut être publié.')
            old = self.search([('website_id', '=', row.website_id.id), ('lang', '=', row.lang),
                               ('key', '=', row.key), ('state', '=', 'published')])
            if any(previous.revision >= row.revision for previous in old):
                raise UserError('Une révision plus récente est déjà publiée.')
            super(KnowledgeArticle, old).write({'state': 'archived'})
            old.flush_recordset(['state'])
            super(KnowledgeArticle, row).write({'state': 'published', 'validated_by': self.env.uid,
                                                'validated_at': fields.Datetime.now()})
        return True

    def action_archive(self):
        self._check_manager()
        return super().write({'state': 'archived'})

    def action_new_revision(self):
        self._check_manager()
        self.ensure_one()
        self._lock_key()
        latest = self.search([('website_id', '=', self.website_id.id), ('lang', '=', self.lang),
                              ('key', '=', self.key)], order='revision desc', limit=1)
        row = self.copy({'revision': latest.revision + 1, 'state': 'draft',
                         'validated_by': False, 'validated_at': False, 'source_revision': False})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': row.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def _published_for(self, website_id, lang='fr', on_date=None):
        day = on_date or fields.Date.today()
        return self.search([('website_id', '=', website_id), ('lang', '=', lang), ('state', '=', 'published'),
                            '|', ('effective_from', '=', False), ('effective_from', '<=', day),
                            '|', ('effective_until', '=', False), ('effective_until', '>=', day)])

    def action_import_seed(self):
        self._check_manager()
        # Called from a website-bound draft: never silently choose another site.
        self.ensure_one()
        import json
        from odoo.tools import file_open
        from ..services.knowledge_import import import_articles
        with file_open('freemoov_livechat_ai/data/knowledge_seed.json', 'r') as stream:
            entries = json.load(stream)
        import_articles(self.env, self.website_id.id, entries)
        return {'type': 'ir.actions.client', 'tag': 'reload'}
