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
    """ Model name: Sale Order
    """
    
    _inherit = 'sale.order'    

    # TODO update go_in_production
    # -------------------------------------------------------------------------
    # Override: button force close:
    # -------------------------------------------------------------------------
    def action_cancel(self, cr, uid, ids, context=None):
        ''' Override method for check order to unlink
        '''
        # ---------------------------------------------------------------------
        # Unlink production before 
        # ---------------------------------------------------------------------
        order_proxy = self.browse(cr, uid, ids, context=context)
        html_log = ''        
        line_ids = []
        for line in order_proxy.order_line:
            if not line.mrp_id: # not production_mrp_id
                continue # Manage only linked to production line
            
            if line.product_uom_maked_sync_qty > 0:
                raise osv.except_osv(
                    _('Cannot cancel'), 
                    _('''This order has production with (B)locked qty, close
                        residual instead of canceling'''),
                    )
            line_ids.append(line.id)
            html_log += '''
                <tr>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                </tr>\n''' % (
                    line.product_id.default_code,
                    line.product_uom_qty,
                    line.product_uom_maked_sync_qty,
                    line.delivered_qty,
                    line.mrp_id.name or '',
                    )
        
        if line_ids:
            # Disconnect manually from MRP:
            self.pool.get('sale.order.line').write(cr, uid, line_ids, {
                'mrp_id': False,
                }, context=context)
                
            message = _('''
                <p>UNLINKED MRP lines to produce:</p>
                <table class='oe_list_content'>
                    <tr>
                        <td class='oe_list_field_cell'>Prod.</td>
                        <td class='oe_list_field_cell'>Order</td>
                        <td class='oe_list_field_cell'>Done</td>
                        <td class='oe_list_field_cell'>Delivered</td>
                        <td class='oe_list_field_cell'>MRP</td>
                    </tr>
                    %s
                </table>
                ''') % html_log
                                
            # Send message
            self.message_post(cr, uid, ids, body=message, context=context)
            
        return super(SaleOrder, self).action_cancel(
            cr, uid, ids, context=context)

        
    def force_close_residual_order(self, cr, uid, ids, context=None):
        ''' Force order and line closed:
        '''
        # Run normal button procedure:
        super(SaleOrder, self).force_close_residual_order(
            cr, uid, ids, context=context)
         
        _logger.warning('Unlink no more production line')
        
        # Pool used:
        sol_pool = self.pool.get('sale.order.line')
        order_proxy = self.browse(cr, uid, ids, context=context)

        # --------------------------------------
        # Read data for log and get information:
        # --------------------------------------
        html_log = ''
        unlink_no_production_ids = []
        for line in order_proxy.order_line:
            if not line.mrp_id: # not production_mrp_id                
                continue # Nothing to do: no MRP
            
            if line.product_uom_qty - line.product_uom_maked_sync_qty <= 0:
                continue # All done remain in MRP order
                
            if 'UNLINK' in line.mrp_id.name:
                if line.product_uom_maked_sync_qty <= 0: # no production remove
                    unlink_no_production_ids.append(line.id)
                    html_log += _('''
                        <tr>
                            <td>%s (MRP UNLINKED: %s)</td>
                            <td>%s</td><td>%s</td><td>%s</td>
                        </tr>\n''') % (
                            line.product_id.default_code,
                            line.mrp_id.name,
                            line.product_uom_qty,
                            line.product_uom_maked_sync_qty,
                            line.delivered_qty,
                            )
                continue

            # Normal production not B(locked) will be deleted:
            if line.product_uom_maked_sync_qty <= 0: # no production remove
                unlink_no_production_ids.append(line.id)
                html_log += _('''
                    <tr>
                        <td>%s (EX MRP: %s)</td>
                        <td>%s</td><td>%s</td><td>%s</td>
                    </tr>\n''') % (
                        line.product_id.default_code,
                        line.mrp_id.name,
                        line.product_uom_qty,
                        line.product_uom_maked_sync_qty,
                        line.delivered_qty,
                        )
                continue
                        
            # Remain has production linked so UNLINK:
            context['production_order_id'] = line.mrp_id.id
            sol_pool.free_line(cr, uid, [line.id], context=context)
            
            # Log unlinked:
            html_log += '''
                <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n''' % (
                    line.product_id.default_code,
                    line.product_uom_qty,
                    line.product_uom_maked_sync_qty,
                    line.delivered_qty,
                    )
        if 'production_order_id' in context:
            del(context['production_order_id'])
        
        # Unlink unlinked production with no B(locked)
        if unlink_no_production_ids:
            _logger.warning('Disconnect unlinked production without B # %s' % (
                len(unlink_no_production_ids), ))
            sol_pool.write(cr, uid, unlink_no_production_ids, {
                'mrp_id': False,
                }, context=context)
                
        # --------------------------
        # Log message for operation:
        # --------------------------
        if html_log:
            message = _('''
                <p>UNLINKED Remain line to produce:</p>
                <table class='oe_list_content'>
                    <tr>
                        <td class='oe_list_field_cell'>Prod.</td>
                        <td class='oe_list_field_cell'>Order</td>
                        <td class='oe_list_field_cell'>Done</td>
                        <td class='oe_list_field_cell'>Delivered</td>
                    </tr>
                    %s
                </table>
                ''') % html_log
                
            # Send message
            self.message_post(cr, uid, ids, body=message, context=context)
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
