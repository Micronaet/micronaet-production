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

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """
        
    _inherit = 'sale.order.line'
    
    _columns = {
        'previous_mrp': fields.text('Previous MRP', readoly=True),
        }

class MrpProductionSequence(orm.Model):
    ''' Object for keep product line in order depend on parent 3 char code
    '''
    _inherit = 'mrp.production.sequence'

    # Button events:
    def set_for_move_false(self, cr, uid, ids, context=None):
        ''' No for move:
        '''
        return self.write(cr, uid, ids, {
            'select_for_move': False,
            }, context=context)
        
    def set_for_move_true(self, cr, uid, ids, context=None):
        ''' No for move:
        '''
        return self.write(cr, uid, ids, {
            'select_for_move': True,
            }, context=context)
        
    _columns = {
        'select_for_move': fields.boolean('Select for move'),
        }

class MrpProduction(orm.Model):
    ''' Add extra field to mrp order
    '''
    _inherit = 'mrp.production'

    # Button events:
    def child_mrp_open(self, cr, uid, ids, context=None):
        ''' Open child MRP
        ''' 
        return {
            'type': 'ir.actions.act_window',
            'name': _('Child MRP'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'mrp.production',
            #'view_id': view_id, # False
            'views': [(False, 'form'),(False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
        
    def join_uncomplete_mrp_production_button(
            self, cr, uid, ids, context=None):    
        ''' Join uncomplete production
        '''    
        # Pool used:
        sol_pool = self.pool.get('sale.order.line')
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        join_uncomplete_mrp_id = current_proxy.join_uncomplete_mrp_id
        if not join_uncomplete_mrp_id:
            raise osv.except_osv(
                _('Nothing to move'), 
                _('Choose production for move here before!'),
                )
            
        # ---------------------------------------------------------------------
        # Select uncomplete production to move here:
        # ---------------------------------------------------------------------
        to_move_ids = []
        for sol in current_proxy.join_uncomplete_mrp_id.order_line_ids:
            product_uom_qty = sol.product_uom_qty
            delivered_qty = sol.delivered_qty
            product_uom_maked_sync_qty = sol.product_uom_maked_sync_qty
            if product_uom_qty <= delivered_qty or \
                    product_uom_qty <= product_uom_maked_sync_qty:
                to_move_ids.append(sol.id)

        if not to_move_ids:
            raise osv.except_osv(
                _('Nothing to move'), 
                _('All line are delivered or produced!'),
                )

        # Move line:
        sol_pool.write(cr, uid, line_ids, {
            'mrp_id': current_proxy.id,
            }, context=context)

        # Reset move field:
        self.write(cr, uid, ids, {
            'join_uncomplete_mrp_id': False,
            }, context=context)        
        
        # Reorder force (for new line)
        self.force_order_sequence(
            cr, uid, [current_proxy.id], context=context)
        
        return True
        
    def generate_child_production_from_sequence(
            self, cr, uid, ids, context=None):
        ''' Choose what production move in new block created here
        '''
        # Pool used:
        sequence_pool = self.pool.get('mrp.production.sequence')
        sol_pool = self.pool.get('sale.order.line')
        counter_pool = self.pool.get('ir.sequence')
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # ---------------------------------------------------------------------
        # Select sequence to move (check if present):
        # ---------------------------------------------------------------------
        sequence_parent = []
        sequence_ids = []
        for sequence in current_proxy.sequence_ids:
            if sequence.select_for_move: # Move only selected:
                sequence_parent.append(sequence.name)
                sequence_ids.append(sequence.id)
            
        if not sequence_ids:
            raise osv.except_osv(
                _('No selection'), 
                _('Select one sequence block to move before press move block button'),
                )
                
        # Delete sequence because moved:
        sequence_pool.unlink(cr, uid, sequence_ids, context=context)

        # ---------------------------------------------------------------------
        # Create or append production
        # ---------------------------------------------------------------------
        # Append mode:
        move_parent_mrp_id = current_proxy.move_parent_mrp_id.id or False
        
        # Create mode:
        if move_parent_mrp_id:
            # Reset move field:
            self.write(cr, uid, ids, {
                'move_parent_mrp_id': False,
                }, context=context)        
        else:
            # Create new production from here
            move_parent_mrp_id = self.create(cr, uid, {
                'parent_mrp_id': ids[0], # Parent reference
                'name': counter_pool.get(cr, uid, 'mrp.production'),
                'date_planned': current_proxy.date_planned,
                'user_id': uid,
                'product_qty': 1.0, # TODO update total (after move line)!
                'bom_id': current_proxy.bom_id.id,
                'product_id': current_proxy.product_id.id,
                'product_uom': current_proxy.product_id.uom_id.id,
                'sequence_mode': current_proxy.sequence_mode,
                }, context=context)
                

        # ---------------------------------------------------------------------
        # Move lines depend on sequence selected
        # ---------------------------------------------------------------------
        # Get line list to move:
        sequence_mode = current_proxy.sequence_mode
        line_ids = []
        for line in current_proxy.order_line_ids:
            default_code = line.product_id.default_code
            parent_code = self.get_sort_code(sequence_mode, default_code)
            if parent_code in sequence_parent:
                line_ids.append(line.id)
                
        # Move line:
        sol_pool.write(cr, uid, line_ids, {
            'mrp_id': move_parent_mrp_id}, context=context)        
        
        # Load parent in child
        self.force_order_sequence(
            cr, uid, [move_parent_mrp_id], context=context)
        
        # Return view:    
        model_pool = self.pool.get('ir.model.data')
        #view_id = model_pool.get_object_reference(
        #    'module_name', 'view_name')[1]
        view_id = False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Child MRP'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': move_parent_mrp_id,
            'res_model': 'mrp.production',
            'view_id': view_id, # False
            'views': [(view_id, 'form'),(False, 'tree')],
            'domain': [('id', '=', move_parent_mrp_id)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            } 
            
    _columns = {
        'parent_mrp_id': fields.many2one(
            'mrp.production', 'Parent production'),
        'move_parent_mrp_id': fields.many2one(
            'mrp.production', 'Move prodution'), # TODO domain in view

        'join_uncomplete_mrp_id': fields.many2one(
            'mrp.production', 'Move prodution'), # TODO domain in view
        }

class MrpProduction(orm.Model):
    ''' Add extra field to mrp order
    '''
    _inherit = 'mrp.production'
    
    _columns = {
        'child_mrp_ids': fields.one2many(
            'mrp.production', 'parent_mrp_id', 'Child MRP'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
