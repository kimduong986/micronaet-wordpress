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
import openerp
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


class ConnectorServer(orm.Model):
    """ Model name: ConnectorServer
    """
    _inherit = 'connector.server'

    # Overridable function to get sold status
    def sold_product_on_website(self, cr, uid, ids, context=None):
        """ Return sold product for default_code
        """
        return {}

    def extract_wordpress_published_report(self, cr, uid, ids, context=None):
        """ Extract list of published elements:
        """
        def get_image_list(self, product, album_ids, context=None):
            """ Fields function for calculate
            """
            ctx = context.copy()
            ctx['return_url'] = True
            web_product_pool = self.pool.get('product.product.web.server')
            if context is None:
                context = {}

            image_mode = context.get('image_mode', 'filename')

            res = ''
            for image in sorted(
                    product.image_ids,
                    key=lambda x: x.filename[:-4]):
                if image.album_id.id in album_ids:
                    if image_mode == 'filename':
                        res += u'[%s: %s]' % (
                            image.album_id.code, image.filename)
                    else:
                        res += u'[%s: Media URL: %s]' % (
                            image.album_id.code,
                            web_product_pool.get_pickle_album_file(image, ctx),
                            )
            return res

        stock_status = True

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        product_pool = self.pool.get('product.product')
        connector_pool = self.pool.get('product.product.web.server')
        server_pool = self.pool.get('connector.server')

        # Get sold product database:
        sold_product = self.sold_product_on_website(
            cr, uid, ids, context=context)

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        connector = self.browse(cr, uid, ids, context=context)[0]
        album_ids = [item.id for item in connector.album_ids]

        ws_name = 'Prodotti'
        excel_pool.create_worksheet(ws_name)

        # Load formats:
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
                },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
                },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
                },
            }

        # ---------------------------------------------------------------------
        # Published product:
        # ---------------------------------------------------------------------
        # Width
        excel_pool.column_width(ws_name, [
            5, 15, 10, 20, 15,
            30, 70,
            30, 70,
            50, 10, 30, 5, 5,
            10,  # Sold
            10, 10, 5, 10,
            10, 10,
            10, 10, 35,  # Trasport
            5, 20, 30, 7,
            7,
            10, 5, 15,
            6, 6, 6, 6, 6, 6,
            25, 25, 25, 25, 25, 25, 25, 25, 25, 25,
            40, 40,
            ])

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            # TODO aggiungere wp_sequence
            'Pubbl.', 'Codice', 'GTIN', 'Colore', 'Brand',
            'Nome', 'Descrizione',
            '(Name)', '(Description)',
            'Categorie', 'Mag.', 'Dett. mag.', 'Extra prezzo', 'Molt.',
            'Venduto',
            'Prezzo ODOO', 'Forz.', 'Prezzo WP', 'Scontato',
            'Cat. Stat.', 'Peso',
            'Peso spediz.', 'Peso volum. sped.', 'Tipi sped.',
            'Mod. imb.', 'Imballo', 'Dimensioni prodotto', 'Vol.',
            'Garanzia',
            'Tipo WP', 'Master', 'Padre',
            'WPID it.', 'WPID en.', 'WPID es.', 'WPID fr.', 'WPID de.', 'WPID pt.',
            'Bullet 1', '(Bullet 1)', 'Bullet 2', '(Bullet 2)',
            'Bullet 3', '(Bullet 3)', 'Bullet 4', '(Bullet 4)',
            'Bullet 5', '(Bullet 5)',
            'Immagini', 'Link',
            ], default_format=excel_format['header'])

        line_ids = connector_pool.search(cr, uid, [
            ('connector_id', '=', connector.id),
            ], context=context)
        _logger.warning('Selected product: %s' % len(line_ids))

        # Italian report:
        grouped = {}
        color_format_all = {}
        selected = {}
        not_selected = []

        for line in sorted(connector_pool.browse(
                cr, uid, line_ids, context=context),
                key=lambda p: (
                    p.product_id.default_code,
                    p.product_id.name),
                ):
            parent = line.wp_parent_id
            product = line.product_id
            default_code = product.default_code or ''
            sold = sold_product.get(default_code, '')

            # -----------------------------------------------------------------
            # Parameters:
            # -----------------------------------------------------------------
            # Images:
            image = get_image_list(
                self, product, album_ids, context=context)
            dropbox_image = get_image_list(
                self, product, album_ids, context={'image_mode': 'url'})

            # GTIN
            gtin = server_pool.get_gtin(line)

            # Stock:
            stock_qty, stock_comment = \
                connector_pool.get_existence_for_product(
                    cr, uid, line, context=context)

            multiplier = line.price_multi or 1
            if multiplier > 1:
                stock_qty = stock_qty // multiplier

            published = 'X' if line.published else ''
            if not published:
                color_format = excel_format['yellow']
            elif stock_qty <= 0:
                color_format = excel_format['red']
            else:
                color_format = excel_format['black']
                # not_selected.append((product, 'no stock'))
                # continue

            # -----------------------------------------------------------------
            # Group data:
            # -----------------------------------------------------------------
            default_code6 = default_code[:6].strip()
            if default_code6:
                if default_code6 not in grouped:
                    grouped[default_code6] = []
                grouped[default_code6].append(default_code[6:].strip())

            row += 1
            selected[line.id] = row  # To update english lang
            color_format_all[line.id] = color_format

            # Readability:
            short_description = line.force_name or \
                product.emotional_short_description or \
                product.name or u''

            description = line.force_description or \
                product.emotional_description or \
                product.large_description or u''

            odoo_price = line.force_price or product.lst_price
            price = connector_pool.get_wp_price(line)

            excel_pool.write_xls_line(
                ws_name, row, [
                    published,
                    default_code,
                    gtin or '',
                    line.wp_color_id.name or '',
                    line.brand_id.name or '',
                    short_description,  # product.name,
                    description,  # product.large_description or '',
                    '',
                    '',
                    ', '.join(tuple(
                        [c.name for c in line.wordpress_categ_ids])),
                    stock_qty,
                    stock_comment,

                    line.price_extra,
                    line.price_multi,

                    sold,

                    odoo_price,
                    price,
                    'X' if line.force_price else '',
                    line.force_discounted or '',

                    product.statistic_category or '',
                    line.weight,

                    # Transport:
                    parent.wp_carrier_weight,
                    parent.wp_carrier_volumetric,
                    ', '.join(
                        [item.name for item in parent.wp_carrier_mode_ids]),
                    'X' if product.model_package_id else '',
                    '%s x %s x %s' % (
                        line.pack_l, line.pack_h, line.pack_p),
                    line.weight_aditional_info,
                    line.wp_volume,
                    'X' if line.lifetime_warranty else '',

                    line.wp_type or '',
                    'X' if line.wp_parent_template else '',
                    line.wp_parent_id.product_id.default_code or '',

                    line.wp_it_id,
                    line.wp_en_id,
                    line.wp_es_id,
                    line.wp_fr_id,
                    line.wp_de_id,
                    line.wp_pt_id,

                    line.bullet_point_1 or '',
                    '',
                    line.bullet_point_2 or '',
                    '',
                    line.bullet_point_3 or '',
                    '',
                    line.bullet_point_4 or '',
                    '',
                    line.bullet_point_5 or '',
                    '',

                    image,
                    dropbox_image,
                    ], default_format=color_format['text'])

        # English report (integration):
        product_ids = product_pool.search(cr, uid, [
            ('id', 'in', selected.keys()),
            ], context=context)
        _logger.warning('Update English text: %s' % len(product_ids))

        ctx = context.copy()
        ctx['lang'] = 'en_US'
        # TODO use line loop (for force name!!!)
        for line in connector_pool.browse(
                cr, uid, line_ids, context=ctx):
            product = line.product_id
            row = selected[line.id]
            color_format = color_format_all[line.id]

            # Readability:
            # line.force_name or \
            # TODO problem when forced
            short_description = product.emotional_short_description or \
                product.name or u''

            description = line.force_description or \
                product.emotional_description or \
                product.large_description or u''

            excel_pool.write_xls_line(
                ws_name, row, [
                    short_description,  # product.name,
                    description,  # product.large_description or '',
                    ], default_format=color_format['text'], col=5)

            # Bullet point:
            excel_pool.write_xls_line(
                ws_name, row, [line.bullet_point_1 or ''],
                default_format=color_format['text'], col=32)
            excel_pool.write_xls_line(
                ws_name, row, [line.bullet_point_2 or ''],
                default_format=color_format['text'], col=34)
            excel_pool.write_xls_line(
                ws_name, row, [line.bullet_point_3 or ''],
                default_format=color_format['text'], col=36)
            excel_pool.write_xls_line(
                ws_name, row, [line.bullet_point_4 or ''],
                default_format=color_format['text'], col=38)
            excel_pool.write_xls_line(
                ws_name, row, [line.bullet_point_5 or ''],
                default_format=color_format['text'], col=40)

        # ---------------------------------------------------------------------
        # Web Schema
        # ---------------------------------------------------------------------
        ws_name = 'Web schema'
        excel_pool.create_worksheet(ws_name)

        # Width
        excel_pool.column_width(ws_name, [20, 60])

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            'Codice padre', 'Telaio-Colori',
            ], default_format=excel_format['header'])

        for code6 in grouped:
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    code6,
                    ', '.join(grouped[code6]),
                    ], default_format=excel_format['black']['text'])

        # ---------------------------------------------------------------------
        # Not selected product:
        # ---------------------------------------------------------------------
        ws_name = 'Scartati'
        excel_pool.create_worksheet(ws_name)

        # Width
        excel_pool.column_width(ws_name, [15, 40, 30])

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            'Codice', 'Nome', 'Motivo',
            ], default_format=excel_format['header'])

        for product, reason in not_selected:
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    product.default_code or '',
                    product.name,
                    reason,
                    ], default_format=excel_format['black']['text'])

        # ---------------------------------------------------------------------
        # Removed product:
        # ---------------------------------------------------------------------
        ws_name = 'Non inclusi'
        excel_pool.create_worksheet(ws_name)

        # Width
        excel_pool.column_width(ws_name, [15, 40, 30])
        # TODO Correct?
        product_ids = product_pool.search(cr, uid, [
            ('statistic_category', '!=', 'P01'),
            ], context=context)
        _logger.warning('Not selected product: %s' % len(product_ids))

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            'Codice', 'Nome', 'Categ. stat.',
            ], default_format=excel_format['header'])
        for product in sorted(product_pool.browse(
                cr, uid, product_ids, context=context),
                key=lambda p: (p.default_code, p.name),
                ):

            row += 1
            excel_pool.write_xls_line(
                ws_name, row, [
                    product.default_code or '',
                    product.name,
                    product.statistic_category or '',
                    ], default_format=excel_format['black']['text'])

        return excel_pool.return_attachment(cr, uid, 'web_product')

    def extract_wordpress_accounting_report(self, cr, uid, ids, context=None):
        """ Extract list of published elements for accounting:
        """
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        connector_pool = self.pool.get('product.product.web.server')

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        connector = self.browse(cr, uid, ids, context=context)[0]
        ws_name = 'Gestionale'
        excel_pool.create_worksheet(ws_name)

        # Load formats:
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
                },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
                },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
                },
            }

        # ---------------------------------------------------------------------
        # Published product:
        # ---------------------------------------------------------------------
        # Width
        excel_pool.column_width(ws_name, [
            5, 15, 35, 5, 20, 20,
            30, 10, 5, 5,
            15, 15,
            15, 12, 12, 12,
            15,
            ])

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            'Pubbl.', 'Codice', 'Nome', 'UM', 'Colore', 'Brand',
            'Categorie', 'Magazzino', 'Q x pack', 'Molt.',
            'Costo', 'Prezzo',
            'Peso', 'H', 'W', 'L',
            'Vol.',
            ], default_format=excel_format['header'])

        line_ids = connector_pool.search(cr, uid, [
            ('connector_id', '=', connector.id),
            ], context=context)

        for line in sorted(connector_pool.browse(
                cr, uid, line_ids, context=context),
                key=lambda p: (
                    p.product_id.default_code,
                    p.product_id.name),
                ):
            product = line.product_id
            default_code = product.default_code or ''

            # -----------------------------------------------------------------
            # Parameters:
            # -----------------------------------------------------------------
            # Stock:
            stock_qty, stock_comment = \
                connector_pool.get_existence_for_product(
                    cr, uid, line, context=context)

            multiplier = line.price_multi or 1
            if multiplier > 1:
                stock_qty = stock_qty // multiplier

            published = 'X' if line.published else ''
            if not published:
                color_format = excel_format['yellow']
            elif stock_qty <= 0:
                color_format = excel_format['red']
            else:
                color_format = excel_format['black']

            row += 1
            price = connector_pool.get_wp_price(line)
            excel_pool.write_xls_line(
                ws_name, row, [
                    published,
                    default_code,
                    product.name,
                    product.uom_id.name,
                    line.wp_color_id.name or '',
                    line.brand_id.name or '',
                    ', '.join(tuple(
                        [c.name for c in line.wordpress_categ_ids])),
                    stock_qty,
                    product.q_x_pack,
                    line.price_multi or '',
                    product.inventory_cost_no_move or product.standard_price,
                    price,
                    line.weight,

                    line.pack_h,
                    line.pack_l,
                    line.pack_p,
                    line.wp_volume,
                    ], default_format=color_format['text'])

        return excel_pool.return_attachment(cr, uid, 'web_product')
