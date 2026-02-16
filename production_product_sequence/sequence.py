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
    """ Object for keep product line in order depend on parent 3 char code
    """
    _name = 'mrp.production.sequence'
    _description = 'MRP production sequence'
    _order = 'sequence, name'    
    
    # Button:
    def remove_parent_block(self, cr, uid, ids, context=None):
        """ Remove block and all element of this block
        """
        # Pool used:
        mrp_pool = self.pool.get('mrp.production')
        
        block_proxy = self.browse(cr, uid, ids, context=context)[0]
        parent_name = block_proxy.name
        sequence_mode = block_proxy.mrp_id.sequence_mode
        
        #TODO Duplicate block, better as a function?
        free_ids = []        
        for line in block_proxy.mrp_id.order_line_ids:
            default_code = line.product_id.default_code            
            if not default_code:
                raise osv.except_osv(
                    _('Product code'), 
                    _('Codice prodotto non presente: %s' % line.product_id.name),
                    )
            parent_code = mrp_pool.get_sort_code(
                sequence_mode, default_code)

            if parent_name == parent_code:
                free_ids.append(line.id)
        
        # Free all sol in block        
        self.pool.get('sale.order.line').write(cr, uid, free_ids, {
            'mrp_id': False, 
            'mrp_sequence': False, # reset order
            }, context=context)
        
        # Delete record block:    
        #TODO give error: self.unlink(cr, uid, ids, context=context)
        return True
        
    # ----------------
    # Field functions:
    # ----------------
    _columns = {
        'sequence': fields.integer('Sequence'), 
        'name': fields.char(
            'Parent', size=15, required=True), 
        'mrp_id': fields.many2one('mrp.production', 'MRP order'),
        'total': fields.integer('Quantity'),
        'done': fields.integer('Fatti'),
        'remain': fields.integer('Residui'),
        }
    _defaults = {
        'sequence': lambda *x: 1000, # New line go bottom
        }

class MrpProduction(orm.Model):
    """ Add extra field to mrp order
    """
    _inherit = 'mrp.production'
    
    # ---------------------------------------------------------------------
    # Utility:
    # ---------------------------------------------------------------------
    def get_sort_code(self, sequence_mode, default_code):
        """ Return sort code for line order
        """
        if sequence_mode == 'parent':
            return default_code[:3]    
        elif sequence_mode == 'frame':
            return '%s...%s' % (
                default_code[:3],
                default_code[6:8],
                )                
        else:
            raise osv.except_osv(
                _('Sequence error'), 
                _('Unmanage sequence: %s' % sequence_mode),
                )        

    # ------------------
    # Override function:
    # ------------------
    def force_production_sequence(self, cr, uid, ids, context=None):
        """ Force new order on sale order line depend on parent code
            and default code
        """
        # Pool used:
        line_pool = self.pool.get('sale.order.line')        
        sequence_pool = self.pool.get('mrp.production.sequence')        
        
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Reload parent element for include new (TODO necessary?):
        self.load_parent_list(cr, uid, ids, context=context)

        # Read parent order:
        master_order = {}
        order = []
        sequence_mode = mrp_proxy.sequence_mode
        
        for parent in mrp_proxy.sequence_ids:
            order.append(parent.name) # keep in order (unlike dict)
            master_order[parent.name] = []
        
        for line in mrp_proxy.order_line_ids:
            default_code = line.product_id.default_code            
            parent_code = self.get_sort_code(sequence_mode, default_code)
            master_order[parent_code].append((line.product_id.default_code, line.id))
                        
        i = 0
        # Loop on forced order parent:
        for parent in order:
            sol_ids = master_order[parent]
            
            # Loop on code order child:
            for default_code, item_id in sorted(sol_ids): 
                i += 1
                line_pool.write(cr, uid, item_id, {
                    'mrp_sequence': i,
                    }, context=context)

        # ---------------------------------------------------------------------
        # Reset sequence:
        # ---------------------------------------------------------------------
        # XXX Put in a button?
        #for sequence in mrp_proxy.sequence_ids:
        #    sequence_pool.write(cr, uid, [sequence.id], {
        #        'sequence': 10,
        #        }, context=context)
        return True

    # ----------------
    # Button function:
    # ----------------
    def load_parent_list(self, cr, uid, ids, context=None):
        """ Load list of parent for se the order
        """
        seq_pool = self.pool.get('mrp.production.sequence')

        # Load current parent:
        parents = {}  # Master total database
        old_parents = {}  # Old to check when remove
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        max_sequence = 0
        sequence_mode = mrp_proxy.sequence_mode
        
        # --------------------------------------------------------------------------------------------------------------
        # Read current sequence parent (so old parents):
        # --------------------------------------------------------------------------------------------------------------
        for seq in mrp_proxy.sequence_ids:
            parents[seq.name] = 0
            old_parents[seq.name] = seq.id
            if seq.sequence < max_sequence:
                max_sequence = seq.sequence
        
        # --------------------------------------------------------------------------------------------------------------
        # Append parent with line (and totals in new parents):
        # --------------------------------------------------------------------------------------------------------------
        for line in mrp_proxy.order_line_ids:
            default_code = line.product_id.default_code            
            parent = self.get_sort_code(sequence_mode, default_code)
            if parent not in parents:
                parents[parent] = [0.0, 0.0]  # Total, Done

            parents[parent][0] += (line.product_uom_qty - line.mx_assigned_qty) or 1
            parents[parent][1] += line.product_uom_maked_sync_qty  # done

        i = 0
        for parent in sorted(parents):
            i += 1
            if parent in old_parents:
                if parents[parent][0]:  # If not total delete block:
                    seq_pool.unlink(cr, uid, old_parents[parent], context=context)
                else:  # Update with totals:
                    seq_pool.write(cr, uid, old_parents[parent], {
                        #'sequence': i,
                        #'name': parent,      
                        #'mrp_id': ids[0],          
                        'total': parents[parent][0],
                        'done': parents[parent][1],
                        'remain': parents[parent][0] - parents[parent][1],
                        }, context=context)
            else:
                # Create new parent:
                seq_pool.create(cr, uid, {
                    'sequence': max_sequence + i, # in order but append to org.
                    'name': parent,      
                    'mrp_id': ids[0],          
                    'total': parents[parent][0],
                    'done': parents[parent][1],
                    'remain': parents[parent][0] - parents[parent][1],
                }, context=context)
        return True

    def force_order_sequence(self, cr, uid, ids, context=None):
        """ Force order line sequence depend on this list of parent
        """
        # Force overridden function sequence:
        self.force_production_sequence(cr, uid, ids, context=context)
        return True
        
    _columns = {
        'sequence_mode': fields.selection([
            ('parent', 'Parent mode (XXX..........)'),
            ('frame', 'Parent-Frame mode (XXX...XX.....)'),
            ], 'Order mode', required=True),
        'sequence_ids': fields.one2many(
            'mrp.production.sequence', 'mrp_id', 'Parent order', 
            help='Set order for parent code and after confirm with button for '
                'all sale order line'), 
        }
        
    _defaults = {
        'sequence_mode': lambda *x: 'parent',                   
        }