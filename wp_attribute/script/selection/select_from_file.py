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
import ConfigParser

print 'Cambiare connector ID (and DB access)!'
import pdb; pdb.set_trace()
connector_id = 5 # REAL connector.server for wordpress # XXX change!
#connector_id = 9 # LOCAL connector.server for wordpress # XXX change!

file_in = './product.xlsx'
row_start = 1

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.cfg')
#cfg_file = os.path.expanduser('../local.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port), 
    db=dbname,
    user=user,
    password=pwd,
    )
    
# Pool used:
product_pool = odoo.model('product.product')
web_pool = odoo.model('product.product.web.server')

# Excel input:
try:
    WB = xlrd.open_workbook(file_in)
except:
    print '[ERROR] Cannot read XLS file: %s' % file_in
    sys.exit()
WS = WB.sheet_by_index(0)

# -----------------------------------------------------------------------------
# Delete all
# -----------------------------------------------------------------------------
web_ids = web_pool.search([
    ('connector_id', '=', connector_id),
    ])
if web_ids:
    print 'Set unpublish all product for this connector, # %s' % len(web_ids)
    web_pool.write(web_ids, {
        'published': False,
        })
        
# -----------------------------------------------------------------------------
# Create from files:
# -----------------------------------------------------------------------------
i = 0
for row in range(row_start, WS.nrows):
    i += 1
    # Mapping:
    default_code = WS.cell(row, 0).value
    selection = (WS.cell(row, 1).value or '').upper()
    short_text = WS.cell(row, 3).value
    long_text = WS.cell(row, 4).value

    if not default_code or selection not in ('X', 'O'):
        print '%s. Selezione non corretta: %s [%s]' % (
            i, default_code, selection)
        continue
        
    product_ids = product_pool.search([
        ('default_code', '=', default_code),
        ])
    if product_ids:
        product_id = product_ids[0]

    # -------------------------------------------------------------------------
    #                         Product:
    # -------------------------------------------------------------------------
    product_pool.write(product_ids, {
        'emotional_short_description': short_text,
        'emotional_description': long_text,
        })

    # Update package:
    product_pool.auto_package_assign(product_ids)
    
    # -------------------------------------------------------------------------
    #                         Web selection:
    # -------------------------------------------------------------------------
    data = {
        'connector_id': connector_id,
        'published': True,
        'product_id': product_id,             
        'wp_type': 'variable',
        }
    
    if selection == 'X': 
        # Create as parant    
        data['wp_parent_template'] = True

    web_ids = web_pool.search([
        ('connector_id', '=', connector_id),
        ('product_id', '=', product_id),
        ])

    if web_ids:
        print '%s. Aggiornamento: %s' % (i, default_code)
        web_pool.write(web_ids, data)
    else:    
        print '%s. Creazione: %s' % (i, default_code)
        web_pool.create(data)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
