# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
from openerp import netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class ProductTemplateAccounting(orm.Model):
    ''' Accounting external fields
    '''
    
    _inherit = 'product.template'
    
    _columns = {
        'minimum_qty': fields.float('Min. quantity', digits=(10, 2), 
            help="Minimum value for stock"),
        'maximum_qty': fields.float('Max. quantity', digits=(10, 2), 
            help="Maximum value for stock"),
        'accounting_qty': fields.float('Accounting quantity', digits=(10, 2), 
            help="Accounting existence updated today"),
    }

class SaleOrderLine(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''
    
    _inherit = 'sale.order.line'

    # -------------
    # Button event:
    # -------------
    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {
            'mrp_id': False, }, context=context)

    def close_production(self, cr, uid, ids, context=None):
        ''' Close production
        '''
        # TODO (interact with accounting)
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        if line_proxy.product_uom_maked_qty: # partial
            pass # TODO close (partial)
            #self.write(cr, uid, ids, {
            #    'is_produced': True,   
            #    }, context=context)
        else: # TODO manage well (now not correct)
            self.write(cr, uid, ids, {
                'product_uom_maked_qty': 
                    line_proxy.product_uom_qty,
                'is_produced': True,
                }, context=context)                
        return True
            
    _columns = {
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        'product_uom_maked_qty': fields.float(
            'Quantity maked', digits=(16, 2), ),
            
        # TODO remove with state?
        'is_produced': fields.boolean('Is produced', required=False),    
        }

class SaleOrderLinePrevisional(orm.Model):
    ''' Previsional production
    '''
    
    _name = 'sale.order.line.previsional'
    
    def set_updated(self, cr, uid, ids, context=None):
        ''' Check the updated boolean (for speed up)
        '''
        self.write(cr, uid, ids, {'updated': True}, context=context)
        return True
        
    _columns = {
        'partner_id':fields.many2one(
            'res.partner', 'Customer', required=False),
        'product_id': fields.many2one(
            'product.product', 'Product', required=False),
        'deadline': fields.date('Deadline'), 
        'note': fields.text('Note'),        
        'product_uom_qty': fields.float('Quantity', digits=(16, 2), 
            required=True),

        'updated': fields.boolean('Updated', 
            help='Manually updated on accounting program'),
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade', ),
        }        

class MrpProduction(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''
    
    _inherit = 'mrp.production'
    
    # TODO 
    #def get_extra_production(self, cr, uid, ids, context=None):
    #    ''' Serch production with that line
    #    '''
    #    res = {}
    #    vote_ids = self.pool.get('sale.order.line').browse(
    #        cr, uid, ids, context=context)
    #    for v in vote_ids:
    #    res[v.idea_id.id] = True # Store the idea identifiers in a set
    #    return res.keys()

    # -------------
    # Button event:
    # -------------
    
    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {
            'used_by_mrp_id': False, }, context=context)

    def _get_totals(self, cr, uid, ids, fields=None, args=None, context=None):
        ''' Calculate all totals 
            oc_qty = sum (qty for all line)
            extra_qty = total production - oc_qty
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {}
            res[order.id]['oc_qty'] = 0.0
            res[order.id]['previsional_qty'] = 0.0
            res[order.id]['use_extra_qty'] = 0.0

            for line in order.order_line_ids:
                res[order.id]['oc_qty'] += line.product_uom_qty # TODO UM?

            for line in order.previsional_line_ids:
                res[order.id]['previsional_qty'] += line.product_uom_qty 

            for line in order.use_mrp_ids: # TO correct (for recursion)
                res[order.id]['use_extra_qty'] += self.browse(cr, uid, line.id).extra_qty

                #res[order.id]['use_extra_qty'] += line.extra_qty 

            res[order.id]['extra_qty'] = (        # Extra =
                order.product_qty +               # Production
                res[order.id]['use_extra_qty'] -  # + extra qty used
                res[order.id]['oc_qty'] -         # - Ordered
                res[order.id]['previsional_qty']) # - Previsional
            res[order.id]['error_qty'] = res[order.id]['extra_qty'] < 0.0
            res[order.id]['has_extra_qty'] = res[order.id]['extra_qty'] > 0.0
        return res    
    
    _columns = {
        'oc_qty': fields.function(
            _get_totals, method=True, type='float', 
            string='OC qty', store=False, readonly=True, multi=True),
        'previsional_qty': fields.function(
            _get_totals, method=True, type='float', 
            string='Previsional qty', store=False, readonly=True, multi=True),
        'use_extra_qty': fields.function(
            _get_totals, method=True, type='float', 
            string='Use extra qty', store=False, readonly=True, multi=True),
        'extra_qty': fields.function(
            _get_totals, method=True, type='float', 
            string='Extra qty', store=False, readonly=True, multi=True),
        'has_extra_qty': fields.function(
            _get_totals, method=True, type='boolean', string='Has extra', 
            store=True,
            #{'sale.order.line':(_get_extra_production,['product_uom_qty'],10)}, 
            readonly=True, multi=True),
        'error_qty': fields.function(
            _get_totals, method=True, type='boolean', 
            string='Total error', store=False, readonly=True, multi=True),
        
        'used_by_mrp_id': fields.many2one('mrp.production', 'Used by'),
        
        'use_mrp_ids': fields.one2many(
            'mrp.production', 'used_by_mrp_id', 'Use mrp'),
        'order_line_ids': fields.one2many(
            'sale.order.line', 'mrp_id', 'Order line'),
        'previsional_line_ids': fields.one2many(
            'sale.order.line.previsional', 'mrp_id', 'Previsional order'),
        'updated':fields.boolean('Label', required=False),    
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
