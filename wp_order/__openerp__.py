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

{
    'name': 'Connector WP Manage order',
    'version': '0.1',
    'category': 'Connector',
    'description': '''        
        Create and manage order on master database
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'wp_connector',
        'connector_web_base',
        'order_destination',
        'force_as_corresponding',  # Unload material with corresponding pick

        # Fees generation:
        'sale_stock',
        'sale_delivery_partial',
        'force_as_corresponding',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/wp_group.xml',
        'security/ir.model.access.csv',
        # 'order_view.xml',
        'order_view_wordpress.xml',
        'carrier_view.xml',

        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
