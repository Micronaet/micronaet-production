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

class MrpWorkcenter(orm.Model):
    ''' Extra fields for workcenter
    '''
    _inherit = 'mrp.workcenter'
    
    _columns = {
        'work_hour': fields.float('Work hour', digits=(10, 2), 
            help='Normal work hour a day'),
        'extra_work_hour': fields.float('Extra work hour', digits=(10, 2), 
            help='Number of hour max after normal work (extraordinary time)'),
        }
    
    _defaults = {
        'work_hour': lambda *x: 8.0,
        'extra_work_hour': lambda *x: 1.0,        
    }        

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

class SaleOrder(orm.Model):
    ''' Add control fields for sale order
    '''    
    _inherit = 'sale.order'
    
    # -------------
    # Button event:
    # -------------
    def nothing(self, cr, uids, ids, context=None):
        ''' Button event does nothing
        '''
        return True
        
    # ---------------
    # Function field:
    # ---------------
    def _get_produced_state(self, cr, uid, ids, fields, args, context=None):
        ''' Check all line if are sync
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):            
            is_line_produced = [
                item.product_uom_qty == item.product_uom_maked_sync_qty 
                    for item in order.order_line]
            res[order.id] = all(is_line_produced)
        return res
        
    def _check_line_produced(self, cr, uid, ids, context=None):
        ''' Check when family_id will be modified in product
        '''
        #select distinct order_id from sale_order_line where id in %s
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id.id not in res:
                res.append(line.order_id.id)
        return res

    _columns = {
        'all_produced': fields.function(
            _get_produced_state, method=True, type='boolean', 
            string='All produced', store={
                'sale.order.line': (
                    _check_line_produced, [
                        'mrp_id', 'product_uom_maked_sync_qty'], 10),
                    })}

class SaleOrderLine(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''    
    _inherit = 'sale.order.line'
    
    # Force new order for production
    _order = 'mrp_sequence,order_id,sequence'

    # -------------
    # Button event:
    # -------------
    def open_production_form(self, cr, uids, ids, context=None):
        ''' Button that open form of MRP linked
        '''
        return True

    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        # Only in draft mode!
        sol_proxy = self.browse(cr, uid, ids, context=context)[0]
        if sol_proxy.order_id.forecasted_production_id:
            # Forecast order delete line:   
            self.unlink(cr, uid, ids, context=context)            
        else:    
            # Normal order unlink from production:
            # TODO remove line without hide gives error (for focus problem)
            self.write(cr, uid, ids, {
                'mrp_id': False, 
                'mrp_sequence': False, # reset order
                }, context=context)

        # Recalculate totals:
        mrp_id = context.get('production_order_id', False)
        if not mrp_id: # odd case
            return False

        # Reload total from sale order line:        
        return self.pool.get('mrp.production').recompute_total_from_sol(
            cr, uid, [mrp_id], context=context)

    def close_production(self, cr, uid, ids, context=None):
        ''' Close production
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        return self.write(cr, uid, ids, {
            'product_uom_maked_qty': 
                line_proxy.product_uom_qty,
            'sync_state': 'closed',
            }, context=context)                

    def undo_close_production(self, cr, uid, ids, context=None):
        ''' Undo close production (before sync)
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # TODO manage if there's partial!!
        return self.write(cr, uid, ids, {
            'product_uom_maked_qty': 0.0,
            'product_uom_maked_sync_qty': 0.0,
            'sync_state': 'draft',
            }, context=context)                
           
    _columns = {
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        'product_uom_maked_qty': fields.float(
            'Maked (temp.)', digits=(16, 2), 
            help='Partial position till not sync in accounting'),
        'product_uom_maked_sync_qty': fields.float(
            'Maked (acc.)', digits=(16, 2), 
            help='This quantity is the sync quantity maked in accounting'),
        'production_note': fields.char('Note', size=100),    

        #'default_code': fields.related('product_id','default_code', 
        #    type='char', string='Code'),
        # TODO remove with state?
        #'is_produced': fields.boolean('Is produced', required=False),
        'mrp_sequence': fields.integer('MRP order'),
        
        'sync_state': fields.selection([
            ('draft', 'Draft'), # Not produced
            ('partial', 'Partial'),# Partial produced
            ('partial_sync', 'Partial sync'), # Partial produced acc. sync
            ('closed', 'Closed'), # Poduced acc. sync
            ('sync', 'Sync'), ],'Sync state', select=True),
        }
        
    _defaults = {
        'sync_state': lambda *x: 'draft',
        }

class SaleOrderLinePrevisional(orm.Model):
    ''' Previsional production
    '''
    
    _name = 'sale.order.line.previsional'
    _description = 'Previsional line'
    _rec_name = 'partner_id'
    
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
        'product_tmpl_id': fields.many2one(
            'product.template', 'Product', required=False),
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
    
    # ------------------
    # Override function:
    # ------------------
    def unlink(self, cr, uid, ids, context=None):
        """ Delete all record(s) from table heaving record id in ids
            return True on success, False otherwise 
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids to be removed from table
            @param context: context arguments, like lang, time zone
            
            @return: True on success, False otherwise
        """
        # Test if line has accounting element sync:
        order_locked = ''
        for production in self.browse(cr, uid, ids, context=context):
            test = [line.product_uom_maked_sync_qty 
                for line in production.order_line_ids]
            if any(test):
                order_locked += _('Order %s\n') % production.name

        if order_locked:
            raise osv.except_osv(
                _('Error'), 
                _('''Before delete production order undo account operation\n
                    %s
                    ''' % order_locked))

        # Delete if no error:            
        res = super(MrpProduction, self).unlink(
            cr, uid, ids, context=context)
        return res
    # -------------
    # Button event:
    # -------------
    def close_all_production(self, cr, uid, ids, context=None):
        ''' Close all production
        '''
        line_proxy = self.browse(cr, uid, ids, context=context).order_line_ids
        
        # Loop for close all (use original button event):
        for line in line_proxy:
           if line.sync_state == 'draft':
               self.pool.get(
                   'sale.order.line').close_production(
                       cr, uid, [line.id], context=context)
        return True

    def accounting_sync(self, cr, uid, ids, context=None):
        ''' Function to override depend on sync method used
        '''
        return True
    
    def force_production_sequence(self, cr, uid, ids, context=None):
        ''' Set current order depend on default code 
            Note: currently is forced for particular customization 
            maybe if order is not your you could override this procedure
        '''
        mrp_proxy = self.browse(cr, uid, ids, context=context)
        order = []
        for line in mrp_proxy.order_line_ids:
            order.append((line.default_code, line.id))
        line_pool = self.pool.get('sale.order.line')        
        i = 0
        for code, item_id in sorted(order):
            i += 1
            line_pool.write(cr, uid, item_id, {
                'mrp_sequence': i,
                }, context=context)
        return True
        
    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {
            'used_by_mrp_id': False, }, context=context)

    """def _get_totals(self, cr, uid, ids, fields=None, args=None, context=None):
        ''' TODO remove part of old program and old fields
        
            Calculate all totals 
            oc_qty = sum (qty for all line)
            extra_qty = total production - oc_qty
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {}
            #res[order.id]['oc_qty'] = 0.0
            #res[order.id]['previsional_qty'] = 0.0
            #res[order.id]['use_extra_qty'] = 0.0

            for line in order.order_line_ids:
                if line.order_id.forecasted_production_id:
                    res[order.id]['forecast_qty'] += line.product_uom_qty 
                    # TODO check UM?

            #for line in order.order_line_ids:
            #    res[order.id]['oc_qty'] += line.product_uom_qty # TODO UM?

            #for line in order.previsional_line_ids:
            #    res[order.id]['previsional_qty'] += line.product_uom_qty 

            #for line in order.use_mrp_ids: # TO correct (for recursion)
            #    res[order.id]['use_extra_qty'] += \
            #        self.browse(cr, uid, line.id).extra_qty

            #    #res[order.id]['use_extra_qty'] += line.extra_qty 

            #res[order.id]['extra_qty'] = (        # Extra =
            #    order.product_qty +               # Production
            #    res[order.id]['use_extra_qty'] -  # + extra qty used
            #    res[order.id]['oc_qty'] -         # - Ordered
            #    res[order.id]['previsional_qty']) # - Previsional
            #res[order.id]['error_qty'] = False#res[order.id]['extra_qty'] < 0.0
            #res[order.id]['has_extra_qty'] = res[order.id]['extra_qty'] > 0.0
        return res"""
    
    def _get_forecast_total(self, cr, uid, ids, fields=None, args=None, 
            context=None):
        ''' TODO remove part of old program and old fields
        
            Calculate all totals 
            oc_qty = sum (qty for all line)
            extra_qty = total production - oc_qty
        '''
        res = {}        
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = 0.0
            for line in order.order_line_ids:
                if line.order_id.forecasted_production_id:
                    res[order.id] += line.product_uom_qty # TODO check UM?
        return res

    # Fields function:
    def _get_mandatory_delivery(
            self, cr, uid, ids, fields, args, context=None):
        ''' Number of fix delivery
        ''' 
        res = {}
        for mo in self.browse(cr, uid, ids, context=context):
            res[mo.id] = {
                'has_mandatory_delivery': '', 
                'mandatory_delivery': 0,
                }
            for so in mo.order_line_ids:
                if so.has_mandatory_delivery:
                    res[mo.id]['mandatory_delivery'] += 1
                    res[mo.id]['has_mandatory_delivery'] += "*"                    
        return res
        
    _columns = {
        #'oc_qty': fields.function(
        #    _get_totals, method=True, type='float', 
        #    string='OC qty', store=False, readonly=True, multi=True),
        #'previsional_qty': fields.function(
        #    _get_totals, method=True, type='float', 
        #    string='Previsional qty', store=False, readonly=True, multi=True),
        #'use_extra_qty': fields.function(
        #    _get_totals, method=True, type='float', 
        #    string='Use extra qty', store=False, readonly=True, multi=True),
        #'extra_qty': fields.function(
        #    _get_totals, method=True, type='float', 
        #    string='Extra qty', store=False, readonly=True, multi=True),
        #'has_extra_qty': fields.function(
        #    _get_totals, method=True, type='boolean', string='Has extra', 
        #    store=True,
        #    #{'sale.order.line':(_get_extra_production,['product_uom_qty'],10)}, 
        #    readonly=True, multi=True),
        #'error_qty': fields.function( # TODO remove or change function?!?
        #    _get_totals, method=True, type='boolean', 
        #    string='Total error', store=False, readonly=True, multi=True),
        'forecast_qty': fields.function(
            _get_forecast_total, method=True, type='float', 
            string='Forecast qty', store=False, readonly=True),
        
        'used_by_mrp_id': fields.many2one('mrp.production', 'Used by'),
        
        'use_mrp_ids': fields.one2many(
            'mrp.production', 'used_by_mrp_id', 'Use mrp'),
        'order_line_ids': fields.one2many(
            'sale.order.line', 'mrp_id', 'Order line'),
        'previsional_line_ids': fields.one2many(
            'sale.order.line.previsional', 'mrp_id', 'Previsional order'),
        'updated':fields.boolean('Label', required=False),    
        'has_mandatory_delivery': fields.function(_get_mandatory_delivery,
            method=True, type='char', size=1, string='Has fix delivery', 
            store=False, multi=True),
        'mandatory_delivery': fields.function(_get_mandatory_delivery,
            method=True, type='integer', string='Fix delivery', 
            store=False, multi=True),
        }

class MrpProductionWorkcenterLine(orm.Model):
    ''' Accounting external fields
    '''    
    _inherit = 'mrp.production.workcenter.line'
    
    _columns = {
        #'product_id': fields.related('mrp_id', 'product_id', 
        #    type='many2one', relation='product.product', string='Product'),
        'has_mandatory_delivery': fields.related('production_id', 
            'has_mandatory_delivery', type='char', size=1, 
            string='Has fix delivery'),    
        'mandatory_delivery': fields.related('production_id', 
            'mandatory_delivery', type='integer', string='Fix delivery'),    
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
