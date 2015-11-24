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
    ''' Add extra field for sync production order
    '''
    _inherit = 'mrp.production'
    
    # -----------------
    # Utility function:
    # -----------------
    def _get_fake_order(self, cr, uid, line, context=None):
        ''' Create or search fake master order for that family
            TODO: one for year?
        '''
        bom_pool = self.pool.get('mrp.bom')

        family_id = line.product_id.family_id.id
        fake_ids = self.search(cr, uid, [
            ('family_id', '=', family_id),
            ('fake_order', '=', True),
            ], context=context)
        if fake_ids:
            return face_ids[0]
        
        # get_bom_id for family:
        bom_ids = bom_pool.searc(cr, uid, [
            ('product_tmpl_id', '=', family_id),
            ('has_lavoration', '=', True),
            ], context=context)
        if not bom_ids:
            _logger.error('No bom found for family selected')
            # TODO create one?
                
        # Create a fake mrp order:
        return self.create(cr, uid, {
            'fake_order': True,
            'product_id': line.product_id.id,
            'product_uom': line.product_id.uom_id,
            'bom_id': bom_ids[0],            
            # TODO enought fields?
            }, context=context)
    
    
    def _add_to_fake_production(self, cr, uid, order_ids, context=None):
        ''' Function that create fake production order and add all order_ids
            line passed (every line go in mrp order with right family code
        '''
        line_pool = self.pool.get('sale.order.line')
        buffer_mrp = {}
        for line in line_pool.browse(cr, uid, order_ids, context=context):
            family_id = line.product_id.family_id.id
            # TODO manager error for no family line
            # TODO check if it is a production product <<<<<< IMPORTANT
            if family_id not in buffer_mrp:                    
                buffer_mrp[family_id] = self._get_family_fake_order(
                    cr, uid, line, context=context)
            
            # Add line to order:
            line_pool.write(cr, uid, [line.id], {
                'mrp_id': buffer_mrp[family_id] # TODO correct fields?
                }, context=context)
                    
        # Update totals and order in all bufferd order managed here:
        # TODO    
        return True

    _columns = {
        'fake_order': fields.boolean('Fake order', 
            help='Fake production order that is used for put all produced'
                'lines that where maked or delivered before installation'
                'of production module'),
        }
        

class SaleOrder(orm.Model):
    ''' Add extra field for sync order
    '''
    _inherit = 'sale.order'
        
    # -----------------
    # Scheduled action:
    # -----------------
    def scheduled_import_order_and_sync(self, cr, uid, 
            csv_file='~/etl/ocdetoerp1.csv', separator=';', header=0, 
            verbose=100, context=None):
        ''' Sync current sale.order improted from accounting with same sale
            order of an old procedure for manage delivery and transport
            (this order has note and B extra information
            # Note: All file import information now is not managed, use 
                    importation header and lines (after import directly form 
                    here for by pass old procedure                    
            3 cases:
                1. order in account only > error
                2. order in both account and real > sync line
                3. order only in real > all order product
            
            Note: All line will be marked at the end of procedure!    
        '''
        # Pool used:
        account_pool = self.pool.get('statistic.header')
        mrp_pool = self.pool.get('mrp.production')
        sol_pool = self.pool.get('sale.order.line')
        
        # Fake database of production:
        fake_mrp = {}
        
        # ----------------------------------------------
        # Import all csv file in temporary order object:
        # ----------------------------------------------
        # Force scheduled importation from here # TODO deactivate other
        # Load account order:
        account_pool.scheduled_import_order(
            cr, uid, csv_file, separator, header, verbose, context=context)

        # TODO Sync new order?

        # -------------------------------------------
        # Load the two order block, account and odoo:
        # -------------------------------------------
        # > Load odoo order:
        odoo = {} # dict for manage odoo order
        odoo_ids = self.search(cr, uid, [
            ('accounting_order', '=', True), # Order for production
            ], context=context)
        for item in self.browse(
                cr, uid, odoo_ids, context=context):    
            odoo[item.name] = item # order proxy

        # > Load account order:        
        account_ids = account_pool.search(cr, uid, [], context=context)
        
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        #                         Header analysis:
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # Loop on all account order first:
        for account in account_pool.browse(
                cr, uid, account_ids, context=context):
            # Get right format name
            name = 'MX-%s/%s' % (
                account.name, # number     
                account.date[-4:], # year
                )                
            
            # -----------------------------------------------------------------
            #       Case 1: Account - ODOO  >> error no sync:
            # -----------------------------------------------------------------
            if name not in odoo: 
                _logger.error(
                    'Order accounting not in odoo, sync! [%s]' % (
                        code))
                continue
                
            # -----------------------------------------------------------------
            #       Case 2: Account AND ODOO  >> need line sync:
            #       Case 3: ODOO - Account  >> all delivered:
            # -----------------------------------------------------------------

            # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            #                     Line analysis:
            # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            # Read odoo lines archived with key = code, deadline:
            master_line_db = {}
            
            # 1. Loop on ODOO order line:
            for odoo_line in odoo.order_line:
            
                # Create a Key    
                if (not odoo_line.product_id.default_code) or (
                        not odoo_line.deadline):
                    _logger.error('ODOO order without code/deadline: %s' % (
                        odoo_line.order_id.name))
                    continue                
                key = (
                    odoo_line.product_id.default_code, 
                    odoo_line.deadline,
                    )
                    
                # Save master line database (populated with ODOO lines):
                master_line_db[key] = [
                    # ODOO order line:                    
                    odoo_line, # 0. Browse obj for odoo order line:
                    
                    # Account order line:                    
                    0.0, # 1. To make (remain maybe not all ordered)                    
                    0.0, # 2. Maked
                    ]
            
            # 2. Loop on Account order line:
            for line in account.line_ids:

                # ------------------------
                # Subcase 0 (description):
                # ------------------------
                if line.type == 'd': # else 'a' for article!
                    pass # TODO Save description for order purposes
                    continue
                
                # Create key:    
                if not line.code or not line.deadline:
                    _logger.error('Account order without code/deadline: %s' % (
                        line.order_id.name))
                    continue
                key = (line.code, line.deadline)

                # -----------------------------------
                # Subcase 1: Account - ODOO >> Error:
                # -----------------------------------
                if key not in master_line_db: 
                    _logger.error(
                        'Order line accounting not in oerp order: %s' % (
                            line.code))
                    # TODO import? better not!
                    continue
                     
                # ----------------------------------------------------
                # Subcase 2: Account AND ODOO >> try a sync operation:
                # Subcase 3: ODOO - Account (all delivered):
                # ----------------------------------------------------
                # Update values in master DB (will be check after)
                if line.type == 'b': # maked quantity
                    master_line_db[key][2] += quantity # append value (multi)
                else: # not maked:
                    master_line_db[key][1] += quantity # append value

                        
            # 3. Update database ODOO status:
            for (odoo_line, acc_remain, acc_maked) in master_line_db:
                # Get element from browse odoo line:
                item_id = odoo_line.id
                mrp_id = odoo_line.mrp_id.id
                family_id = odoo_line.product_id.family_id.id
                order = odoo_line.product_uom_qty
                temp = odoo_line.product_uom_maked_qty
                maked = odoo_line.product_uom_maked_sync_qty

                # (Mode 1: not present):
                
                if any([acc_remain, acc_maked]): # Mode 2 Account AND ODOO
                    # Maked/Not maked and delivered/not delivered:                    
                    delivered = order - acc_remain - acc_maked
                    acc_maked += delivered # (maked and delivered = maked)
                    
                    data = {
                        'product_uom_maked_qty': 0, # reset
                        'product_uom_maked_sync_qty': acc_maked,
                        'product_uom_delivered_qty': delivered,
                        #'sync_state': 'closed', # all close TODO
                        }

                    # There's some production create in not pres.   
                    if acc_maked and not mrp_id:
                        # Create or get fake production:
                        if family_id not in fake_mrp:
                            fake_mrp[family_id] = mrp_pool._get_fake_order(
                                cr, uid, odoo_line, context=context)                           
                        
                    sol_pool.write(cr, uid, item_id, data, context=context)
                else: # Mode 3: all delivered: odoo - account                    
                    if not mrp_id: # so all produced
                        # Create or get fake production:
                        if family_id not in fake_mrp:
                            fake_mrp[family_id] = mrp_pool._get_fake_order(
                                cr, uid, odoo_line, context=context)                           
                    
                    data = {
                        'product_uom_maked_qty': 0, # reset
                        'product_uom_maked_sync_qty': order,
                        'product_uom_delivered_qty': order, # all
                        #'sync_state': 'closed', # all close TODO
                        }
                    sol_pool.write(cr, uid, item_id, data, context=context)
                    continue

            # TODO manage production fake inline!
        return True
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

