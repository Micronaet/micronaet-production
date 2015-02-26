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
            
    _columns = {
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        }

class SaleOrderLinePrevisional(orm.Model):
    ''' Previsional production
    '''
    
    _name = 'sale.order.line.previsional'
            
    _columns = {
        'partner_id':fields.many2one(
            'res.partner', 'Customer', required=False),
        'deadline': fields.datetime('Deadline'), 
        'note': fields.text('Note'),        
        'product_uom_qty': fields.float('Quantity', digits=(16, 2)),
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


    def _get_totals(self, cr, uid, ids, fields=None, args=None, context=None):
        ''' Calculate all totals 
            oc_qty = sum (qty for all line)
            extra_qty = total production - oc_qty
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {}
            res[order.id]['oc_qty'] = 0.0
            for line in order.order_line_ids:
                res[order.id]['oc_qty'] += line.product_uom_qty # TODO UM?
            res[order.id][
                'extra_qty'] = order.product_qty - res[order.id]['oc_qty']
            res[order.id]['error_qty'] = res[order.id]['extra_qty'] < 0.0
            res[order.id]['has_extra_qty'] = res[order.id]['extra_qty'] > 0.0
        return res    
    
    _columns = {
        'oc_qty': fields.function(
            _get_totals, method=True, type='float', 
            string='OC qty', store=False, readonly=True, multi=True),
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
        
        # TODO there's extra bool?
        'order_line_ids': fields.one2many(
            'sale.order.line', 'mrp_id', 'Order line'),
        'previsional_line_ids': fields.one2many(
            'sale.order.line.previsional', 'mrp_id', 'Previsional order'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
