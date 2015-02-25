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

class SaleOrderLine(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''
    
    _inherit = 'sale.order.line'

    # -------------
    # Button event:
    # -------------
    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {
            'mrp_id': False, }, context=context)
            
    _columns = {
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        }

class MrpProduction(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''
    
    _inherit = 'mrp.production'
    
    _columns = {
        'extra_qty': fields.float('Extra q.', digits=(16, 2)), 
        # TODO there's extra bool?
        'order_line_ids': fields.one2many(
            'sale.order.line', 'mrp_id', 'Order line'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
