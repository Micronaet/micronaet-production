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

class StockPicking(orm.Model):
    """ Model name: StockPicking
    """
    
    _inherit = 'stock.picking'
    
    _columns = {
        'dust': fields.boolean('Month dust unload'),
    }

class MrpPaint(orm.Model):
    """ Model name: MrpPaint
    """
    
    _name = 'mrp.paint'
    _description = 'Paint form'
    _rec_name = 'date'
    _order = 'date'

    # -------------------------------------------------------------------------
    # Button or procedure:
    # -------------------------------------------------------------------------
    # Fast Workflow:
    def wf_reopen_paint(self, cr, uid, ids, context=None):
        ''' Reopen painting form
        '''
        move_pool = self.pool.get('stock.move')
        
        # ---------------------------------------------------------------------
        # Remove stock movement:
        # ---------------------------------------------------------------------
        move_ids = [
            cost.move_id.id for cost in self.browse(
                cr, uid, ids, context=context)[0].cost_ids if cost.move_id]
        if move_ids:
            move_pool.write(cr, uid, move_ids, {
                'state': 'draft',
                }, context=context)
            move_pool.unlink(cr, uid, move_ids, context=context)        
            
        return self.write(cr, uid, ids, {
            'state': 'draft',
            }, context=context)
        
    def wf_close_paint(self, cr, uid, ids, context=None):
        ''' Create stock move to unload dust product
        '''
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        type_pool = self.pool.get('stock.picking.type')
        cost_pool = self.pool.get('mrp.paint.cost')

        # ---------------------------------------------------------------------
        # A) Picking:        
        # ---------------------------------------------------------------------
        # Check if picking is present:
        paint = self.browse(cr, uid, ids, context=context)[0]
                
        if not paint.picking_id: #  Search this month painting picking:
            # Picking date every first day of the month:
            date = paint.date
            picking_date = '%s-01 08:00:00' % date[:7] 
            
            picking_ids = picking_pool.search(cr, uid, [
                ('min_date', '=', picking_date),
                ('dust', '=', True),
                ], context=context)
            if picking_ids:
                picking_id = picking_ids[0]
            else:   
                type_ids = type_pool.search(cr, uid, [
                    ('code', '=', 'internal'),
                    ('name', 'ilike', 'SL '),
                    ], context=context)
                if not type_ids:
                    raise osv.except_osv(
                        _('Error'), 
                        _('SL stocking move type not found, create before!'),
                        )
                picking_type = type_pool.browse(
                    cr, uid, type_ids, context=context)[0]
                    
                picking_id = picking_pool.create(cr, uid, { 
                    'partner_id': paint.create_uid.company_id.partner_id.id,
                    'min_date': picking_date,                    
                    'origin': 'Verniciatura mese: %s' % date[:7],
                    'picking_type_id': picking_type.id,                    
                    'dust': True,
                    }, context=context)
                    
                # Save for next time:    
                self.write(cr, uid, paint.id, {
                    'picking_id': picking_id,
                    }, context=context)    

                # Reload data:    
                paint = self.browse(cr, uid, ids, context=context)[0]

        picking = paint.picking_id

        # ---------------------------------------------------------------------
        # Stock movement:
        # ---------------------------------------------------------------------
        link_move = []
        picking_type = picking.picking_type_id
        location_id = picking_type.default_location_src_id.id
        location_dest_id = picking_type.default_location_dest_id.id
        origin = picking.origin
        
        for cost in self.browse(
                cr, uid, ids, context=context)[0].cost_ids:
            product = cost.dust_id
            if not product:
                continue    
            move_id = move_pool.create(cr, uid, {
                'product_id': product.id,
                'product_uom_qty': cost.dust_weight,

                'name': product.name,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'picking_type_id': picking_type.id,
                'origin': origin,
                'product_id': product.id,
                'date': paint.create_date,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'state': 'done',
                }, context=context)

            link_move.append((cost.id, move_id))    
            
        # Update cost linked to move:
        for cost_id, move_id in link_move:
            cost_pool.write(cr, uid, [cost_id], {
                'move_id': move_id,
                }, context=context)

        return self.write(cr, uid, ids, {
            'state': 'confirmed',
            'total_real_confirmed': paint.total_real,
            'total_calculated_confirmed': paint.total_calculated,
            'calc_confirmed': paint.calc,
            }, context=context)
    
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
                'gas_total_cost': paint.gas_id.standard_price * gap, # XXX
                }
        return res

    def _get_total_paint(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}

        for paint in self.browse(cr, uid, ids, context=context):
            res[paint.id] = {}
            error = False
            calc = ''

            # -----------------------------------------------------------------
            # Total real with all cost and error
            # -----------------------------------------------------------------
            # Gas:
            partial = paint.gas_id.standard_price * (
                paint.gas_stop - paint.gas_start)
            calc += u'''<b>Gas:</b> Lettura (%s - %s)M³ x 
                %s €/m³ = <b>%s €</b>%s<br/>''' % (
                    paint.gas_stop,
                    paint.gas_start,
                    paint.gas_id.standard_price, 
                    partial,
                    '' if partial else ' *ERRORE',
                    )
            if not partial:
                error = True
                    
            work_unit = paint.work_id.standard_price
            calc += u'''<b>Costo lavoratore: %s €</b><br/>%s''' % (
                work_unit,
                '' if work_unit else ' *ERRORE',
                )
            if not work_unit:
                error = True
                
            i = 0
            calc += u'<br/><b>Costi reali:</b><br/>'
            for line in paint.cost_ids:
                i += 1

                # -------------------------------------------------------------
                # Dust:
                # -------------------------------------------------------------
                subtotal = line.dust_weight * line.dust_id.standard_price
                partial += subtotal
                calc += u'''
                    <b>Colore %s:</b> 
                        [<b>Polvere: </b>%s Kg x %s = <b>%s €</b>%s] + 
                    ''' % (
                        line.color_id.name or '',
                        line.dust_weight,
                        line.dust_id.standard_price,
                        subtotal,
                        '' if subtotal else ' *ERRORE',     
                        )                    
                if not subtotal:
                    error = True
                                
                # -------------------------------------------------------------
                # Lavoration:
                # -------------------------------------------------------------
                subtotal = work_unit * line.work_hour 
                partial += subtotal
                calc += u'''[<b>Lavorazione: </b>%s x %s H = <b>%s €</b>%s]
                    <br/>''' % (
                        work_unit,
                        line.work_hour,
                        subtotal,
                        '' if subtotal else ' *ERRORE',                    
                        )
                if not subtotal:
                    error = True
            res[paint.id]['total_real'] = partial
            calc += u'''<b>Totale reale: %s €</b><br/><br/>''' % partial

            # -----------------------------------------------------------------
            # Total calculated with CPV rate:
            # -----------------------------------------------------------------
            partial = 0.0
            calc += u'''<b>Totale teorici:</b><br/>'''
            for line in paint.total_ids:
                subtotal = line.product_total * line.cpv_cost
                partial += subtotal
                calc += u'''<b>Codice %s:</b> %s PZ x %s € = <b>%s €</b>%s
                <br/>''' % (
                    line.product_code,
                    line.product_total,
                    line.cpv_cost,                    
                    subtotal,
                    '' if subtotal else ' *ERRORE',                    
                    )
                if not subtotal:
                    error = True

            res[paint.id]['total_calculated'] = partial                
            calc += u'''<b>Totale teorico: %s €</b>''' % partial

            res[paint.id]['error'] = error
            res[paint.id]['calc'] = calc
        return res
        
    # -------------------------------------------------------------------------       
    # Table:
    # -------------------------------------------------------------------------       
    _columns = {
        'date': fields.date('Date', required=True),

        # ---------------------------------------------------------------------
        # GAS:
        # ---------------------------------------------------------------------
        'gas_id': fields.many2one('product.product', 'Gas product', 
            help='Product used to manage unit cost for Gas'),
        'gas_unit': fields.related(
            'gas_id', 'standard_price', 
            type='float', string='Gas unit', store=False),
        'gas_start': fields.integer('Gas start'),        
        'gas_stop': fields.integer('Gas stop'),        
        'gas_total': fields.function(_get_gas_total, method=True, 
            type='integer', string=u'Gas total M³', multi='gas_sum'), 
        'gas_total_cost': fields.function(_get_gas_total, method=True, 
            type='float', string='Gas total cost', multi='gas_sum'), 

        # ---------------------------------------------------------------------
        # WORK:
        # ---------------------------------------------------------------------
        'work_id': fields.many2one('product.product', 'Word product', 
            help='Product used to manage unit cost for work'),
        'work_unit': fields.related(
            'work_id', 'standard_price', 
            type='float', string='Work unit', store=False),
        
        'note': fields.text('Note'),

        # Dynamic total:        
        'total_real': fields.function(
            _get_total_paint, method=True, 
            type='float', string='Total real', 
            store=False, multi=True), 
        'total_calculated': fields.function(
            _get_total_paint, method=True, 
            type='float', string='Total teorical', 
            store=False, multi=True), 
        'calc': fields.function(
            _get_total_paint, method=True, 
            type='text', string='Calc', 
            store=False, multi=True), 
        'error': fields.function(
            _get_total_paint, method=True, 
            type='boolean', string='Has error', 
            store=False, multi=True), 

        # Saved total:    
        'total_real_confirmed': fields.float('Total real confirmed', 
            digits=(16, 2)),
        'total_calculated_confirmed': fields.float('Total teorical confirmed', 
            digits=(16, 2)),
        'calc_confirmed': fields.text('Calc detail'),    
        
        # Linked document:
        'picking_id': fields.many2one('stock.picking', 'Picking', 
            help='Picking linked for unload documents (SL type)'),
        
        # Fast workflow:
        'state': fields.selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ], 'State', readonly=True),
        }

    _defaults = {
        # Default value:
        'state': lambda *x: 'draft',
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
    
    # TODO delete linked move if present:
    # TODO update linked move when change data or create

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
        'move_id': fields.many2one('stock.move', 'Move linked'),
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
