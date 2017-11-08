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

    """# -----------------------    
    # Override button action:
    # -----------------------    
    def action_button_confirm(self, cr, uid, ids, context=None):
        super(SaleOrder, self).action_button_confirm(
            cr, uid, ids, context=context)
        # Extra action mark order line as order (for production):
        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [
            ('order_id', '=', ids[0])], context=context)
        sol_pool.write(cr, uid, sol_ids, {
            'order_confirmed': True}, context=context)    
        return True"""
    
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
    # XXX double merge with obj after!!!
    _inherit = 'sale.order.line'
    
    # Force new order for production
    # TODO remove:
    #_order = 'mrp_sequence,order_id,sequence,id'    

    # -------------
    # Button event:
    # -------------
    def open_production_form(self, cr, uid, ids, context=None):
        ''' Button that open form of MRP linked
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Production',
            'res_model': 'mrp.production',
            'res_id': line_proxy.mrp_id.id,
            'view_type': 'form',
            'view_mode': 'form,tree',
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            }

    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        # Only in draft mode!
        mrp_pool = self.pool.get('mrp.production')
        sol_proxy = self.browse(cr, uid, ids, context=context)[0]

        mrp_id = context.get('production_order_id', False)
        if not mrp_id: # odd case
            return False

        if sol_proxy.order_id.forecasted_production_id:
            # Forecast order delete line:   
            self.unlink(cr, uid, ids, context=context)            
        else:    
            # TODO test if maked qty!!!
            # Normal order unlink from production:
            # TODO remove line without hide gives error (for focus problem)
            if mrp_id:
                mrp_proxy = mrp_pool.browse(cr, uid, mrp_id, context=context)
                date_planned = mrp_proxy.date_planned
            else:
                date_planned = False
            # Generate a container MRP order
            unlinked_mrp_id = mrp_pool.generate_mrp_unlinked_container(
                cr, uid, date_planned, context=context)
            
            self.write(cr, uid, ids, {
                'mrp_id': unlinked_mrp_id, 
                'mrp_sequence': False, # reset order
                'mrp_unlinked': True, # marked as unlinked
                }, context=context)

        # Reload total from sale order line:        
        return self.pool.get('mrp.production').recompute_total_from_sol(
            cr, uid, [mrp_id], context=context)

    def close_production(self, cr, uid, ids, context=None):
        ''' Close production
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        return self.write(cr, uid, ids, {
            'product_uom_maked_sync_qty': 
                line_proxy.product_uom_qty,
            'sync_state': 'sync',
            }, context=context)                

    def undo_close_production(self, cr, uid, ids, context=None):
        ''' Undo close production (before sync)
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # TODO manage if there's partial!!
        return self.write(cr, uid, ids, {
            #'product_uom_maked_qty': 0.0,
            'product_uom_maked_sync_qty': 0.0,
            'sync_state': 'draft',
            }, context=context)                

    def _mrp_function_similar(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''          
        res = {}
        for item_id in ids:
            res[item_id] = ['', 0.0]

        context = context or {}
        load_status_info = context.get('load_status_info', True) # TODO False!!
        if not load_status_info: 
            return res
        
        # Load all open MRP key = family_id
        mrp_family = {}
        mrp_pool = self.pool.get('mrp.production')        
        mrp_ids = mrp_pool.search(cr, uid, [
            ('state', 'not in', ('done', 'cancel')), # TODO only open lavoration!!!
            ], context=context)
                    
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            mrp_info = '%s [q. %s]\n' % (
                mrp.name.lstrip('MO').lstrip('0'),
                mrp.product_qty,
                )
                
            if mrp.product_id.id not in mrp_family:
                mrp_family[mrp.product_id.id] = {
                    'mrp_similar_info': mrp_info, 
                    'mrp_similar_total': mrp.product_qty,
                    }
            else:    
                mrp_family[mrp.product_id.id][
                    'mrp_similar_info'] += mrp_info
                mrp_family[mrp.product_id.id][
                    'mrp_similar_total'] += mrp.product_qty
                
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = mrp_family.get(
                line.product_id.family_id.id, 
                {'mrp_similar_info': '', 'mrp_similar_total': 0.0})
        return res

    _columns = {
        'mrp_status_info': fields.related(
            'mrp_id', 'mrp_status_info', type='char', string='MRP info',
            store=False),

        'mrp_similar_total': fields.function(
            _mrp_function_similar, method=True, 
            type='float', string='Open MRP total', 
            store=False, multi=True),
        'mrp_similar_info': fields.function(
            _mrp_function_similar, method=True, 
            type='text', string='Open MRP info', 
            store=False, multi=True),
        }        
           
class SaleOrderLine(orm.Model):
    ''' Manage family in sale.order.line
    '''
    _inherit = 'sale.order.line'

    # Function fields
    def _go_in_production_from_state(
            self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate state of production from order
        '''    
        res = {}
        
        for item in self.browse(cr, uid, ids, context=context):
            # check state fot not to go in production:
            if item.order_id.state in ('draft', 'sent', 'cancel', 'done'):
                res[item.id] = False                  
            else:
                res[item.id] = True
        return res        
    
    def _get_sol_family_name(self, cr, uid, ids, fields, args, context=None):
        ''' Save family name for group clause
        '''       
        res = {}
        for sol in self.browse(cr, uid, ids, context=context):
            try:
                res[sol.id] = sol.product_id.family_id.name or _(
                    'Non definita')
            except:
                res[sol.id] = _('Non definita')
        return res       
                
    # Store function fields:
    def _refresh_in_production(self, cr, uid, ids, context=None):
        ''' Get state of production from state of order
        '''
        return self.pool.get('sale.order.line').search(cr, uid, [
            ('order_id', 'in', ids)], context=context)            

    def _refresh_line_in_production(self, cr, uid, ids, context=None):
        ''' Get state of production from state of order
        '''
        return ids
        
    # family_name:    
    def _store_sol_product_id(self, cr, uid, ids, context=None):
        ''' Change product in sale order line
        '''
        _logger.warning('Store sol product_id change')
        return ids

    def _store_sol_template_id(self, cr, uid, ids, context=None):
        ''' Change family in product template
            change product with this template in sol
        '''
        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [
            ('product_id.product_tmpl_id', 'in', ids),
            ], context=context)
        _logger.warning('Update %s lines, template %s' % (
            len(sol_ids), ids,
            ))
        return sol_ids        
            
    _columns = {        
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        'mrp_unlinked': fields.boolean('MRP unlinked'),

        # TODO remove:    
        'order_confirmed': fields.boolean('Order confirmed',
            help='Used for filter in production (T when order in confirmed'),

        # TODO check all cases!!!
        'go_in_production': fields.function(
            _go_in_production_from_state, method=True, type='boolean', 
            string='Go in production', store={
                'sale.order': (
                    _refresh_in_production, ['state'], 10),
                'sale.order.line': (
                    _refresh_line_in_production, ['order_id'], 10),
                }),
                 
        # Delivered:    
        'product_uom_delivered_qty': fields.float(
            'Delivered', digits=(16, 2), 
            help='Quantity delivered (info from account)'),
            
        # Produced:
        # TODO remove field:
        'product_uom_maked_qty': fields.float(
            'Maked (temp.)', digits=(16, 2), 
            help='Partial position till not sync in accounting'),

        'product_uom_maked_sync_qty': fields.float(
            'Maked', digits=(16, 2), 
            help='This quantity is the quantity currently maked'),

        'product_uom_assigned_qty': fields.float(
            '(Assigned) not use!', digits=(16, 2),  # TODO change after add
            help='This quantity is the stock qty present and assigned to'
                'this current line'),

        'production_note': fields.char('Note', size=100),    

        'family_name': fields.function(
            _get_sol_family_name, method=True, type='char', 
            size=80, string='Famiglia', 
            store={
                'sale.order.line': (
                    _store_sol_product_id, ['product_id'], 10),
                'product.template': (
                    _store_sol_template_id, ['family_id'], 10),
                }), 

        #'default_code': fields.related('product_id','default_code', 
        #    type='char', string='Code'),
        # TODO remove with state?
        #'is_produced': fields.boolean('Is produced', required=False),
        'mrp_sequence': fields.integer('MRP order'),
        
        # TODO remove?
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
        # TODO maybe rewrite when unlink anc keep maked qty!!!!!!!!!!!!!!!!!!!!
        # Test if line has accounting element sync:
        order_locked = ''
        for production in self.browse(cr, uid, ids, context=context):
            # Unlink if no produce remain and not order closed:
            test = [line.product_uom_maked_sync_qty 
                for line in production.order_line_ids \
                    #if not line.mx_closed # XXX vedere se attivare (complicaz)
                    ]

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
    def button_refresh(self, cr, uid, ids, context=None):
        ''' Fake button for refresh
        '''
        return True
        
    def button_confirm_forced(self, cr, uid, ids, context=None):
        ''' Close manually the lavoration
        '''
        return self.write(cr, uid, ids, {
            'state': 'done'}, context=context)

    def button_redraft_forced(self, cr, uid, ids, context=None):
        ''' Redraft manually the lavoration
        '''
        return self.write(cr, uid, ids, {
            'state': 'draft'}, context=context)

    def row_in_tree_view(self, cr, uid, ids, context=None):
        ''' Open line in tree vindow for manage better
        '''        
        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [
            ('mrp_id', '=', ids[0]),
            ], context=context)
            
        model_pool = self.pool.get('ir.model.data')
        tree_id = model_pool.get_object_reference(
            cr, uid, 'production_accounting_external',
            'production_sale_order_line_tree_view',
            )[1]
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Righe'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'sale.order.line',
            'view_id': tree_id,
            'views': [(tree_id, 'tree')],
            'domain': [('id', 'in', sol_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
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
                       
        # Close also MRP record:               
        return self.button_confirm_forced(cr, uid, ids, context=context)

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
    
    def generate_mrp_unlinked_container(
            self, cr, uid, date_planned=False, context=None):
        ''' Generate container MRP order for unlinked elements
        '''
        if not date_planned:
            date_planned = datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT)
        name = 'UNLINK-%s.%s' % (date_planned[2:4], date_planned[5:7])

        mrp_ids = self.search(cr, uid, [
            ('name', '=', name),
            #('unlinked_mrp', '=', True), # XXX not necessary
            ], context=context)
        
        if mrp_ids:
            return mrp_ids[0]
        else:
            return self.create(cr, uid, {
                'name': name,
                'product_id': 1,
                'bom_id': False,
                'product_qty': 1, # XXX
                'product_uom': 1, # XXX
                'date_planned': date_planned,
                'state': 'done', # no open for report
                }, context=context)    

    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {
            'used_by_mrp_id': False,
            }, context=context)

    def _get_total_information(self, cr, uid, ids, fields=None, args=None, 
            context=None):
        ''' TODO remove part of old program and old fields
        
            Calculate all totals 
            oc_qty = sum (qty for all line)
            extra_qty = total production - oc_qty
        '''
        res = {}    
        for order in self.browse(cr, uid, ids, context=context):
        
            # Check for total order and total production:
            res[order.id] = {}
            res[order.id]['forecast_qty'] = 0.0
            total = 0.0
            
            for line in order.order_line_ids:
                total += line.product_uom_qty
                if line.order_id.forecasted_production_id:
                    # TODO check UM?
                    res[order.id]['forecast_qty'] += line.product_uom_qty 

            if order.product_qty == total:
                res[order.id]['error_total'] = False
            else:
                res[order.id]['error_total'] = _(
                    'Total of order line different of sum(lines)'
                    'Need reschedule operation (button)!')
                return res
                    
            # Check for total order and total scheduled:    
            scheduled_qty = sum([
                item.lavoration_qty for item in order.scheduled_lavoration_ids
                ])        
            if order.product_qty == scheduled_qty:
                res[order.id]['error_total'] = False
            else:
                res[order.id]['error_total'] = _(
                    'Total of order different of sum(scheduled lines)'
                    'Need reschedule operation (button)!')
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
        
    def _function_get_schedulation_range(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):            
            min_date = False
            max_date = False
            for line in order.scheduled_lavoration_ids:
                date_planned = line.date_planned[:10]
                if not min_date or min_date > date_planned:
                    min_date = date_planned
                if not max_date or max_date < date_planned:
                    max_date = date_planned
            if not (min_date and max_date):        
                res[order.id] = _('No ref.')
            elif min_date == max_date:
                res[order.id] = '[%s]' % min_date
            else:    
                res[order.id] = '[%s - %s]' % (min_date, max_date)
        return res
        
    def _get_order_line_ids(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        ''' 
        res = {}   
        sol_pool = self.pool.get('sale.order.line')
        for item_id in ids:
            item_ids = sol_pool.search(
                cr, uid, [
                    ('mrp_id', '=', item_id)], 
                    order='mrp_sequence,order_id,sequence,id', 
                    context=context)
                   
            res[item_id] = item_ids #sol_pool.browse(cr, uid, item_ids, context=context)        
        return res
        
    _columns = {
        'unlinked_mrp': fields.boolean('Unlinked order', 
            help='Order for keep all unlinked sale line'),
        'forecast_qty': fields.function(
            _get_total_information, method=True, type='float', 
            string='Forecast qty', store=False, readonly=True, multi=True),
        'error_total': fields.function(
            _get_total_information, method=True, type='char', size=80, 
            string='Error in totals', store=False, readonly=True, multi=True),
        
        'used_by_mrp_id': fields.many2one('mrp.production', 'Used by'),
        
        'use_mrp_ids': fields.one2many(
            'mrp.production', 'used_by_mrp_id', 'Use mrp'),
            
        # TODO remove: vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
        'order_line_ids': fields.one2many(
            'sale.order.line', 'mrp_id', 'Order line'),
        # TODO remove: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        
        'sort_order_line_ids': fields.function(
            _get_order_line_ids, method=True, relation='sale.order.line',
            type='one2many', string='Order line', 
            store=False),                        
        
        'previsional_line_ids': fields.one2many(
            'sale.order.line.previsional', 'mrp_id', 'Previsional order'),
        'updated':fields.boolean('Label', required=False),    
        'has_mandatory_delivery': fields.function(_get_mandatory_delivery,
            method=True, type='char', size=1, string='Has fix delivery', 
            store=False, multi=True),
        'mandatory_delivery': fields.function(_get_mandatory_delivery,
            method=True, type='integer', string='Fix delivery', 
            store=False, multi=True),
        
        'mrp_status_info': fields.function(
            _function_get_schedulation_range, method=True, type='char', 
            size=100, string='Sched. info', store=False),
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
