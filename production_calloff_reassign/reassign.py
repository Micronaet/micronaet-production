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


class SaleOrder(orm.Model):
    """ Model name: Sale order
    """
    
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def calloff_get_usable(self, cr, uid, ids, context=None):
        ''' Get reusable product from call off order
        '''
        import pdb; pdb.set_trace()
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # ---------------------------------------------------------------------
        # Calloff availability:
        # ---------------------------------------------------------------------
        calloff_product = {} 
        for line in current_proxy.calloff_id.order_line:
            product = line.product_id
            b_qty = line.product_uom_maked_sync_qty
            delivery_qty = line.product_uom_delivered_qty
            if b_qty <= delivery_qty:
                continue
            record = [
                b_qty - delivery_qty, # available
                0.0, # used
                line.id, # line ref.
                ]
                
            if product.id in calloff_product:
                calloff_product[product.id] = [record]
            else:
                calloff_product[product.id].append(record)

        # ---------------------------------------------------------------------
        # Calculate assign qty:
        # ---------------------------------------------------------------------
        assign_product = [] # product needed in this order
        if calloff_product:
            for line in current_proxy.order_line:
                product = line.product_id
                if product.id not in calloff_product:
                    continue
                
                # Readability:    
                oc_qty = line.product_uom_qty
                b_qty = line.product_uom_maked_sync_qty
                delivery_qty = line.product_uom_delivered_qty
                
                if b_qty >= delivery_qty:
                    need_qty = oc_qty - b_qty
                else:
                    need_qty = oc_qty - delivery_qty

                if need_qty <= 0.0: # no need to assign
                    continue
                    
                assign_qty = 0.0
                for record in calloff_product[product.id]:
                    this_qty = record[0] - record[1] # avail - used                
                    if this_qty <= 0.0:
                        continue
                        
                    if need_qty <= this_qty: # use remain needed
                        assign_qty += need_qty
                        record[1] += need_qty
                        break
                        
                    else: # use all this block
                        assign_qty += this_qty
                        record[1] += this_qty
                        need_qty -= this_qty
                        
                # TODO loop for get qty:
                assign_product.append((
                    line,
                    assign_qty, # only usable qty
                    ))
        return assign_product, calloff_product

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def calloff_info(self, cr, uid, ids, context=None):
        ''' Reassign call off quantity produced
        '''
        assign_product, calloff_product = self.calloff_get_usable(
            cr, uid, ids, context=context)
        
        res = ''
        for line, assign_qty in assign_product:
            res += '<tr><td>%s</td><td>%s</td></tr>' % (
                line.product_id.default_code or '',
                assign_qty,
                )  
        res = _('''
            <style>
                .table_bf {
                     border: 1px solid black;
                     padding: 3px;
                     width: 400px;
                     }
                .table_bf td {
                     border: 1px solid black;
                     padding: 3px;
                     text-align: center;
                     }
                .table_bf th {
                     border: 1px solid black;
                     padding: 3px;
                     text-align: center;
                     background-color: grey;
                     color: white;
                     }
            </style>
            <table class='table_bf'>
                <tr class='table_bf'>
                    <th>Product</th>
                    <th>Q. Used</th>
                </tr>%s
            </table>
            ''') % res
            
        return self.write(cr, uid, ids, {
            'calloff_pre_assign': res,
            }, context=context)        
    
    def calloff_reassign_here(self, cr, uid, ids, context=None):
        ''' Reassign call off quantity produced
        '''
        assign_product, calloff_product = self.calloff_get_usable(
            cr, uid, ids, context=context)
        # TODO
        # Remove from calloff:        

        # Assign product to the order:        
        
        return True
        
    _columns = {
        'calloff': fields.boolean('Call off'),
        'calloff_id': fields.many2one(
            'sale.order', 'Call off order', 
            help='Linked call off order'),
        'calloff_pre_assign': fields.text('Calloff pre assign', readonly=True),
        'calloff_log': fields.text('Calloff log', readonly=True),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
