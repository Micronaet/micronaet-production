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

import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
#                             Read Parameters:
# -----------------------------------------------------------------------------
cfg_file = "family_odoo.cfg" # same directory
config = ConfigParser.ConfigParser()
config.read(cfg_file)

# General parameters:
server = config.get('odoo', 'server')
port = eval(config.get('odoo', 'port'))
database = config.get('odoo', 'database')
user = config.get('odoo', 'user')
password = config.get('odoo', 'password')

file_in = config.get('csv', 'name')
separator = eval(config.get('csv', 'separator'))
header =  eval(config.get('csv', 'header'))

# -----------------------------------------------------------------------------
#                               Start procedure:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port), 
    db=database, 
    user=user, 
    password=password)

family_pool = odoo.model('product.template')

# ----------------------------------
# Read and store all family present:
# ----------------------------------
family_ids = family_pool.search([('is_family', '=', True)])
family_convert = {}
if family_ids:
    for item in family_pool.browse(family_ids):
        family_convert[item.name] = [item.id, []] # create record [ID, [code]]
    
# -------------------------
# Load elements from files:
# -------------------------
i = -header
max_col = False
for row in open(file_in, 'rb'):
    line = row.split(separator)
    i += 1
    if i <= 0: # jump header
        continue
    if not max_col:
        max_col = len(line)    
    default_code = line[0]
    family = line[1]
    category = line[2]
    jump = line[3].strip() # for \n
    
    if jump == "*" or not family:
        print "Jump line %s" % (line, )
        continue

    if family not in family_convert:
        # Create dict record 
        family_convert[family] = [
            family_pool.create({
                'name': family,
                'is_family': True,
                }),
            []]   
    family_convert[family][1].append(default_code)

# ----------------------
# Update family to odoo:
# ----------------------
for key in family_convert:
    item_id, family_list = family_convert[key]
    family_pool.write(item_id, {
        'family_list': "|".join(family_list)
        })
    family_pool.update_family(item_id)    
# TODO launch procedure for update all products        
