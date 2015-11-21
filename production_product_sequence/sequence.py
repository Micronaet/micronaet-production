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
    
    # Button function:
    def load_parent_list(self, cr, uid, ids, context=None):
        ''' Load list of parent for se the order
        '''
        seq_pool = self.pool.get('mrp.production.sequence')
        parents = []
        for line in self.browse(cr, uid, ids, context=context).order_line_ids:
            parent = line.product_id.default_code[:3]
            if parent not in parents:
                parents.append(parent)
        
        i = 0
        parents.sort()
        for parent in parents:
            i += 1
            seq_pool.create(cr, uid, {
                'sequence': i,
                'name': parent,                
                }, context=context)            
        return True

    def force_order_sequence(self, cr, uid, ids, context=None):
        ''' Force order line sequence depend on this list of parent
        '''
        return True
        
    # ----------------
    # Field functions:
    # ----------------
    def _get_total_order_lines(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        total = {}
        parent_len = 3 # TODO 
        
        line_pool = self.pool.get('sale.order.line')
        line_ids = line_pool.search(cr, uid, [
            ('mrp_id', '=', item.mrp_id.id),
            ], context=context)
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            parent = line.product_id.default_code[:parent_len]
            if parent not in total:    
                total[parent] = 1
            else:    
                total[parent] = +1
                
        for item in self.browse(cr, uid, ids, context=context):
            parent = item.product_id.default_code[:parent_len]
            res[item.id] = total.get(parent, 0)            
        return res 
        
    _columns = {
        'sequence': fields.integer('Sequence'), 
        'name': fields.char(
            'Parent', size=15, required=True), 
        'mrp_id': fields.many2one('mrp.production', 'MRP order'),
        'total': fields.function(
            _get_total_order_lines, method=True, 
            type='integer', string='# line', 
            store=False),                         
        }
    _defaults = {
        'sequence': lambda *x: 1000, # New line go bottom
        }

class MrpProduction(orm.Model):
    ''' Add extra field to mrp order
    '''
    _inherit = 'mrp.production'
    
    _columns = {
        'sequence_ids': fields.one2many(
            'mrp.production.sequence', 'mrp_id', 'Parent order', 
            help='Set order for parent code and after confirm with button for '
                'all sale order line'), 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
