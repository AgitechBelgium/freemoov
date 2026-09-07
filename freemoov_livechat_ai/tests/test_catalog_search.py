"""Search must tolerate ordinary French without silently removing filters."""
from odoo.tests import tagged

from .common import FreemoovAiCase
from ..services.tools.catalog import chercher_produits


@tagged('post_install', '-at_install', 'freemoov_ai')
class TestCatalogSearch(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        Category = self.env['product.public.category']
        self.root = Category.create({'name': 'Trottinette électrique RecetteXYZ'})
        self.child = Category.create({'name': 'RecetteXYZ Urban', 'parent_id': self.root.id})
        self.parts = Category.create({'name': 'Accessoire RecetteXYZ'})
        self.env['product.template'].create([
            {'name': name, 'list_price': price, 'is_published': published, 'sale_ok': sale,
             'public_categ_ids': [(6, 0, [category.id])]}
            for name, price, published, sale, category in [
                ('RecetteXYZ Trottinette A', 450, True, True, self.root),
                ('RecetteXYZ Trottinette B', 500, True, True, self.child),
                ('RecetteXYZ Trottinette chère', 900, True, True, self.root),
                ('RecetteXYZ Trottinette cachée', 400, False, True, self.root),
                ('RecetteXYZ Trottinette non vendue', 300, True, False, self.root),
                ('RecetteXYZ Accessoire', 100, True, True, self.parts),
            ]
        ])

    def test_plural_category_keeps_budget_publication_and_descendants(self):
        result = chercher_produits(self.env, self.channel,
                                  categorie='trottinettes électriques recetteXYZ', budget_max=600)
        self.assertEqual({p['nom'] for p in result['produits']},
                         {'RecetteXYZ Trottinette A', 'RecetteXYZ Trottinette B'})

    def test_category_accents_case_and_word_order(self):
        result = chercher_produits(self.env, self.channel,
                                  categorie='RECETTEXYZ ELECTRIQUES TROTTINETTES', budget_max=600)
        self.assertEqual(len(result['produits']), 2)

    def test_unknown_category_does_not_fall_back_to_entire_catalog(self):
        result = chercher_produits(self.env, self.channel, categorie='CategorieInexistanteXYZ')
        self.assertEqual(result['produits'], [])

    def test_search_plural_preserves_model_numbers(self):
        self.env['product.template'].create({'name': 'RecetteXYZ Trottinette N15S',
                                            'is_published': True, 'list_price': 500})
        result = chercher_produits(self.env, self.channel, recherche='RecetteXYZ trottinettes N15S')
        self.assertEqual([p['nom'] for p in result['produits']], ['RecetteXYZ Trottinette N15S'])
