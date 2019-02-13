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

class MrpPaint(orm.Model):
    """ Model name: MrpPaint
    """
    
    _name = 'mrp.paint'
    _description = 'Paint form'
    _rec_name = 'date'
    _order = 'date'
    
    def reload_cost_list(self, cr, uid, ids, context=None):
        ''' Reload cost list from product list
        '''
        return True

    def reload_total_list(self, cr, uid, ids, context=None):
        ''' Reload total list from product list
        '''
        return True

    # -------------------------------------------------------------------------       
    # Fields function:
    # -------------------------------------------------------------------------       
    def _get_gas_total(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for paint in self.browse(cr, uid, ids, context=context):
            gap = paint.gas_stop - paint.gas_start
            res[paint.id] = {
                'gas_total': gap,
                'gas_total_cost': gap * paint.gas_unit,
                }                
        return res
        
    # -------------------------------------------------------------------------       
    # Table:
    # -------------------------------------------------------------------------       
    _columns = {
        'date': fields.date('Date', required=True),
        'gas_start': fields.integer('Gas start'),        
        'gas_stop': fields.integer('Gas stop'),        
        'gas_total': fields.function(_get_gas_total, method=True, 
            type='integer', string=u'Gas total M³', multi=True), 
        'gas_total_cost': fields.function(_get_gas_total, method=True, 
            type='float', string='Gas total cost', multi=True), 

        'gas_id': fields.many2one('product.product', 'Gas product', 
            help='Product used to manage unit cost for Gas'),
        'work_id': fields.many2one('product.product', 'Word product', 
            help='Product used to manage unit cost for work'),

        # Saved in daily form:
        'gas_unit': fields.related(
            'gas_id', 'standard_price', 
            type='float', string='Gas unit', store=True),
        'work_unit': fields.related(
            'work_id', 'standard_price', 
            type='float', string='Work unit', store=True),
        
        'note': fields.text('Note'),
        }

class MrpPaintProduct(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.product'
    _description = 'Paint product'
    _rec_name = 'product_code'
    _order = 'product_code'
    
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint'),
        'product_code': fields.char('Product code', size=10, required=True),
        'color_code': fields.char('Color code', size=10, required=True),
        'product_qty': fields.integer('Qty', required=True),
        'cpv_cost': fields.float('CPV', digits=(16, 2)),
        }
    
class MrpPaintCost(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.cost'
    _description = 'Paint cost'
    _rec_name = 'product_code'
    _order = 'product_code'
    
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint'),
        
        # Summary:
        'product_code': fields.char('Product code', size=10, required=True),
        'color_code': fields.char('Color code', size=10, required=True),
        
        # Work:
        'work_hour': fields.float('Work hour', required=True),

        # Dust:
        'dust_id': fields.many2one('product.product', 'Dust', required=True),
        'dust_weight': fields.float('Dust weight', required=True),
        'dust_unit': fields.related(
            'dust_id', 'standard_price', 
            type='float', string='Dust unit', store=True),
        }

class MrpPaintCost(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.total'
    _description = 'Paint total'
    _rec_name = 'product_code'
    _order = 'product_code'
    
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint'),

        'product_code': fields.char('Product code', size=10, required=True),
        'product_total': fields.integer('Product total'),
        'cost_total': fields.integer('Cost Total'),
        }
    
class MrpPaint(orm.Model):
    """ Model name: MrpPaint update relationship
    """
    
    _inherit = 'mrp.paint'
    
    _columns = {
        'product_ids': fields.one2many(
            'mrp.paint.product', 'paint_id', 'Product'),
        'cost_ids': fields.one2many(
            'mrp.paint.cost', 'paint_id', 'Cost'),
        'total_ids': fields.one2many(
            'mrp.paint.total', 'paint_id', 'Total'),
        }
    
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
