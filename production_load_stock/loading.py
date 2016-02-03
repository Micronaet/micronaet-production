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


class StockMove(orm.Model):
    """ Model name: Sale order for production
    """    
    _inherit = 'stock.move'

    _columns = {
        'production_sol_id': fields.many2one(
            'sale.order.line', 'Sale line linked', ondelete='cascade',
            help='Line linked for load / unload for production'),
        'production_load_type': fields.selection([
            ('cl', 'Product load'),
            ('sl', 'Material unload'),
            ], 'Production load type'),
        }     

    _defaults = {        
        # Default value:
        'production_load_type': lambda *x: 'cl',    
        }

class SaleOrder(orm.Model):
    """ Model name: Sale order for production
    """    
    _inherit = 'sale.order.line'

    # Utility:
    def _search_bom_for_product(self, cr, uid, product_id, context=None):
        ''' Search reference BOM for product (now is the one that was imported
        ''' 
        bom_pool = self.pool.get('mrp.bom')
        bom_ids = bom_pool.search(cr, uid, [
            ('product_id', '=', product_id),
            ('sql_import', '=', True),
            ], context=context)
        if not bom_ids:
            _logger.error('No BOM found for product passed')
            return False
        
        return bom_pool.browse(cr, uid, bom_ids, context=context)[0]
    
    def _create_stock_move_for_production(self, cr, uid, line, bom, 
            context=None):
        ''' Generate dict for stock production move
        '''    
        pass
        # TODO
        return {}
        
    def _recreate_production_sol_move(self, cr, uid, sol_ids, 
            context=None):    
        ''' Generic function used for create / update stock move,
            CL and SL, used from create and write method            
        '''    
        assert len(sol_ids), 'Only one row a time!'
        
        # Pool used:
        move_pool = self.pool.get('stock.move')

        # Parameter for location:
        # TODO 
                
        line_proxy = self.browse(cr, uid, sol_ids, context=context)[0]

        # get product BOM for materials:
        bom_proxy = self._search_bom_for_product(cr, uid, 
            line_proxy.product_id.id, context=context)

        maked_qty = line_proxy.product_uom_maked_sync_qty or 0.0

        # Unlink all stock move (always):
        move_ids = move_pool.search(cr, uid, [
            ('production_sol_id', '=', line_proxy.id)], context=context)
        if move_ids:
            move_pool.unlink(cr, uid, move_ids, context=context)

        if not maked_qty:   
            return True
        
        # Create SL move:
        if bom_proxy:
            # Unload materials:
            for bom in bom_proxy.bom_line_ids:
                unload_qty = bom.product_qty * maked_qty
                continue
                move_pool.create(cr, uid, {
                    'production_sol_id': line_proxy.id,
                    'production_load_type': 'sl',
                    'product_id': bom.product_id.id,
                    'product_qty': unload_qty, 
                    'product_uom': line.product_id.uom_id.id,
                    #'product_uom_qty',
                    #'product_uos',
                    #'product_uos_qty',
                    'state': 'done', # confirmed, available
                    'date_expected': datetime.now().strftime(
                        DEFAULT_SERVER_DATE_FORMAT),
                    'origin': line_proxy.mrp_id.name,
                    'display_name': 'SL: %s' % line_proxy.product_id.name,
                    'name': 'SL: %s' % line_proxy.product_id.name,
                    'location_dest_id': 0, # TODO
                    'location_id': 0, # TODO
                    #'warehouse_id',
                    #'picking_type_id',

                    #'weight'
                    #'weight_net',
                    #'picking_id'
                    #'group_id'
                    #'production_id'
                    #'product_packaging'                    
                    #'company_id'
                    #'date':
                    #date_expexted'
                    #'note':,
                    #'partner_id':
                    #'price_unit',
                    #'priority',.                    
                    }, context=context)
        
        # Load end product:    
        # TODO        
        #move_pool.create(cr, uid, {
        #    'production_sol_id': line_proxy.id,
        #    'production_load_type': 'cl',
        #    'product_uom_qty': maked_qty,
        #    }, context=context)
        return True
        
    def write(self, cr, uid, ids, vals, context=None):
        """ Update record(s) comes in {ids}, with new value comes as {vals}
            return True on success, False otherwise
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of record ids to be update
            @param vals: dict of new values to be set
            @param context: context arguments, like lang, time zone
            
            @return: True on success, False otherwise
        """
        import pdb; pdb.set_trace()
        res = super(SaleOrder, self).write(
            cr, uid, ids, vals, context=context)

        # Check maked qty for create production moves:
        if 'product_uom_maked_sync_qty' in vals:
            self._recreate_production_sol_move(cr, uid, ids, 
                context=context)
        return res
    
    def create(self, cr, uid, vals, context=None):
        """ Create a new record for a model ClassName
            @param cr: cursor to database
            @param uid: id of current user
            @param vals: provides a data for new record
            @param context: context arguments, like lang, time zone
            
            @return: returns a id of new record
        """    
        import pdb; pdb.set_trace()
        res_id = super(SaleOrder, self).create(
            cr, uid, vals, context=context)
        
        # Check maked qty for create production moves:
        self._recreate_production_sol_move(cr, uid, ids, 
            context=context)
            
        return res_id
    
    _columns = {
        'move_production_ids': fields.one2many(
            'stock.move', 'production_sol_id', 
            'Production moves'), 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
