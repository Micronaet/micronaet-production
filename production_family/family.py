# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
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

class ProductTemplateFamily(orm.Model):
    ''' Add extra information to default product
    '''    
    _inherit = 'product.template'
    
    # -------------
    # button event:
    # -------------
    def update_family(self, cr, uid, ids, context=None):
        ''' Force single family update
        '''
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        product_pool = self.pool.get('product.product')
        
        # Search all elements of code:
        for code in product_proxy.family_list.split("|"):
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=ilike', code + "%")], context=context)
            product_pool.write(cr, uid, product_ids, {
                'family_id': product_proxy.id,
                'internal_manufacture': product_proxy.force_manufacture,
                }, context=context)    
        return True

    _columns = {
        'is_family': fields.boolean('Is family'),
        'family_id': fields.many2one('product.template', 'Family', 
            help='Parent family product belongs',
            domain=[('is_family', '=', True)]),            
        'family_list': fields.text(
            'Family list',
            help='Code list (divided by |), ex.: 001|002 for 001* and 002*'),
        'force_manufacture': fields.boolean('Force manufacture', 
            help='If yes update all product also for manufacture else not'),
        'internal_manufacture': fields.boolean('Internal manufacture', 
            help='If true this product order line will go in production'),
        }
        
    _defaults = {
        'is_family': lambda *x: False,
        'force_manufacture': lambda *x: True,
        'internal_manufacture': lambda *x: True,
        }

class MrpBomFamily(orm.Model):
    ''' Add extra information to set up BOM for family
    '''    
    _inherit = 'mrp.bom'
    
    _columns = {
        'family': fields.boolean('Is family BOM'),
        }

class MrpProductionFamily(orm.Model):
    ''' Add extra information to set up production for family
    '''    
    _inherit = 'mrp.production'
    
    _columns = {
        'family': fields.boolean('Is family BOM'),
        }

class MrpLavorationFamily(orm.Model):
    ''' Add extra information to set up lavoration for family
    '''    
    _inherit = 'mrp.production.workcenter.line'
    
    _columns = {
        'family': fields.related('production_id', 'family', type='boolean', 
            string='Family', store=False),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
