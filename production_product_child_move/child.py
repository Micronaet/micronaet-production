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
        # Create or append production
        # ---------------------------------------------------------------------
        # Append mode:
        move_parent_mrp_id = current_proxy.move_parent_mrp_id.id or False
        
        # Create mode:
        if not move_parent_mrp_id:
            # Create new production from here
            move_parent_mrp_id = self.create(cr, uid, {
                'parent_mrp_id': ids[0], # Parent reference
                'name': counter_pool.get(cr, uid, 'mrp.production'),
                'date_planned': curent_proxy.schedule_from_date,
                'user_id': uid,
                'product_qty': 1.0, # TODO update total (after move line)!
                'bom_id': counter_pool.bom_id.id,
                'product_id': counter_pool.product_id.id,
                'product_uom': counter_pool.product_id.uom_id.id,
                }, context=context)
                
        # Reset move field:
        self.write(cr, uid, ids, {
            'move_parent_mrp_id': False,
            }, context=context)        

        # ---------------------------------------------------------------------
        # Select sequence to move:
        # ---------------------------------------------------------------------
        sequence_parent = []
        sequence_ids = []
        for sequence in current_proxy.sequence_ids:
            if sequence.select_for_move: # Move only selected:
                sequence_parent.append(sequence.name)
                sequence_ids.append(sequence.id)
            
        # Delete sequence because moved:
        sequence_pool.unlink(cr, uid, sequence_ids, context=context)

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
            'views': [(False, 'tree'), (view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            } 
            
    _columns = {
        'parent_mrp_id': fields.many2one(
            'mrp.production', 'Parent production'),
        'move_parent_mrp_id': fields.many2one(
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
