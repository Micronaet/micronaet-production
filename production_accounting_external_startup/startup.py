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
                1. order in fake only > error
                2. order in both fake and real > sync line
                3. order only in real > all order product
        '''
        # Pool used:
        fake_pool = self.pool.get('statistic.header')
        
        # ----------------------------------------------
        # Import all csv file in temporary order object:
        # ----------------------------------------------
        # Force scheduled importation from here 
        # TODO deactivate other scheduler activity
        
        # Load fake order:
        fake_pool.scheduled_import_order(
            cr, uid, ids, 
            csv_file, separator, header, verbose, 
            context=context)
        
        # ----------------------------------------
        # Load the two order block, fake and real:
        # ----------------------------------------
        # > Load real order:    
        real = {} # dict for manage key and keep trace of imported
        real_ids = self.search(cr, uid, [
            ('accounting_order', '=', True),
            ], context=context)
            
        # Save records for sync operation:
        for item in self.browse(
                cr, uid, real_ids, context=context):    
            real[item.name] = item

        # > Load fake order:        
        fake_ids = fake_pool.search(cr, uid, [], context=context)
        fake_proxy = fake_pool.browse(cr, uid, fake_ids, context=context)
        
        # Loop on all fake order first:
        for fake in fake_proxy:
            # Get right format (key)
            name = 'MX-%s/%s' % (
                fake.name, # number     
                fake.date[-4:], # year
                )                
            
            # Case 1 (error):    
            if name not in real: 
                _logger.error(
                    'Order from accounting not present in real order: %s' % (
                        code))
                continue
                
            # Case 2 (need line sync):
            
            # Read real lines:
            real_lines = {}
            for real_line in real.order_line:
                real_lines[real_line.product_id.default_code] = real_line
                
            # Loop on fake lines:    
            for line in fake.line_ids:
                if line.type == 'd':
                    # TODO Save description
                    pass
                else: # a(tricle)
                    # Subcase 1 (error):
                    if line.code not in real_lines:
                        _logger.error(
                            'Order line accounting not in oerp order: %s' % (
                                line.code))
                        continue        
                    # Subcase 2 (try a sync operation)
                    # TODO test totals and decide 3 cases
            
            # Case 3 (need production for real line not in fake):
            for item in real_lines:
                pass # TODO
                       
                        
                                                
            
            
            
                        
                    
                
        #    3 Case: Present fake obj, presente both, present real obj
        
        # 3. Sync line in middle case
        # > Create fake production order and put there all line 
        
        return True
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
