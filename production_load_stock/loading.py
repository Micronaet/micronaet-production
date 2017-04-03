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

# TODO delete vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
class MrpProduction(orm.Model):
    """ Model name: Temp procedure for update stock
    """    
    _inherit = 'mrp.production'
    
    def button_create_cl_sl(self, cr, uid, ids, context=None):
        ''' Create CL and SL temporary (after when B q is saved)
        '''
        context = context or {}
        context['forced_record'] = True # for date problems
        self.update_all_mrp_production(cr, uid, ids, context=context)
        
        # Update status information:
        pick_pool = self.pool.get('stock.picking')
        pick_ids = pick_pool.search(cr, uid, [
            ('production_id', '=', ids[0])], context=context)
        if not pick_ids:
            return False
        
        # Log pick info:
        log = ''
        for pick in pick_pool.browse(cr, uid, pick_ids, context=context):
            # TODO add also no bom information? 
            log += '%s: %s [# %s]\n' % (
                pick.production_load_type.upper(), 
                pick.name, 
                len(pick.move_lines))
 
        # log mrp info
        mrp = pick.production_id
        log += 'MRP: %s [# %s]\n' % (mrp.name, len(mrp.order_line_ids))
        
        self.write(cr, uid, ids, {
            'pick_status': log}, context=context)
        return True
    
    def button_get_picking(self, cr, uid, ids, context=None):
        ''' Open CL and SL picking
        '''
        pick_pool = self.pool.get('stock.picking')
        company_pool = self.pool.get('res.company')
        
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(cr, uid, company_ids, 
            context=context)[0]

        if company_proxy.stock_report_mrp_in_ids: # XXX only first
            mrp_type_in = company_proxy.stock_report_mrp_in_ids[0].id
        else:
            mrp_type_in = False    
        if company_proxy.stock_report_mrp_out_ids:    
            mrp_type_out = company_proxy.stock_report_mrp_out_ids[0].id
        else:
            mrp_type_out = False

        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        item_ids = []        
        item_ids.append(pick_pool.get_mrp_picking(
            cr, uid, mrp_proxy, 'cl', mrp_type_in, 
            context=context))
            
        item_ids.append(pick_pool.get_mrp_picking(
            cr, uid, mrp_proxy, 'sl', mrp_type_out, 
            context=context))
        return {
            'type': 'ir.actions.act_window',
            'name': 'MRP pick in e out',
            'res_model': 'stock.picking',
            #'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', item_ids)],
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            }
        
    def update_all_mrp_production(self, cr, uid, ids, context=None):
        ''' Rewrite all production in all order
        '''
        context = context or {}
        forced = context.get('forced_record', False)

        log_file = 'update_production.%s.csv' % (ids[0])
        log_path = os.path.expanduser('~')
        log_filename = os.path.join(log_path, log_file)
        log_f = open(log_filename, 'a')
                
        start_date = '2016-01-01'
        sol_pool = self.pool.get('sale.order.line')
        log_f.write('Start update procedure')
        
        i = 0
        for mrp in self.browse(cr, uid, ids, context=context): # mrp_id
            i += 1
            date_planned = mrp.date_planned

            if forced or date_planned >= start_date:
                state = 'MAKED'
            else:    
                state = 'JUMPED'
                
            log_f.write('[%s] Order: %s dated %s [%s]' % (
                state,
                mrp.name, 
                mrp.date_planned,
                mrp.product_id.name,
                ))
                
            for line in mrp.order_line_ids:                
                if state == 'MAKED':
                    sol_pool.write(cr, uid, [line.id], {
                        'product_uom_maked_sync_qty': 
                            line.product_uom_maked_sync_qty,
                        }, context=context)

                log_f.write('>>> [%s] Production: %s OC: %s B: %s' % (
                    state,
                    line.product_id.name, 
                    line.product_uom_qty,
                    line.product_uom_maked_sync_qty,                    
                    ))
        log_f.write('End update procedure')
        
        return True
           
    _columns = {
        'pick_status': fields.text('Update status')
        }
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

class StockPicking(orm.Model):
    """ Model name: Stock picking for production
    """    
    _inherit = 'stock.picking'
    
    # Utility:
    def get_mrp_picking(self, cr, uid, mrp_proxy, mode, picking_type_id, 
            context=None):
        ''' Search or create pick lined to mrp (bf or cl)
        '''
        pick_ids = self.search(cr, uid, [
            ('production_id', '=', mrp_proxy.id),
            ('production_load_type', '=', mode),
            ], context=context)
        if pick_ids:
            return pick_ids[0]
            
        return self.create(cr, uid, {
            'production_id': mrp_proxy.id,
            'production_load_type': mode,
            'origin': mrp_proxy.name,
            'partner_id': mrp_proxy.company_id.partner_id.id,
            'picking_type_id': picking_type_id,
            'state': 'done', 
            }, context=context)    

    _columns = {
        'production_id': fields.many2one(
            'mrp.production', 'MRP', ondelete='cascade',
            help='Link pick to production'),
        'production_load_type': fields.selection([
            ('cl', 'Product load'),
            ('sl', 'Material unload'),
            ], 'Production load type'),
        }

class StockQuant(orm.Model):
    """ Model name: Sale order for production
    """    
    _inherit = 'stock.quant'

    _columns = {
        'production_sol_id': fields.many2one(
            'sale.order.line', 'Sale line linked', ondelete='set null',
            help='Line linked for load / unload for production'),
        'persistent': fields.boolean('Persistent'),
        }

class StockMove(orm.Model):
    """ Model name: Sale order for production
    """    
    _inherit = 'stock.move'

    _columns = {
        'production_sol_id': fields.many2one(
            'sale.order.line', 'Sale line linked', ondelete='set null',
            help='Line linked for load / unload for production'),
        'production_load_type': fields.selection([
            ('cl', 'Product load'),
            ('sl', 'Material unload'),
            ], 'Production load type'),
        'persistent': fields.boolean('Persistent'),
        }     

    _defaults = {        
        # Default value:
        'production_load_type': lambda *x: 'cl',    
        }

class SaleOrder(orm.Model):
    """ Model name: Sale order for production
    """    
    _inherit = 'sale.order.line'

    #à Button:
    def open_product_bom(self, cr, uid, ids, context=None):
        ''' 
        '''
        assert len(ids), 'Only one row a time!'
        
        bom_pool = self.pool.get('mrp.bom')
        sol_proxy = self.browse(cr, uid, ids, context=context)
        product = sol_proxy.product_id
        bom_ids = bom_pool.search(cr, uid, [
            ('product_id', '=', product.id),
            ('sql_import', '=', True),
            ], context=context)
        if bom_ids:
            bom_id = bom_ids[0]
        else:    
            bom_id = bom_pool.create(cr, uid, {
                'sql_import': True,
                'product_id': product.id,
                'product_tmpl_id': product.product_tmpl_id.id,
                'code': product.default_code, 
                'product_qty': 1.0,
                #'product_uom'
                }, context=context)            
        return {
            'type': 'ir.actions.act_window',
            'name': 'BOM',
            'res_model': 'mrp.bom',
            'res_id': bom_id,
            'view_type': 'form',
            'view_mode': 'form', # tree
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            #'domain': [('product_id', 'in', ids)],
            }
        
    # Utility:
    def _search_bom_for_product(self, cr, uid, product_id, context=None):
        ''' Search reference BOM for product (now is the one that was imported
        ''' 
        bom_pool = self.pool.get('mrp.bom')
        bom_ids = bom_pool.search(cr, uid, [
            ('product_id', '=', product_id),
            ('sql_import', '=', True),
            ], context=context)
        if not bom_ids:
            #_logger.error('No BOM for product ID %s passed' % product_id)
            return False
        return bom_pool.browse(cr, uid, bom_ids, context=context)[0]
    
    def _create_stock_move_for_production(self, cr, uid, line, bom, 
            context=None):
        ''' Generate dict for stock production move
        '''    
        pass
        # TODO
        return {}
        
    def _recreate_production_sol_move(self, cr, uid, sol_ids, 
            context=None):
        ''' Generic function used for create / update stock move,
            CL and SL, used from create and write method    
            
            XXX Note:
            03/04/2017: Now Unload SL movement are dynamically calculated        
        '''        
        assert len(sol_ids), 'Only one row a time!'
        
        if context is None:
            context = {}
            
        #persistent = context.get('force_persistent', False)
        
        # Pool used:
        pick_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')
        company_pool = self.pool.get('res.company')

        # Parameter for location:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(cr, uid, company_ids, 
            context=context)[0]

        # TODO remove stock elements (use type)?:
        stock_location = company_proxy.stock_location_id.id
        mrp_location = company_proxy.stock_mrp_location_id.id
        if not(mrp_location and stock_location):
            raise osv.except_osv(
                _('Error'), 
                _('Set up in company location for stock and mrp!'))
        
        if company_proxy.stock_report_mrp_in_ids: # XXX only first
            mrp_type_in = company_proxy.stock_report_mrp_in_ids[0].id
        else:
            mrp_type_in = False    
            
        # XXX 03/04/2017: Now Unload SL movement are dynamicalli calculated
        #if company_proxy.stock_report_mrp_out_ids:    
        #    mrp_type_out = company_proxy.stock_report_mrp_out_ids[0].id
        #else:
        #    mrp_type_out = False
        
        line_proxy = self.browse(cr, uid, sol_ids, context=context)[0]        
        # Test if is a stock load family:
        try:
            if line_proxy.mrp_id.bom_id.product_tmpl_id.no_stock_operation:
                _logger.warning('No load stock family, do nothing!')
                return True
        except:        
            _logger.warning('Error test no load stock family!')
            # continune unload stock as default
        
        # Get pick document linked to MRP production:
        mrp_picking_in = pick_pool.get_mrp_picking(
            cr, uid, line_proxy.mrp_id, 'cl', mrp_type_in, 
            context=context)
            
        # XXX 03/04/2017: Now Unload SL movement are dynamically calculated
        #mrp_picking_out = pick_pool.get_mrp_picking(
        #    cr, uid, line_proxy.mrp_id, 'sl', mrp_type_out, 
        #    context=context)
        # get product BOM for materials:
        #bom_proxy = self._search_bom_for_product(cr, uid, 
        #    line_proxy.product_id.id, context=context)

        #if persistent:
        #    maked_qty = line_proxy.product_uom_force_qty or 0.0
        #else:
        maked_qty = line_proxy.product_uom_maked_sync_qty or 0.0

        # -------------------------------
        # Unlink all stock move (always):
        # -------------------------------
        # XXX 03/04/2017: Now Unload SL movement are dynamically calculated
        #if not persistent: # XXX domain persistent status for delete?
        move_ids = move_pool.search(cr, uid, [
            ('production_sol_id', '=', line_proxy.id),
            #('persistent', '=', False),
            ], context=context)
        if move_ids:
            # Set to draft:
            move_pool.write(cr, uid, move_ids, {
                'state': 'draft',
                }, context=context)
            # delete:    
            move_pool.unlink(cr, uid, move_ids, context=context)

        # -----------------------
        # Unlink all stock quant:
        # -----------------------
        quant_ids = quant_pool.search(cr, uid, [
            ('production_sol_id', '=', line_proxy.id),
            #('persistent', '=', False),
            ], context=context)
        if quant_ids:
            # Set to draft:
            quant_pool.unlink(cr, uid, quant_ids, context=context)

        if not maked_qty:   
            return True
        
        # ---------------------------------------------------------------------
        # Create SL move for materials:
        # ---------------------------------------------------------------------
        # XXX 03/04/2017: Now Unload SL movement are dynamicalli calculated
        # so stopped procedure for unload with movements:
        #if bom_proxy:
        #    # Unload materials:
        #    for bom in bom_proxy.bom_line_ids:
        #        unload_qty = bom.product_qty * maked_qty
        #        if unload_qty <= 0.0:
        #            continue # jump line                    
        #        # Move create:    
        #        move_pool.create(cr, uid, {
        #            'picking_id': mrp_picking_out,
        #            'production_load_type': 'sl',
        #            'location_dest_id': mrp_location,
        #            'location_id': stock_location,
        #            'picking_type_id': mrp_type_out,
        #            'product_id': bom.product_id.id,
        #            'product_uom_qty': unload_qty, 
        #            'product_uom': bom.product_id.uom_id.id,
        #            #'product_uom_qty',
        #            #'product_uos',
        #            #'product_uos_qty',
        #            'production_sol_id': line_proxy.id,
        #            'state': 'done', # confirmed, available
        #            'date_expected': datetime.now().strftime(
        #                DEFAULT_SERVER_DATE_FORMAT),
        #            'origin': line_proxy.mrp_id.name,
        #            'display_name': 'SL: %s' % line_proxy.product_id.name,
        #            'name': 'SL: %s' % line_proxy.product_id.name,
        #            'persistent': persistent,
        #            #'warehouse_id',
        #            #'weight'
        #            #'weight_net',
        #            #'group_id'
        #            #'production_id'
        #            #'product_packaging'                    
        #            #'company_id'
        #            #'date':
        #            #date_expexted'
        #            #'note':,
        #            #'partner_id':
        #            #'price_unit',
        #            #'priority',.                    
        #            }, context=context)                 
        #        # Quants create:    
        #        quant_pool.create(cr, uid, {
        #            'in_date': datetime.now().strftime(
        #                DEFAULT_SERVER_DATETIME_FORMAT),
        #            'cost': 0.0, # TODO
        #            'location_id': stock_location,
        #            'product_id': bom.product_id.id,
        #            'qty': - unload_qty, 
        #            #'product_uom': bom.product_id.uom_id.id,
        #            'production_sol_id': line_proxy.id,
        #            'persistent': persistent,
        #            }, context=context)   
        #else:
        #    # No bom error!!
        #    #_logger.error('BOM not found sql_import for product: %s' % (
        #    #    line_proxy.product_id.default_code or ''))
        #    raise osv.except_osv(
        #        _('Error'), 
        #        _('BOM not found sql_import for product: %s' % (
        #            line_proxy.product_id.default_code or '')))
        
        # ---------------------------------------------------------------------
        # CL for load Product:    
        # ---------------------------------------------------------------------
        # TODO
        #if not persistent:
        # XXX 03/04/2017: Now Unload SL movement are dynamicalli calculated
        # XXX Always load B of F quantity
        move_pool.create(cr, uid, {
            'picking_id': mrp_picking_in,
            'production_load_type': 'cl',
            'picking_type_id': mrp_type_in,
            'location_dest_id': stock_location,
            'location_id': mrp_location,
            'product_id': line_proxy.product_id.id,
            'product_uom_qty': maked_qty, 
            'product_uom': line_proxy.product_id.uom_id.id,
            'production_sol_id': line_proxy.id,
            #'product_uom_qty',
            #'product_uos',
            #'product_uos_qty',
            'state': 'done', # confirmed, available
            'date_expected': datetime.now().strftime(
                DEFAULT_SERVER_DATE_FORMAT),
            'origin': line_proxy.mrp_id.name,
            'display_name': 'CL: %s' % line_proxy.product_id.name,
            'name': 'CL: %s' % line_proxy.product_id.name,
            #'warehouse_id',
            #'picking_type_id',

            #'weight'
            #'weight_net',
            #'picking_id'
            #'group_id'
            #'production_id'
            #'product_packaging'                    
            #'company_id'
            #'date':
            #date_expexted'
            #'note':,
            #'partner_id':
            #'price_unit',
            #'priority',.                    
            }, context=context)
            
        # Quants create:    
        quant_pool.create(cr, uid, {
            'in_date': datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT),
            'cost': 0.0, # TODO
            'location_id': stock_location,
            'product_id': line_proxy.product_id.id,
            'qty': maked_qty, 
            'production_sol_id': line_proxy.id,
            }, context=context)   
        return True
        
    def write(self, cr, uid, ids, vals, context=None):
        """ Update record(s) comes in {ids}, with new value comes as {vals}
            return True on success, False otherwise
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids to be update
            @param vals: dict of new values to be set
            @param context: context arguments, like lang, time zone
            
            @return: True on success, False otherwise
        """
        res = super(SaleOrder, self).write(
            cr, uid, ids, vals, context=context)

        # Check maked qty for create production moves:
        if 'product_uom_maked_sync_qty' in vals:
            self._recreate_production_sol_move(cr, uid, ids, 
                context=context)
        return res
    
    def create(self, cr, uid, vals, context=None):
        """ Create a new record for a model ClassName
            @param cr: cursor to database
            @param uid: id of current user
            @param vals: provides a data for new record
            @param context: context arguments, like lang, time zone
            
            @return: returns a id of new record
        """    
        res_id = super(SaleOrder, self).create(
            cr, uid, vals, context=context)
        
        # Check maked qty for create production moves:
        maked_qty = vals.get('product_uom_maked_sync_qty', 0.0)
        if maked_qty:
            self._recreate_production_sol_move(cr, uid, [res_ids], 
                context=context)            
        return res_id
    
    _columns = {
        'move_production_ids': fields.one2many(
            'stock.move', 'production_sol_id', 
            'Production moves'), 
            
        # Force persistent over quantity:    
        'product_uom_force_qty': fields.float(
            'Forced', digits=(16, 2), help='Force extra qty to confirm'),        
        #'product_uom_force_remove': fields.float(
        #    'Forced removed', digits=(16, 2), help='Force removed'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
