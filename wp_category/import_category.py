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

class ProductPublicCategory(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.public.category'
    
    _columns = {
        'wp_id': fields.integer('Worpress ID'),
        }

class ProductPublicCategory(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'connector.server'

    def publish_category_now(self, cr, uid, ids, context=None):
        ''' Publish now button
            Used also for more than one elements (not only button click)
            Note all product must be published on the same web server!            
            '''
        if context is None:    
            context = {}

        server_id = ids[0]
        _logger.warning('Publish category all on wordpress:')
        
        # ---------------------------------------------------------------------
        #                         WORDPRESS Publish:
        # ---------------------------------------------------------------------
        server_pool = self.pool.get('connector.server')
        category_pool = self.pool.get('product.public.category')
        
        # ---------------------------------------------------------------------
        #                        CREATE CATEGORY OPERATION:
        # ---------------------------------------------------------------------
        data = {'create': [], 'update': []}

        # Read WP Category present:
        wcapi = server_pool.get_wp_connector(
            cr, uid, server_id, context=context)

        wp_db = {}
        wp_name = {} # TODO manage!
        import pdb; pdb.set_trace()
        for record in wcapi.get('products/categories').json():
            wp_db[record['id']] = record['name']
            wp_name[(record['parent'] or False, record['name'])] = record['id']
            
        # ---------------------------------------------------------------------
        # Read ODOO PARENT category:
        # ---------------------------------------------------------------------
        odoo_parent = {}
        category_ids = category_pool.search(cr, uid, [
            ('parent_id', '=', False),
            ('connector_id', '=', server_id),
            ], context=context)

        for category in category_pool.browse(
                cr, uid, category_ids, context=context):    
            wp_id = category.wp_id            
            odoo_id = category.id
            name = category.name
            
            record_data = {
                'name': name,
                'parent': 0,
                'menu_order': category.sequence,
                'display': 'default',
                }

            # Check if present :            
            key = (False, name)
            
            if wp_id in wp_db or key in wp_name: # Update (ID or Name present)
                record_data['id'] = wp_id
                data['update'].append(record_data)
                try:
                    del(wp_db[wp_id])
                except:
                    pass # yet deleted (from Front end?)
    
            else: # Create:
                data['create'].append(record_data)
                odoo_parent[name] = odoo_id

        res = wcapi.post('products/categories/batch', data).json()
        for record in res.get('create', ()):
            wp_id = record['id']
            if not wp_id:
                # TODO manage error:
                _logger.error('Not Updated wp_id for %s' % wp_id)
                continue

            name = record['name']
            odoo_id = odoo_parent.get(name, False)
            if not odoo_id:
                _logger.error('Not Updated wp_id for %s' % name)
                continue

            category_pool.write(cr, uid, odoo_id, {
                'wp_id': record['id'],
                }, context=context)
            odoo_parent[name] = odoo_id
            _logger.info('Updated wp_id for %s' % name)

        # ---------------------------------------------------------------------
        # Read ODOO category child:
        # ---------------------------------------------------------------------
        odoo_child = {}
        data = {'create': [], 'update': []}
        category_ids = category_pool.search(cr, uid, [
            ('parent_id', '!=', False),
            ('connector_id', '=', server_id),
            ], context=context)

        for category in category_pool.browse(
                cr, uid, category_ids, context=context):    
            wp_id = category.wp_id            
            odoo_id = category.id
            name = category.name
            parent_wp_id = category.parent_id.wp_id
            
            record_data = {
                'name': name,
                'parent': parent_wp_id,
                'menu_order': category.sequence,
                'display': 'default',
                }

            # Check if present :
            key = (parent_wp_id, name)

            if wp_id in wp_db or key in wp_name: # Update
                record_data['id'] = wp_id
                data['update'].append(record_data)
                try:
                    del(wp_db[wp_id])
                except:
                    pass # yet deleted (from Front end?)
    
            else: # Create:
                data['create'].append(record_data)
                odoo_child[name] = odoo_id

        # ---------------------------------------------------------------------
        #                     UPDATE / DELETE CATEGORY OPERATION:
        # ---------------------------------------------------------------------
        data['delete'] = wp_db.keys()
        try:
            res = wcapi.post('products/categories/batch', data).json()
        except:
            raise osv.except_osv(
                _('Error'), 
                _('Wordpress server not answer, timeout!'),
                )
                
        
        # Update category with WP ID:
        for record in res.get('create', ()):
            wp_id = record['id']
            if not wp_id:
                # TODO manage error:
                _logger.error('Not Updated wp_id for %s' % wp_id)
                continue
                
            name = record['name']
            odoo_id = odoo_child.get(name, False)
            if not odoo_id:
                _logger.error('Not Updated wp_id for %s' % name)
                continue
                
            category_pool.write(cr, uid, odoo_id, {
                'wp_id': record['id'],
                }, context=context)
            _logger.info('Updated wp_id for %s' % name)
        return True
        # TODO      
        # Check updated
        # Check deleted
        # Update product first category?
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
