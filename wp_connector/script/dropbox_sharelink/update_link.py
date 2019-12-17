# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import ConfigParser
import subprocess

# -----------------------------------------------------------------------------
# Read configuration parameter (2 Databases): 
# -----------------------------------------------------------------------------
for config_file in ('../openerp.cfg', '../gpb.openerp.cfg'):
    import pdb; pdb.set_trace()
    cfg_file = os.path.expanduser(config_file)

    config = ConfigParser.ConfigParser()
    config.read([cfg_file])
    dbname = config.get('dbaccess', 'dbname')
    user = config.get('dbaccess', 'user')
    pwd = config.get('dbaccess', 'pwd')
    server = config.get('dbaccess', 'server')
    port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

    album_id = int(config.get('odoo', 'album_id'))
    dropbox_path = config.get('odoo', 'dropbox_path')
    try:
        only_empty = eval(config.get('odoo', 'only_empty'))
    except:
        only_empty = False    

    print 'Accesso: Server %s Database %s Read folder: %s [album: %s]' % (
        server, dbname, dropbox_path, album_id)

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
    image_pool = odoo.model('product.image.file')
    domain = [('album_id', '=', album_id)]
    if only_empty:
        domain.append(('dropbox_link', '=', False))

    image_ids = image_pool.search(domain)
    
    if not image_ids:
        print 'No image exit in folder, exit'
        sys.exit()

    print 'Found %s album image [ID %s]' % (len(image_ids), album_id)
    image_db = {}
    for image in image_pool.browse(image_ids):
        image_db[image.filename] = image.id

    print 'Search image in path %s' % dropbox_path
    for root, folders, files in os.walk(dropbox_path):
        os.chdir(root)
        total = len(files)
        i = 0
        for f in files:
            i += 1
            if f not in image_db:
                print 'Not present on DB, not empty, not load album: %s' % f
                continue

            #fullname = os.path.join(root, f)    
            command = ['dropbox.py', 'sharelink', f]
            try:
                dropbox_link = subprocess.check_output(command)            
                image_pool.write([image_db[f]], {
                    'dropbox_link': 
                        dropbox_link.strip().rstrip('dl=0') + 'raw=1'
                    })
                print '[INFO] Dropbox sharelink file %s [%s of %s]' % (
                    f, i, total)
            except:
                print '[ERROR] Cannot sharelink file %s [%s of %s]' % (
                    f, i, total)
        break

