#!/usr/bin/python
# '*'coding: utf'8 '*'
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001'2015 Micronaet S.r.l. (<https://micronaet.com>)
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
import erppeek
import xlrd
import woocommerce
import ConfigParser
import slugify
import pickle

database = {}
for root, folders, files in os.path('./config'):
    for filename in files:
        if filename == 'wordpress.cfg':
            continue
        company = database.split('.')[0]       
        database[company] = os.path.join(root, filename)
    break    

pickle_file = './log/wp_data.p'
variant_db = pickle.load(open(pickle_file, 'rb'))

# -----------------------------------------------------------------------------
# WP web read: Spaziogiardino
# -----------------------------------------------------------------------------
# Worpress parameters:
config = ConfigParser.ConfigParser()
cfg_file = os.path.expanduser('../wordpress.cfg')
config.read([cfg_file])
wordpress_url = config.get('wordpress', 'url')
consumer_key = config.get('wordpress', 'key')
consumer_secret = config.get('wordpress', 'secret')

wcapi = woocommerce.API(
    url=wordpress_url,
    consumer_key=consumer_key,
    consumer_secret=consumer_secret,
    wp_api=True,
    version='wc/v3',
    query_string_auth=True,
    timeout=600,
    )

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
for company in database:
    cfg_file = database[company]
    
    # From config file:
    config = ConfigParser.ConfigParser()
    config.read([cfg_file])
    dbname = config.get('dbaccess', 'dbname')
    user = config.get('dbaccess', 'user')
    pwd = config.get('dbaccess', 'pwd')
    server = config.get('dbaccess', 'server')
    port = config.get('dbaccess', 'port')  # verify if it's necessary: getint
    connector_id = config.get('dbaccess', 'connector_id')


    # -------------------------------------------------------------------------
    # Connect to ODOO:
    # -------------------------------------------------------------------------
    odoo = erppeek.Client(
        'http://%s:%s' % (
            server, port), 
        db=dbname,
        user=user,
        password=pwd,
        )
    
    for lang in lang_db:
        wp_lang = lang[:2]
        odoo.context = {'lang': lang}
        web_product_pool = odoo.model('product.product.web.server')
    
        web_product_ids = web_product_pool.search([
            ('wp_parent_template', '=', True),
            ])
                    
        for master in web_product_pool.browse(web_product_ids):
            for variation in master.variant_ids:
                product = variation.product_id                
                default_code = product.default_code #.replace(' ', '&nbsp;')
                if variation.published:
                    status = 'publish'  
                else:
                    status = 'private'
                    print 'Unpublished: %s' % default_code
                
                if default_code not in variant_db[wp_lang]:
                    print 'Master code not found: %s' % default_code
                    continue
    
                wp_data = variant_db[wp_lang][default_code]
                product_id = wp_data['product_id']
                variation_id = wp_data['variation_id']
                
                # XXX Problem with this:
                stock_quantity, stock_comment = \
                    web_product_pool.get_existence_for_product(product.id)

                # -------------------------------------------------------------
                # Stock data:
                # -------------------------------------------------------------
                data = {
                    'lang': wp_lang,
                    'stock_quantity': stock_quantity,
                    'manage_stock': True,
                    # Visibility:
                    'status': status,
                    
                    #'stock_status': 'instock', 
                    # instock (def.), outofstock, onbackorder
                    }                

                # -------------------------------------------------------------
                # Variation update:
                # -------------------------------------------------------------
                call = 'products/%s/variations/%s' % (
                    product_id, variation_id)
                reply = wcapi.put(call, data)
                if reply.status_code >= 300:
                    print 'Error publish stock status: %s, [%s: %s]\n\n%s' % (
                        default_code, call, data, reply.text)                    
                else:
                    print 'Update %s with stock status: %s [%s: %s]\n%s\n' % (
                        default_code, stock_quantity,  call, data, reply.text,
                        )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: