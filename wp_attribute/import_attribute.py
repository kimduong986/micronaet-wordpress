#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import pdb
import openerp
import json
import woocommerce
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)

vat_rate = 1.22


class ConnectorCarrierShipping(orm.Model):
    """ Carrier shipping mode
    """
    _name = 'connector.carrier.shipping'
    _description = 'Carrier shipping'
    _order = 'name'

    _columns = {
        'code': fields.char(
            'Codice', size=35, help='Utilizzato per Wordpress', required=True),
        'name': fields.char('Tipo', size=35, required=True),
    }


class ProductProductWebServerIntegration(orm.Model):
    """ Model name: ProductProductWebServer
    """

    _inherit = 'product.product.web.server'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def open_permalink(self, cr, uid, ids, context=None):
        """ Return URL
        """
        product = self.browse(cr, uid, ids, context=context)
        return {
            'type': 'ir.actions.act_url',
            'url': product.permalink,
            'target': 'new',
            }

    def open_variant_detail_form(self, cr, uid, ids, context=None):
        """ Open variant form
        """
        model_pool = self.pool.get('ir.model.data')
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'wp_attribute',
            'view_product_product_web_server_wp_variant_tree')[1]
        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'wp_attribute',
            'view_product_product_web_server_wp_full_detail_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Variante'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'product.product.web.server',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form'), (tree_view_id, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def clean_wp_reference(self, cr, uid, ids, context=None):
        """ Clean procedure for WP product deleted
        """
        return self.write(cr, uid, ids, {
            'wp_it_id': False,
            'wp_en_id': False,
            'wp_es_id': False,
            'wp_fr_id': False,
            'wp_de_id': False,
            'wp_pt_id': False,
            }, context=context)

    def unmark_need_update(self, cr, uid, ids, context=None):
        """ Mark for scheduled update
        """
        return self.write(cr, uid, ids, {
            'need_update': False,
        }, context=context)

    def mark_need_update(self, cr, uid, ids, context=None):
        """ Mark for scheduled update
        """
        return self.write(cr, uid, ids, {
            'need_update': True,
        }, context=context)

    def scheduled_publish_master_selected(self, cr, uid, context=None):
        """ Schedule update for new or marked for update
            Note: All connector update!
        """
        if context is None:
            context = {}

        # No image publish:
        connector_pool = self.pool.get('connector.server')
        connector_ids = connector_pool.search(cr, uid, [
            ('wordpress', '=', True),
        ], context=context)
        connector_pool.write(cr, uid, connector_ids, {
            'wp_publish_image': False,
        }, context=context)

        # Select list:
        forced_ids = set(self.search(cr, uid, [
            '&',
            ('need_update', '=', True),
            ('wp_parent_template', '=', True),
        ], context=context))

        new_ids = set(self.search(cr, uid, [
            '|',
            '|',
            '|',
            '|',
            '|',
            ('wp_it_id', '=', 0),
            ('wp_en_id', '=', 0),
            ('wp_es_id', '=', 0),
            ('wp_fr_id', '=', 0),
            ('wp_de_id', '=', 0),
            ('wp_pt_id', '=', 0),
        ], context=context))

        # Union of new and forced:
        forced_ids.union(new_ids)
        active_ids = tuple(forced_ids)

        if not active_ids:
            _logger.warning('Wordpress product: No need to update')
            return False

        context['active_ids'] = active_ids
        _logger.info('Wordpress: Updating %s products' % len(active_ids))
        res = self.publish_master_now(cr, uid, [], context=context)
        _logger.info('Wordpress: Updated %s products' % len(active_ids))

        # Clean selection when done:
        self.write(cr, uid, active_ids, {
            'need_update': False,
        }, context=context)
        return res  # Normal closing action

    def publish_master_now(self, cr, uid, ids, context=None):
        """ Publish but only this
        """
        if context is None:
            context = {}
        if context.get('active_model') == 'product.product.web.server':
            master_ids = context.get('active_ids', False) or ids
        else:
            master_ids = ids

        connector_pool = self.pool.get('connector.server')
        current = self.browse(cr, uid, master_ids, context=context)[0]
        connector_id = current.connector_id.id

        _logger.warning('Publish master product: %s' % len(master_ids))
        new_context = context.copy()
        new_context['domain_extend'] = [
            ('id', 'in', tuple(master_ids)),
            ]

        return connector_pool.publish_attribute_now(
            cr, uid, [connector_id], context=new_context)

    def link_variant_now(self, cr, uid, ids, context=None):
        """ Link all child variant
        """
        parent_id = ids[0]
        current_product = self.browse(cr, uid, parent_id, context=context)
        connector_id = current_product.connector_id.id
        wp_parent_code = current_product.wp_parent_code
        if not wp_parent_code:
            raise osv.except_osv(
                _('Errore'),
                _('Non presente il codice da usare quindi non possibile!'),
                )

        child_ids = self.search(cr, uid, [
            # Parent code similar:
            ('product_id.default_code', '=ilike', '%s%%' % wp_parent_code),

            ('wp_parent_template', '=', False),  # Not parent product
            ('id', '!=', parent_id),  # Not this
            ('connector_id', '=', connector_id),  # This connector
            ], context=context)

        _logger.info('Updating %s product...' % len(child_ids))
        return self.write(cr, uid, child_ids, {
            'wp_parent_id': parent_id,
            }, context=context)

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def reset_parent(self, cr, uid, parent_ids, context=None):
        """ Remove parent reference
        """
        return self.write(cr, uid, parent_ids, {
            'wp_parent_code': False,
            'wp_parent_id': False,

            # XXX Lang reset:
            'wp_it_id': False,
            'wp_en_id': False,
            'wp_es_id': False,
            'wp_fr_id': False,
            'wp_de_id': False,
            'wp_pt_id': False,
            # todo There's problem if product has no previous parent
            }, context=context)

    def set_as_master_product(self, cr, uid, ids, context=None):
        """ Set as master product for this connection and remove if present
            previous
        """

        current_id = ids[0]
        current_product = self.browse(cr, uid, current_id, context=context)
        connector_id = current_product.connector_id.id
        default_code = current_product.product_id.default_code
        wp_parent_code = current_product.wp_parent_code  # if auto master
        wp_parent_id = current_product.wp_parent_id  # Current master

        # XXX Bad reference (when add new lang):
        wp_it_id = wp_en_id = wp_es_id = wp_fr_id = wp_de_id = wp_pt_id = False
        if wp_parent_id:
            wp_it_id = wp_parent_id.wp_it_id
            wp_en_id = wp_parent_id.wp_en_id
            wp_es_id = wp_parent_id.wp_es_id
            wp_fr_id = wp_parent_id.wp_fr_id
            wp_de_id = wp_parent_id.wp_de_id
            wp_pt_id = wp_parent_id.wp_pt_id
        elif wp_parent_code:
            find_parent_ids = self.search(cr, uid, [
                ('wp_parent_code', '=', wp_parent_code),
                ('id', '!=', current_id),
                ('wp_parent_template', '=', True),
                ], context=context)
            if find_parent_ids:
                wp_parent_id = self.browse(
                    cr, uid, find_parent_ids, context=context)[0]
                wp_it_id = wp_parent_id.wp_it_id
                wp_en_id = wp_parent_id.wp_en_id
                wp_es_id = wp_parent_id.wp_es_id
                wp_fr_id = wp_parent_id.wp_fr_id
                wp_de_id = wp_parent_id.wp_de_id
                wp_pt_id = wp_parent_id.wp_pt_id

        if wp_parent_code:
            # -----------------------------------------------------------------
            # Case: has parent code:
            # -----------------------------------------------------------------
            # Search parent with same code if present
            previous_ids = self.search(cr, uid, [
                ('wp_parent_code', '=', wp_parent_code),
                ('id', '!=', current_id),
                ], context=context)

            # Remove previous situation:
            self.reset_parent(cr, uid, previous_ids, context=context)

            # Force this master with code:
            self.link_variant_now(cr, uid, ids, context=context)

        elif wp_parent_id:
            # -----------------------------------------------------------------
            # Case: parent present:
            # -----------------------------------------------------------------
            # Remove previous situation:
            self.reset_parent(cr, uid, [wp_parent_id], context=context)

        else:
            # -----------------------------------------------------------------
            # Case: no parent no code:
            # -----------------------------------------------------------------
            pass  # nothing to do

        # ---------------------------------------------------------------------
        # Set this as parent
        # ---------------------------------------------------------------------
        return self.write(cr, uid, ids, {
            'wp_parent_template': True,
            'wp_it_id': wp_it_id,
            'wp_en_id': wp_en_id,
            'wp_es_id': wp_es_id,
            'wp_fr_id': wp_fr_id,
            'wp_de_id': wp_de_id,
            'wp_de_id': wp_pt_id,
            }, context=context)

    def _get_wp_pricelist_for_web(
            self, cr, uid, ids, fields=None, args=None, context=None):
        """ Fields function for calculate
        """
        res = {}
        for web in self.browse(cr, uid, ids, context=context):
            res[web.id] = {
                'wp_web_pricelist': self.get_wp_price(web) * vat_rate,
                'wp_web_discounted_net': web.force_discounted / vat_rate,
            }
        return res

    def onchange_force_vat_price(
            self, cr, uid, ids, force_vat_price, context=None):
        """
        """
        res = {'value': {}}
        if force_vat_price:
            res['value']['force_price'] = force_vat_price / vat_rate
        return res

    _columns = {
        'need_update': fields.boolean(
            'Aggiornare',
            help='Viene aggiornato durante l\'operazione in notturna'),
        'wp_parent_template': fields.boolean(
            'Prodotto master',
            help='Prodotto riferimento per raggruppare i prodotti dipendenti'),
        'wp_parent_code': fields.char('Codice appartenenza',
            help='Codice usato per calcolare appartenenza automatica'),
        'wp_parent_id': fields.many2one(
            'product.product.web.server', 'Prodotto padre'),
        'wp_default_choice_id': fields.many2one(
            'product.product.web.server', 'Scelta predefinita',
            help='Se non indicato prende il master'),
        'wp_color_id': fields.many2one(
            'connector.product.color.dot', 'Colore'),

        'force_vat_price': fields.float('Forza prezzo ivato', digits=(16, 2)),
        'wp_web_pricelist': fields.function(
            _get_wp_pricelist_for_web, method=True, multi=True, readonly=True,
            type='float', string='Prezzo listino web',
            help='Prezzo esposto sul sito (barrato se scontato)'),
        'wp_web_discounted_net': fields.function(
            _get_wp_pricelist_for_web, method=True, multi=True, readonly=True,
            type='float', string='Prezzo scontato web',
            help='Prezzo esposto sul sito come scontato'),

        'wp_carrier_weight': fields.float(
            'Peso fisico', digits=(16, 2),
            help='Peso fisico usato per la spedizione'),
        'wp_carrier_volumetric': fields.float(
            'Peso volumetrico', digits=(16, 2),
            help='Peso volumetrico usato per la spedizione'),
        'wp_carrier_mode_ids': fields.many2many(
            'connector.carrier.shipping', 'product_carrier_rel', 'product_id',
            'mode_id', 'Modo spedizione'),
    }

    _sql_constraints = [
        ('parent_code_uniq', 'unique (wp_parent_code)',
            'Il codice di appartenenza deve essere unico!'),
        ]


class ProductProductWebServerRelation(orm.Model):
    """ Model name: ProductProductWebServer
    """

    _inherit = 'product.product.web.server'

    def open_master_variant(self, cr, uid, ids, context=None):
        """ Open variant form
        """
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'wp_attribute',
            'view_product_product_web_server_wp_full_detail_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Variante'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'product.product.web.server',
            'view_id': view_id,
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    _columns = {
        'variant_ids': fields.one2many(
            'product.product.web.server', 'wp_parent_id', 'Varianti'),
        }


class ConnectorProductColorDot(orm.Model):
    """ Model name: ConnectorProductColorDot
    """

    _name = 'connector.product.color.dot'
    _description = 'Color dot'
    _rec_name = 'name'
    _order = 'name'

    def _get_image_name(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        # replace_char_with_blank = '/\\'

        res = {}
        path = False
        with_check = len(ids) == 1
        for image in self.browse(cr, uid, ids, context=context):
            if not path:
                path = os.path.expanduser(image.connector_id.dot_image_path)
            code = image.name.upper()
            # for char in replace_char_with_blank:
            #     code = code.replace(char, ' ')

            name = '%s.png' % code
            fullname = os.path.join(path, name)

            if with_check:
                image_present = os.path.isfile(fullname)
            else:
                image_present = False

            res[image.id] = {
                'image_name': name,
                'image_fullname': fullname,
                'image_present': image_present,
                }
        return res

    _columns = {
        'not_active': fields.boolean('Not active'),
        'connector_id': fields.many2one(
            'connector.server', 'Server', required=True),
        'name': fields.char(
            'Code', size=64, required=True,
            help='Frame-Color used on web site for color (as key!)'),
        'code': fields.char(
            'Sigla', size=10, required=True,
            help='Sigla utilizzata nelle importazioni'),
        'description': fields.char('Web description', size=80, translate=True),
        'hint': fields.char(
            'Hint', size=80, translate=True,
            help='Tooltip text when mouse over image'),
        'dropbox_image': fields.char('Dropbox link', size=180),

        # Image in particular folder
        'image_name': fields.function(
            _get_image_name, method=True, multi=True,
            type='char', string='Image name',),
        'image_fullname': fields.function(
            _get_image_name, method=True, multi=True,
            type='char', string='Image fullname'),
        'image_present': fields.function(
            _get_image_name, method=True, multi=True,
            type='boolean', string='Image present'),
        }


class ProductPublicCategory(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'connector.server'

    _columns = {
        'brand_code': fields.char('Brand code', size=30, required=True,
            help='Brand used for attribute name for company product'),
        'dot_image_path': fields.char('Color image', size=180, required=True,
            help='Color path for dot images, use ~ for home'),
        }

    def external_get_wp_id(self, cr, uid, ids, context=None):
        """ External extract data to get Code - Lang: WP ID
        """
        web_pool = self.pool.get('product.product.web.server')
        connector_id = ids[0]
        not_found = []
        # TODO manage not parent product!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        # Read WP product:
        wcapi = self.get_wp_connector(
            cr, uid, connector_id, context=context)
        _logger.warning('Read all product on wordpress:')

        parameter = {'per_page': 20, 'page': 1}
        variation_parameters = {'per_page': 30, 'page': 1}
        theres_data = True
        while theres_data:
            call = 'products'
            reply = self.wp_loopcall(
                wcapi, 'get', call, params=parameter).json()

            parameter['page'] += 1

            for item in reply:
                wp_id = item['id']
                lang = item['lang']
                default_code = item['sku']
                field = 'wp_%s_id' % lang

                if not default_code:
                    not_found.append(wp_id)
                    _logger.warning('Product not found: %s lang: %s' % (
                        default_code, lang))

                web_ids = web_pool.search(cr, uid, [
                    ('product_id.default_code', '=', default_code),
                    ], context=context)
                if not web_ids:
                    not_found.append(wp_id)
                    _logger.warning('Code: %s lang: %s not found on DB' % (
                        default_code, lang))
                    continue

                if len(web_ids) > 1:
                    pdb.set_trace()

                web_product = web_pool.browse(
                    cr, uid, web_ids, context=context)[0]
                this_wp_id = eval('web_product.%s' % field)
                if this_wp_id != wp_id:
                    not_found.append(wp_id)
                    continue

                # Update product reference:
                if not this_wp_id:
                    web_pool.write(cr, uid, web_ids, {
                        field: wp_id,
                        }, context=context)
            break # TODO remove
        return not_found

    def publish_attribute_now(self, cr, uid, ids, context=None):
        """ Publish now button
            Used also for more than one elements (not only button click)
            Note all product must be published on the same web server!
            """
        """def split_code(default_code, lang='it'):
            ''' Split 2 part of code
            '''   
            default_code = (default_code or '')[:12] # No exta part
            return (
                default_code[:6].strip(),
                '%s-%s-%s' % (
                    default_code[6:8].strip().upper() or 'NE',  # XXX Neutro
                    default_code[8:].strip().upper(),
                    lang.upper(),
                    ),
                )"""

        def lang_sort(lang):
            """ Setup lang order
            """
            if 'it' in lang:
                return 1
            elif 'en' in lang:
                return 2

        # =====================================================================
        # Log operation on Excel file:
        # ---------------------------------------------------------------------
        now = ('%s' % datetime.now()).replace(
            '/', '').replace(':', '').replace('-', '')[:30]
        ws_name = now
        excel_pool = self.pool.get('excel.writer')
        excel_pool.create_worksheet(ws_name)
        excel_pool.set_format()
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'text': excel_pool.get_format('text'),
            }
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            'Commento',
            'Chiamata',
            'End point',
            'Data',
            'Reply',
            ], default_format=excel_format['header'])
        excel_pool.column_width(ws_name, [30, 20, 30, 50, 100])
        # =====================================================================

        # ---------------------------------------------------------------------
        # Handle connector:
        # ---------------------------------------------------------------------
        variation_parameters = {'per_page': 30, 'page': 1}

        # Sort order and list of languages:
        langs = [
            'it_IT',
            'en_US',
            ]
        default_lang = 'it'

        if context is None:
            context = {}

        # Data publish selection (remove this part from publish:
        unpublished = []

        # Pool used:
        web_product_pool = self.pool.get('product.product.web.server')
        dot_pool = self.pool.get('connector.product.color.dot')

        connector_id = ids[0]
        server_proxy = self.browse(cr, uid, connector_id, context=context)
        # brand_code = server_proxy.brand_code # As default

        if server_proxy.wp_publish_image:
            _logger.warning('Publish attribute on wordpress with image')
        else:
            unpublished.append('image')
            _logger.warning('Publish attribute on wordpress without image')

        # Read WP Category present:
        wcapi = self.get_wp_connector(
            cr, uid, connector_id, context=context)

        # ---------------------------------------------------------------------
        #                          COLLECT DATA:
        # ---------------------------------------------------------------------
        domain = [
            ('connector_id', '=', ids[0]),
            ('wp_parent_template', '=', True),
            # ('wp_it_id', '=', False),  # New master
            ]
        domain_extend = context.get('domain_extend')
        if domain_extend:
            domain.extend(domain_extend)
            _logger.warning('Domain extended: %s' % (domain, ))

        product_ids = web_product_pool.search(cr, uid, domain, context=context)
        _logger.warning('Product for this connector: %s...' % len(product_ids))

        product_db = {}  # Master database for lang - parent - child
        lang_color_db = {}  # Master list for color in default lang
        fabric_color_odoo = {}  # Dropbox link for image
        product_default_color = {}  # First variant showed

        parent_total = 0
        for odoo_lang in langs:
            lang = odoo_lang[:2]
            context_lang = context.copy()
            context_lang['lang'] = odoo_lang

            # Start with lang level:
            product_db[odoo_lang] = {}
            lang_color_db[lang] = []

            for parent in web_product_pool.browse(  # Default_selected product:
                    cr, uid, product_ids, context=context_lang):
                parent_total += 1

                # TODO default_selected is first element
                default_selected = parent  # TODO Change during next loop:
                product_db[odoo_lang][parent] = [default_selected, []]

                for variant in parent.variant_ids:
                    # Note: first variant is parent:
                    product = variant.product_id
                    default_code = product.default_code or ''
                    color = variant.wp_color_id.name
                    attribute = color + '-' + lang
                    fabric_color_odoo[attribute] = variant.wp_color_id

                    # Save color for attribute update
                    if attribute not in lang_color_db[lang]:
                        lang_color_db[lang].append(attribute)

                    # Save variant with color element:
                    product_db[odoo_lang][parent][1].append(
                        (variant, attribute))

                # Save default color for lang product
                wp_default_choice_id = \
                    default_selected.wp_default_choice_id or default_selected

                # Save default (changed) in master reference:
                product_default_color[
                    (default_selected, lang)
                    ] = wp_default_choice_id.wp_color_id.name + '-' + lang

        _logger.warning('Parent found: %s' % parent_total)

        # ---------------------------------------------------------------------
        #               ATTRIBUTES: (mandatory: Tessuto, Brand)
        # ---------------------------------------------------------------------
        call = 'products/attributes'
        current_wp_attribute = self.wp_loopcall(
            wcapi, 'get', call, params=variation_parameters).json()

        # =====================================================================
        # Excel log:
        # ---------------------------------------------------------------------
        row += 1
        excel_pool.write_xls_line(ws_name, row, [
            'Richiesta elenco attributi:',
            ], default_format=excel_format['title'])
        row += 1
        excel_pool.write_xls_line(ws_name, row, [
            'Elenco attributi',
            'get',
            call,
            '',
            u'%s' % (current_wp_attribute, ),
            ], default_format=excel_format['text'])
        # =====================================================================

        error = ''
        try:
            if current_wp_attribute['data']['status'] >= 400:
                error = current_wp_attribute['message']
        except:
            pass

        if error:
            raise osv.except_osv(_('Connection error:'), error)

        # ---------------------------------------------------------------------
        # Search Master Attribute:
        # ---------------------------------------------------------------------
        attribute_id = {
            'Tessuto': False,
            'Brand': False,
            'Materiale': False,
            # TODO Material, Certificate
            }
        _logger.warning('Searching attribute %s...' % (attribute_id.keys(), ))
        for record in current_wp_attribute:
            name = record['name']
            # lang = record['lang'] # todo not present!
            if name in attribute_id:
                attribute_id[name] = record['id']
        if not all(attribute_id.values()):
            raise osv.except_osv(
                _('Attribute error'),
                _('Cannot find some attribute terms %s!') % attribute_id,
                )

        # ---------------------------------------------------------------------
        #                   TERMS: (for Tessuto, Attribute)
        # ---------------------------------------------------------------------
        current_wp_terms = []
        theres_data = True
        parameter = {'per_page': 30, 'page': 1}

        _logger.warning('Search all terms for attribute %s...' % (
            attribute_id.keys(), ))

        # =====================================================================
        # Excel log:
        # ---------------------------------------------------------------------
        row += 1
        excel_pool.write_xls_line(ws_name, row, [
            'Richiesta termini:',
            ], default_format=excel_format['title'])
        # =====================================================================

        # Fabric attribute:
        while theres_data:
            call = 'products/attributes/%s/terms' % attribute_id['Tessuto']
            res = self.wp_loopcall(
                wcapi, 'get', call, params=parameter).json()

            # =================================================================
            # Excel log:
            # -----------------------------------------------------------------
            row += 1
            excel_pool.write_xls_line(ws_name, row, [
                'Lettura attributi tessuto',
                'get',
                call,
                u'%s' % (parameter, ),
                u'%s' % (res, ),
                ], default_format=excel_format['text'])
            # =================================================================
            parameter['page'] += 1

            try:
                if res.get['data']['status'] >= 400:
                    raise osv.except_osv(
                        _('Category error:'),
                        _('Error getting category list: %s' % (res, )),
                        )
            except:
                pass  # Records present
            if res:
                current_wp_terms.extend(res)
            else:
                theres_data = False

        # todo need lang?
        lang_color_terms = {
            'it': {},
            'en': {},
            }
        for record in current_wp_terms:
            name = record['name']
            key = name[:-3]
            lang = record['lang']
            lang_color_terms[lang][key] = record['id']

        # ---------------------------------------------------------------------
        #                        TERMS: (for Brand Attribute)
        # ---------------------------------------------------------------------
        lang_brand_terms = {}  # not needed for now

        call = 'products/attributes/%s/terms' % attribute_id['Brand']

        for record in self.wp_loopcall(
                wcapi, 'get', call, params=variation_parameters).json():

            lang = record['lang']
            name = record['name']

            if lang not in lang_brand_terms:
                lang_brand_terms[lang] = {}

            lang_brand_terms[lang][name] = record['id']

        # ---------------------------------------------------------------------
        # Update / Create: todo only fabric?
        # ---------------------------------------------------------------------
        # Start from IT (default) lang:
        for lang in sorted(lang_color_db, key=lambda l: lang_sort(l)):
            # Clean every loop:
            data = {
                'create': [],
                'update': [],
                'delete': [],
                }
            for attribute in lang_color_db[lang]:
                key = attribute[:-3] # Key element (without -it or -en)
                odoo_color = fabric_color_odoo[attribute]
                item = {
                    'name': attribute,
                    'lang': lang,
                    'color_name': odoo_color.hint,
                    }

                # Image part:
                if odoo_color.dropbox_image:
                    item['color_image'] = odoo_color.dropbox_image

                if lang != default_lang:  # Different language:
                    # todo correct
                    wp_it_id = lang_color_terms[default_lang].get(key)
                    if wp_it_id:
                        item.update({
                            'translations': {'it': wp_it_id}
                            })
                    else:
                        _logger.error('Attribute not found %s %s!' % (
                            key,
                            lang,
                            ))
                        # TODO manage?

                # Only create:
                if key in lang_color_terms[lang]:
                    data['update'].append(item)
                else:
                    data['create'].append(item)

            # -----------------------------------------------------------------
            # Delete:
            # -----------------------------------------------------------------
            # todo Not for now:
            # todo correct
            # for name in lang_color_terms:
            #    if name not in lang_color_db:
            #        data['delete'].append(lang_color_terms[name])

            # -----------------------------------------------------------------
            # Batch operation (fabric terms for attribute manage):
            # -----------------------------------------------------------------
            try:
                # =============================================================
                # Excel log:
                # -------------------------------------------------------------
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    'Aggiornamento tessuti:',
                    ], default_format=excel_format['title'])
                # =============================================================

                if any(data.values()):  # only if one is present
                    call = 'products/attributes/%s/terms/batch' % \
                        attribute_id['Tessuto']
                    res = self.wp_loopcall(
                        wcapi, 'post', call, data=data).json()

                    # =========================================================
                    # Excel log:
                    # ---------------------------------------------------------
                    row += 1
                    excel_pool.write_xls_line(ws_name, row, [
                        'Batch attributi tessuto',
                        'post',
                        call,
                        u'%s' % (data),
                        u'%s' % (res, ),
                        ], default_format=excel_format['text'])
                    # =========================================================

                    # ---------------------------------------------------------
                    # Save WP ID (only in dict not in ODOO Object)
                    # ---------------------------------------------------------
                    for record in res.get('create', ()):
                        try:
                            key = record['name'][:-3]
                            wp_id = record['id']
                            if not wp_id:  # TODO manage error:
                                _logger.error(
                                    'Not Updated wp_id for %s' % wp_id)
                                continue

                            # Update for language not IT (default):
                            lang_color_terms[lang][key] = wp_id
                        except:
                            _logger.error('No name in %s' % record)
                            pdb.set_trace()
                            continue
            except:
                raise osv.except_osv(
                    _('Error'),
                    _('Wordpress server timeout! \n[%s]') % (sys.exc_info(), ),
                    )

        # ---------------------------------------------------------------------
        #                       PRODUCT AND VARIATIONS:
        # ---------------------------------------------------------------------
        permalinks = {}
        translation_lang = {}
        parent_unset = []

        wp_variant_lang_ref = {}
        for odoo_lang in sorted(product_db, key=lambda l: lang_sort(l)):
            context_lang = context.copy()
            context_lang['lang'] = odoo_lang
            lang = odoo_lang[:2]

            for parent in product_db[odoo_lang]:
                master_record, variants = product_db[odoo_lang][parent]
                master_product = master_record.product_id
                master_code = master_product.default_code

                # -------------------------------------------------------------
                # TEMPLATE PRODUCT: Upload product reference:
                # -------------------------------------------------------------
                # 1. Call upload original procedure:
                context['log_excel'] = []
                translation_lang.update(
                    web_product_pool.publish_now(
                        cr, uid, [master_record.id], context=context))
                # TODO Launch only for default lang? (this run twice!)
                # REMOVE: Update brand terms for product:

                # =============================================================
                # Excel log:
                # -------------------------------------------------------------
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    'Pubblicazione prodotto base: %s' % master_code,
                    ], default_format=excel_format['title'])

                for log in context['log_excel']:
                    row += 1
                    excel_pool.write_xls_line(
                        ws_name, row, log,
                        default_format=excel_format['text'], col=1)
                # =============================================================

                lang_product_default_color = product_default_color[
                    (master_record, lang)]

                # -------------------------------------------------------------
                # Setup default attribute:
                # -------------------------------------------------------------
                wp_id, lang_master_name = translation_lang.get(
                    master_code, {}).get(lang, (False, False))
                data = {
                    # Only color (not brand as default)
                    'default_attributes': [{
                        'id': attribute_id['Tessuto'],
                        'option': lang_product_default_color,
                        }],

                    # Write to force code in attribute:
                    'lang': lang,
                    'name': lang_master_name,
                    }

                call = 'products/%s' % wp_id
                reply = self.wp_loopcall(
                    wcapi, 'put', call, data=data).json()

                # =============================================================
                # Excel log:
                # -------------------------------------------------------------
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    'Pubblicazione varianti lingua %s' % lang,
                    ], default_format=excel_format['title'])
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    'Default nella scheda prodotto',
                    'put',
                    call,
                    u'%s' % (data, ),
                    u'%s' % (reply, ),
                    ], default_format=excel_format['text'])
                # =============================================================

                if not wp_id:
                    _logger.error(
                        'Cannot found wp_id, code %s' % default_code)
                    # XXX Cannot update!
                    continue
                else:
                    permalink = reply['permalink']
                    if lang == 'it' and permalink:
                        permalinks[parent.id] = permalink

                # -------------------------------------------------------------
                #          VARIANTS: Setup color terms for product
                # -------------------------------------------------------------
                # 2. Update attributes:
                # First block for setup color:
                data = {
                    # To force lang procedure:
                    'lang': lang,
                    'name': lang_master_name,

                    # ---------------------------------------------------------
                    # 1. Fabric XXX mandatory!
                    # ---------------------------------------------------------
                    'attributes': [{
                        'id': attribute_id['Tessuto'],
                        'options': [],
                        'variation': True,
                        'visible': True,
                        }]}

                # -------------------------------------------------------------
                # 2. Brand! (XXX mandatory!)
                # -------------------------------------------------------------
                if master_record.brand_id:
                    data['attributes'].append({
                        'id': attribute_id['Brand'],
                        'options': [master_record.brand_id.name],
                        'variation': False,
                        'visible': True,
                        })

                # -------------------------------------------------------------
                # 3. Material: XXX facoltative
                # -------------------------------------------------------------
                data['attributes'].append({
                    'id': attribute_id['Materiale'],
                    'options': [],
                    'variation': False,
                    'visible': True,
                    })

                # Update first element colors:
                for line, variant_color in variants:
                    # Get variant color:
                    data['attributes'][0]['options'].append(variant_color)

                    # ---------------------------------------------------------
                    # Update material block:
                    # ---------------------------------------------------------
                    for material in line.material_ids:
                        material_wp_id = eval('material.wp_%s_id' % lang)
                        if material_wp_id and material.name not in \
                                data['attributes'][2]['options']:
                            data['attributes'][2]['options'].append(
                                material.name)

                try:
                    call = 'products/%s' % wp_id
                    res = self.wp_loopcall(
                        wcapi, 'post', call, data=data).json()

                    # =========================================================
                    # Excel log:
                    # ---------------------------------------------------------
                    row += 1
                    excel_pool.write_xls_line(ws_name, row, [
                        'Aggiornamento termini attributi',
                        'post',
                        call,
                        u'%s' % (data, ),
                        u'%s' % (res, ),
                        ], default_format=excel_format['text'])
                    # =========================================================

                except:
                    raise osv.except_osv(
                        _('Error'),
                        _('Wordpress server not answer, timeout!'),
                        )

                # -------------------------------------------------------------
                # Upload product variations:
                # -------------------------------------------------------------
                call = 'products/%s/variations' % wp_id
                res = self.wp_loopcall(
                    wcapi, 'get', call, params=variation_parameters).json()

                # =============================================================
                # Excel log:
                # -------------------------------------------------------------
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    'Lettura varianti attuali',
                    'get',
                    call,
                    u'',
                    u'%s' % (res, ),
                    ], default_format=excel_format['text'])
                # =============================================================

                data = {
                    'delete': [],
                    }

                # -------------------------------------------------------------
                #                     VARIANTS: Creation
                # -------------------------------------------------------------
                for item in res:
                    # No option
                    if not item['attributes'] or not item['attributes'][0][
                            'option']:
                        data['delete'].append(item['id'])
                    else:
                        # todo TEST BETTER:
                        wp_variant_lang_ref[(
                            web_product_pool.wp_clean_code(
                                item['sku'], destination='odoo'),
                            item['lang'])] = item['id']
                        """
                        if lang == default_lang:
                            wp_variant_lang_ref[
                                (item['sku'], lang)] = item['id']
                        else:
                            # Variant has no sku, compose from parent + option
                            option = False
                            for attribute in item['attributes']:
                                if attribute['id'] == attribute_id['Tessuto']:
                                    option = attribute['option']
                            if not option:
                                _logger.error(
                                    'Cannot get sku for variant %s' % (item, ))
                                continue
                                
                            option = option[:-3].replace('-', '') # remove lang
                            wp_variant_lang_ref[(
                                '%-6s%s' %parent, option), # XXX 
                                lang,
                                )] = item['id']
                        """

                # Clean variant no color:
                if data['delete']:
                    call = 'products/%s/variations/batch' % wp_id
                    self.wp_loopcall(
                        wcapi, 'post', call, data=data).json()
                    # todo log

                for line, fabric_code in variants:
                    variant = line.product_id
                    variant_code = variant.default_code
                    variant_id = wp_variant_lang_ref.get(
                        (variant_code, lang), False)
                    variant_it_id = wp_variant_lang_ref.get(
                        (variant_code, default_lang), False)

                    # todo Price for S (ingle)
                    price = web_product_pool.get_wp_price(line)
                    sale_price = u'%s' % (
                        (line.force_discounted / vat_rate) or '')
                    # todo error: is always 0
                    # sale_price = u'%s' % (line.wp_web_discounted_net or '')

                    # Description:
                    name = line.force_name or variant.name or u''
                    description = line.force_description or \
                        variant.emotional_description or \
                        variant.large_description or u''
                    # before: line.force_name or \
                    short_description = \
                        variant.emotional_short_description or name
                    stock_quantity, stock_comment = \
                        web_product_pool.get_existence_for_product(
                            cr, uid, line, context=context)

                    multiplier = line.price_multi or 1
                    if multiplier > 1:
                        stock_quantity = stock_quantity // multiplier

                    # Create or update variant:
                    data = {
                        'regular_price': u'%s' % price,
                        'sale_price': sale_price,
                        'short_description': short_description,
                        'description': description,
                        'lang': lang,
                        'weight': '%s' % line.wp_volume,  # X Used for volume
                        'menu_order': parent.wp_sequence,
                        'dimensions': {
                            'length': '%s' % line.pack_l,
                            'height': '%s' % line.pack_h,
                            'width': '%s' % line.pack_p,
                            },
                        'manage_stock': True,
                        'stock_quantity': stock_quantity,
                        'status': 'publish' if line.published else 'private',
                        'attributes': [{
                            'id': attribute_id['Tessuto'],
                            'option': fabric_code,
                        }],
                    }

                    # ---------------------------------------------------------
                    # GTIN Part:
                    # ---------------------------------------------------------
                    gtin = self.get_gtin(line)
                    if gtin:
                        data['gtin'] = gtin

                    # 'slug': self.get_lang_slug(variant_code, lang),
                    # todo
                    # stock_status
                    # 'weight': '%s' % line.weight,

                    # ---------------------------------------------------------
                    # Language block:
                    # ---------------------------------------------------------
                    # used always?:
                    data['sku'] = web_product_pool.wp_clean_code(variant_code)
                    if default_lang == lang:  # Add language default ref.
                        # data['sku'] = self.wp_clean_code(variant_code)
                        pass
                    else:
                        if not variant_it_id:
                            _logger.error(
                                'Cannot update variant in lang, no it: %s' % (
                                    variant_code
                                    ))
                            continue  # XXX test if correct!

                        data['translations'] = {
                            'it': variant_it_id,  # Created before
                            }

                    # ---------------------------------------------------------
                    # Material block terms:
                    # ---------------------------------------------------------
                    for material in line.material_ids:
                        material_wp_id = eval('material.wp_%s_id' % lang)
                        if material_wp_id:
                            data['attributes'].append({
                                'id': attribute_id['Materiale'],
                                'option': material.name,
                                })

                    # ---------------------------------------------------------
                    # Images block:
                    # ---------------------------------------------------------
                    image = False
                    if 'image' not in unpublished:
                        image = web_product_pool.get_wp_image(
                            line, variant=True)

                    if image:
                        data['image'] = image

                    if variant_id:  # Update
                        operation = 'UPD'
                        call = 'products/%s/variations/%s' % (
                            wp_id,
                            variant_id,
                            )
                        res = self.wp_loopcall(
                            wcapi, 'put', call, data=data).json()
                        # todo permalink update
                        # del(current_variant[fabric_code]) #for clean operat.

                        # =====================================================
                        # Excel log:
                        # -----------------------------------------------------
                        row += 1
                        excel_pool.write_xls_line(ws_name, row, [
                            'Aggiorna variante',
                            'put',
                            call,
                            u'%s' % (data, ),
                            u'%s' % (res, ),
                            ], default_format=excel_format['text'])
                        # =====================================================

                    else:  # Create
                        # todo always pass image when new:
                        if 'image' not in data:
                            image = web_product_pool.get_wp_image(
                                line, variant=True)
                            if image:
                                data['image'] = image

                        operation = 'NEW'
                        call = 'products/%s/variations' % wp_id
                        res = self.wp_loopcall(
                            wcapi, 'post', call, data=data).json()
                        # todo permalink update

                        # =====================================================
                        # Excel log:
                        # -----------------------------------------------------
                        row += 1
                        excel_pool.write_xls_line(ws_name, row, [
                            'Crea variante',
                            'post',
                            call,
                            u'%s' % (data, ),
                            u'%s' % (res, ),
                            ], default_format=excel_format['text'])
                        # =====================================================

                        try:
                            variant_id = res['id']
                            # Save for other lang:
                            wp_variant_lang_ref[
                                (variant_code, lang)] = variant_id
                        except:
                            variant_id = '?'

                    if res.get('data', {}).get('status', 0) >= 400:
                        _logger.error('%s Variant: %s [%s] >> %s [%s] %s' % (
                            operation,
                            variant_code,
                            variant_id,
                            fabric_code,
                            res.get('message', 'Error without comment'),
                            wp_id,
                            ))
                    else:
                        _logger.info('%s Variant %s [%s] linked to %s' % (
                            operation,
                            variant_code,
                            variant_id or 'NEW',
                            wp_id,
                            ))
                # TODO Delete also remain

        if parent_unset:
            _logger.error('Set parent for code start with: %s' % (
                parent_unset))

        # Update permalinks:
        for master_id in permalinks:
            web_product_pool.write(cr, uid, [parent.id], {
                'permalink': permalinks[master_id],
            }, context=context)

        # ---------------------------------------------------------------------
        # Attribute update ODOO VS WP:
        # ---------------------------------------------------------------------
        # todo
        # Update dot color images and records! (here?)

        # Return log calls:
        return excel_pool.return_attachment(
            cr, uid, 'Log call', name_of_file='call.xlsx', context=context)
