import os
import sys
import erppeek
import ConfigParser
import pdb
from datetime import datetime


def log_message(log_file, message, mode='info', verbose=True):
    """ Log message
    """
    mode = mode.upper()
    log_file.write('[%s] %s. %s\n' % (
        mode,
        datetime.now(),
        message,
    ))
    if verbose:
        print(message.strip())


def get_product(line, odoo_db, cache):
    """ Extract product from line if present (primary company)
        Extract product from secondary company with sku
    """
    if 'product' not in cache:
        cache['product'] = {}

    product = line.product_id
    sku = line.sku
    if sku not in cache['product']:
        if product:
            cache['product'][sku] = product
        else:
            product_ids = odoo_db['gpb']['product'].search([
                ('default_code', '=', sku),
            ])
            if product_ids:
                 cache['product'][sku] = \
                     odoo_db['gpb']['product'].browse(product_ids)[0]

    return cache['product'].get(sku)


def get_web_product(line, odoo_db, cache):
    """ Extract web product from line
    """
    if 'web' not in cache:
        cache['web'] = {}

    connector_id = line.order_id.connector_id.id
    product = line.product_id
    sku = line.sku
    if sku not in cache['web']:
        if product:
            pool = odoo_db['fia']['web']
        else:
            pool = odoo_db['gpb']['web']

        web_ids = pool.search([
            ('connector_id', '=', connector_id),
            ('default_code', '=', sku),
        ])
        if web_ids:
             cache['web'][sku] = \
                 pool.browse(web_ids)[0]

    return cache['web'].get(sku)



def clean_date(value):
    """ Clean not ascii char
    """
    return (value or '').replace('-', '')


def clean_char(value, limit):
    """ Clean not ascii char
    """
    res = ''
    for c in (value or ''):
        if ord(c) < 127:
            res += c
        else:
            res += '#'
    return res[:limit]

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
odoo_db = {}
product_cache = {}

for root, folders, files in os.walk('..'):
    for cfg_file in files:
        if not cfg_file.startswith('openerp'):
            print('Not a config file: %s' % cfg_file)
            continue
        company = cfg_file.split('.')[1]
        f_log = open(os.path.join('./log', 'export.%s' % company), 'a')

        cfg_file = os.path.expanduser(os.path.join('../', cfg_file))
        config = ConfigParser.ConfigParser()
        config.read([cfg_file])
        dbname = config.get('dbaccess', 'dbname')
        user = config.get('dbaccess', 'user')
        pwd = config.get('dbaccess', 'pwd')
        server = config.get('dbaccess', 'server')
        port = config.get('dbaccess', 'port')
        connector_id = int(config.get('dbaccess', 'connector_id'))
        send_message = eval(config.get('dbaccess', 'send_message'))

        # ---------------------------------------------------------------------
        # Connect to ODOO:
        # ---------------------------------------------------------------------
        odoo = erppeek.Client(
            'http://%s:%s' % (server, port),
            db=dbname, user=user, password=pwd,
            )
        odoo_db[company] = {
            'order': odoo.model('wordpress.sale.order'),
            'product': odoo.model('product.product'),
            'web': odoo.model('product.product.web.server'),
        }
        log_message(f_log, 'Connected with ODOO, company %s\n' % company)
    break

# Use first company order only:
order_ids = odoo_db['fia']['order'].search()
orders = odoo_db['fia']['order'].browse(order_ids)
order_file = open(os.path.join('./data', 'wordpress.order.csv'), 'w')
log_message(f_log, 'Reading %s order from company %s\n' % (
    len(order_ids), company))

mask = '%-10s%-15s%8s%1s%-30s%-30s%-16s%-30s%-5s%-30s%-8s%-35s%-30s' \
       '%-18s%-45s%-20s%-30s%-5s' \
       '%-10.2f%-10.2f%-10.2f' \
       '%-20s%-10.2f%-1s%-10s%-10s\n'  # TODO \r

for order in orders:
    wp_record = eval(order.wp_record)
    for line in order.line_ids:
        # Data from product:
        product = get_product(line, odoo_db, product_cache)
        if product:
            cost = product.standard_price
        else:
            cost = 0.0

        # Data from web product:
        web_product = get_web_product(line, odoo_db, product_cache)
        if web_product:
            brand = web_product.brand_id.name or ''
            category = ''
            if web_product.wordpress_categ_ids:
                category = web_product.wordpress_categ_ids[0].name  # first!
        else:
            brand = ''
            category = ''

        data = (
            # Header:
            clean_char(order.name, 10),  # Order number
            clean_char(order.state, 15),  # State of order (Causale)
            clean_date(order.date_order),  # Date order (AAAAMMGG)
            'F',  # TODO A or F (Azienda or Persona Fisica) (1 Char)
            clean_char(order.partner_name, 30),  # Last name
            clean_char('', 30),  # First name (non importato, unito al cognome)
            clean_char('', 16),  # Fiscal code (non presente)
            clean_char(order.billing, 30),  # Address
            clean_char('', 5),  # ZIP
            clean_char('', 30),  # City
            clean_date(''),  # Birthday (AAAAMMGG) Non presente
            clean_char(order.partner_email, 35),  # Email
            clean_char(order.partner_phone, 30),  # Phone

            # Line:
            clean_char(line.sku, 18),  # SKU
            clean_char(line.name, 45),  # Product description
            clean_char(brand, 20),  # Brand
            clean_char(category, 30),  # Category (more than one!)
            clean_char('NR', 5),  # UOM  (sempre NR?)
            line.quantity,  # Q.  (10.2)
            cost,  # Cost  (10.2)
            line.price,  # List price  (10.2)

            # Footer
            clean_char(order.payment, 20),  # Payment
            (order.real_shipping_total or order.shipping_total),  # Trans. 10.2
            '',  # S = esente IVA (1 char)
            clean_char('', 10),  # Sconto ordine
            clean_char('', 10),  # Coupon sconto
        )
        order_file.write(mask % data)
        order_file.flush()

