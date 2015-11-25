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
    _name = 'mrp.production.sequence'
    _description = 'MRP production sequence'
    _order = 'sequence, name'    
    
    # ----------------
    # Field functions:
    # ----------------
    _columns = {
        'sequence': fields.integer('Sequence'), 
        'name': fields.char(
            'Parent', size=15, required=True), 
        'mrp_id': fields.many2one('mrp.production', 'MRP order'),
        'total': fields.integer('# line'),
        }
    _defaults = {
        'sequence': lambda *x: 1000, # New line go bottom
        }

class MrpProduction(orm.Model):
    ''' Add extra field to mrp order
    '''
    _inherit = 'mrp.production'
    
    # ------------------
    # Override function:
    # ------------------
    def force_production_sequence(self, cr, uid, ids, context=None):
        ''' Force new order on sale order line depend on parent code
            and default code
        '''
        # Pool used:
        line_pool = self.pool.get('sale.order.line')        
        mrp_proxy = self.browse(cr, uid, ids, context=context)

        # Reload parent element for include new (TODO necessary?):
        self.load_parent_list(cr, uid, ids, context=context)
        
        # Read parent order:
        master_order = {}
        for parent in mrp_proxy.sequence_ids:
            master_order[parent] = []
        
        for line in mrp_proxy.order_line_ids:
            master_order.append(
                (line.product_id.default_code, line.id))
                        
        i = 0
        for parent, sol_ids in master_order: #sorted(order):
            for default_code, item_id in sorted(sol_ids): 
                i += 1
                line_pool.write(cr, uid, item_id, {
                    'mrp_sequence': i,
                    }, context=context)
        return True

    # ----------------
    # Button function:
    # ----------------
    def load_parent_list(self, cr, uid, ids, context=None):
        ''' Load list of parent for se the order
        '''
        seq_pool = self.pool.get('mrp.production.sequence')

        # Load current parent:
        parents = {}
        old_parents = {}
        mrp_proxy = self.browse(cr, uid, ids, context=context)
        max_sequence = 0
        for seq in mrp_proxy.sequence_ids:
            parents[seq.name] = 0
            old_parents[seq.name] = seq.id
            if seq.sequence < max_sequence:
                max_sequence = seq.sequence
        
        # Append parent with line:
        for line in mrp_proxy.order_line_ids:
            parent = line.product_id.default_code[:3]
            if parent not in parents:
                parents[parent] = line.product_uom_qty or 1
            else:
                parents[parent] += line.product_uom_qty or 1

        i = 0
        for parent in sorted(parents):
            i += 1
            if parent in old_parents:
                # Delete in no elements:
                if parents[parent] == 0:
                    seq_pool.unlink(cr, uid, old_parents[parent], 
                        context=context)
                else:        
                    seq_pool.write(cr, uid, old_parents[parent], {
                        #'sequence': i,
                        #'name': parent,      
                        #'mrp_id': ids[0],          
                        'total': parents[parent]
                        }, context=context)            
            else:
                seq_pool.create(cr, uid, {
                    'sequence': max_sequence + i, # in order but append to org.
                    'name': parent,      
                    'mrp_id': ids[0],          
                    'total': parents[parent]
                    }, context=context)            
        return True

    def force_order_sequence(self, cr, uid, ids, context=None):
        ''' Force order line sequence depend on this list of parent
        '''
        # Force overrided function sequence:
        self.force_production_sequence(cr, uid, ids, context=context)
        return True
        
    _columns = {
        'sequence_ids': fields.one2many(
            'mrp.production.sequence', 'mrp_id', 'Parent order', 
            help='Set order for parent code and after confirm with button for '
                'all sale order line'), 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
