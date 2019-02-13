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
        assert len(ids) == 1, 'Works only with one record a time'
        
        cost_pool = self.pool.get('mrp.paint.cost')
        
        # ---------------------------------------------------------------------
        # Load list of product:
        # ---------------------------------------------------------------------
        paint_cost = {}
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        for product in current_proxy.product_ids:
            color_id = product.color_id.id
            if color_id in paint_cost:
                paint_cost[color_id] += product.product_qty
            else: # not necessary:
                paint_cost[color_id] = product.product_qty

        # ---------------------------------------------------------------------
        # Check current list for create / delete operation:
        # ---------------------------------------------------------------------
        current_cost = {}
        for cost in current_proxy.cost_ids:
            current_cost[cost.color_id.id] = cost.id
            
        # ---------------------------------------------------------------------
        # Add extra data not present:
        # ---------------------------------------------------------------------
        for color_id in paint_cost:
            if color_id in current_cost:
                cost_pool.write(cr, uid, current_cost[color_id], {
                    'product_qty': paint_cost[color_id],
                    }, context=context)
            else:
                cost_pool.create(cr, uid, {
                    'paint_id': current_proxy.id,
                    'color_id': color_id,
                    'product_qty': paint_cost[color_id],
                    }, context=context)
                    
        # ---------------------------------------------------------------------
        # Delete not present:
        # ---------------------------------------------------------------------
        for color_id in current_cost:
            if color_id not in paint_cost:
                cost_pool.unlink(
                    cr, uid, current_cost[color_id], context=context)
        return True

    def reload_total_list(self, cr, uid, ids, context=None):
        ''' Reload total list from product list
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        total_pool = self.pool.get('mrp.paint.total')
        
        # ---------------------------------------------------------------------
        # Load list of product:
        # ---------------------------------------------------------------------
        paint_total = {}
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        for product in current_proxy.product_ids:
            product_code = product.product_code
            if product_code in paint_total:
                paint_total[product_code] += product.product_qty
            else: # not necessary:
                paint_total[product_code] = product.product_qty

        # ---------------------------------------------------------------------
        # Check current list for create / delete operation:
        # ---------------------------------------------------------------------
        total_cost = {}
        for total in current_proxy.total_ids:
            total_cost[total.product_code] = (total.id, total.cpv_cost)
            
        # ---------------------------------------------------------------------
        # Add extra data not present:
        # ---------------------------------------------------------------------
        for product_code in paint_total:
            if product_code in total_cost:
                total_id, cpv_cost = total_cost[product_code]
                total_pool.write(cr, uid, total_id, {
                    'product_total': paint_total[product_code],
                    'cost_total': paint_total[product_code] * cpv_cost,
                    }, context=context)
            else:
                total_pool.create(cr, uid, {
                    'paint_id': current_proxy.id,
                    'product_code': product_code,
                    'product_total': paint_total[product_code],
                    # cost_total = 0
                    }, context=context)
                    
        # ---------------------------------------------------------------------
        # Delete not present:
        # ---------------------------------------------------------------------
        for product_code in total_cost:
            if product_code not in paint_total:
                total_pool.unlink(
                    cr, uid, total_cost[product_code][0], context=context)
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

    def _get_total_paint(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for paint in self.browse(cr, uid, ids, context=context):
            # Total of product
            partial = 0.0
            for total in paint.total_ids:
                partial += total.cost_total
                
            res[paint.id] = partial     
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
        
        'total_real': fields.float('Total real', digits=(16, 2)),
        'total_calculated': fields.function(
            _get_total_paint, method=True, 
            type='float', string='Total calculated', 
            store=False), 
                        
        }

class MrpPaintProductColor(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.product.color'
    _description = 'Paint product color'
    _rec_name = 'name'
    _order = 'name'
    
    _columns = {
        'code': fields.char('Code', size=10),
        'name': fields.char('Color', size=64, required=True),
        }

class MrpPaintProduct(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.product'
    _description = 'Paint product'
    _rec_name = 'product_code'
    _order = 'product_code'
    
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint', ondelete='cascade'),
        'product_code': fields.char('Product code', size=10, required=True),
        'color_id': fields.many2one('mrp.paint.product.color', 'Color', 
            required=True),
        'product_qty': fields.integer('Qty', required=True),
        }
    
class MrpPaintCost(orm.Model):
    """ Model name: Mrp paint product
    """
    
    _name = 'mrp.paint.cost'
    _description = 'Paint cost'
    _rec_name = 'color_id'
    _order = 'color_id'
    
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint', ondelete='cascade'),
        
        # Summary:
        'color_id': fields.many2one('mrp.paint.product.color', 'Color', 
            required=True),
        'product_qty': fields.integer('Qty', required=True),
        
        # Work:
        'work_hour': fields.float('Work hour'),

        # Dust:
        'dust_id': fields.many2one('product.product', 'Dust'),
        'dust_weight': fields.float('Dust weight'),
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

    # -------------------------------------------------------------------------    
    # Onchange:
    # -------------------------------------------------------------------------    
    def onchange_cpv_cost(self, cr, uid, ids, product_total, cpv_cost, 
            context=None):
        ''' Update total
        '''    
        return {'value': {
            'cost_total': product_total * cpv_cost,
            }}
        
    _columns = {
        'paint_id': fields.many2one('mrp.paint', 'Paint', ondelete='cascade'),

        'product_code': fields.char('Product code', size=10, required=True),
        'product_total': fields.integer('Product total'),
        'cpv_cost': fields.float('CPV', digits=(16, 2)),
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
