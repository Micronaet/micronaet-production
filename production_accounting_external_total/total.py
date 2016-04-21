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

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    
    _inherit = 'mrp.production'

    def _get_total_line(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
    
        self.cr.execute('''
            SELECT 
                 mrp_id, 
                 sum(product_uom_qty) as todo, 
                 sum(product_uom_maked_sync_qty) as done, 
                 sum(product_uom_qty) = sum(product_uom_maked_sync_qty) as ok
             FROM 
                 sale_order_line 
             GROUP BY 
                 mrp_id 
             HAVING 
                 mrp_id in (%s);
             ''' % (','.join(map(lambda x: str(x), ids)))
             )
        for item in self.cr.fetchall()
            res[item[0]] = {}
            res[item[0]]['total_line_todo'] = item[1]
            res[item[0]]['total_line_done'] = item[2]
            res[item[0]]['total_line_ok'] = item[3]
            

                
        for mrp in self.browse(cr, uid, ids, context=context):
            import pdb; pdb.set_trace()
            res[mrp.id] = {}
            res[mrp.id]['total_line_todo'] = 0.0
            res[mrp.id]['total_line_done'] = 0.0
            for line in mrp.order_line_ids:
                res[mrp.id]['total_line_todo'] += line.product_uom_qty
                res[mrp.id]['total_line_done'] += line.product_uom_maked_sync_qty
            
            if res[mrp.id]['total_line_todo'] == res[
                    mrp.id]['total_line_done']:
                res[mrp.id]['total_line_ok'] = True
            else:    
                res[mrp.id]['total_line_ok'] = False
        return res        
    
    _columns = {
        'total_line_todo': fields.function(
            _get_total_line, method=True, 
            type='float', string='Todo', 
            store=False), 
        'total_line_done': fields.function(
            _get_total_line, method=True, 
            type='float', string='Todo', 
            store=False), 
        'total_line_ok': fields.function(
            _get_total_line, method=True, 
            type='boolean', string='Completed', 
            store=False),
                        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
