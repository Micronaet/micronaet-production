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
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleOrder(orm.Model):
    ''' Reload element from accounting
    '''
    _inherit = 'sale.order'
    
    # -------------
    # Button event:
    # -------------
    def open_csv_order(self, cr, uid, ids, context=None):
        ''' Search current order in CSV file
        '''
        assert len(ids) == 1, _('Procedure must called only for one record')
        
        # Current format: XX-00001/2015
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        name = order_proxy.name.split('-')[-1].split('/')[0]
        
        header_pool = self.pool.get('statistic.header')                
        header_ids = header_pool.search(cr, uid, [
            ('name', '=', name)], context=context)
        if not header_ids:    
             raise osv.except_osv(
                 'Error', 
                 'No header for that order found (maybe all delivered?)')
                 
        return {
            'name': 'Original order',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'domain': [('id', '=', header_ids[0])],
            #'view_id': view_id, ref_id
            'context': context,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def reload_production(self, cr, uid, ids, context=None):
        ''' Reload from accounting
        '''
        assert len(ids) == 1, 'Need to be called with one record passed!' 

        # Pool used:
        cron_pool = self.pool.get('ir.cron')
        sql_pool = self.pool.get('micronaet.accounting')
        line_pool = self.pool.get('sale.order.line')

        # Proxy used:
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        cron_ids = cron_pool.search(cr, uid, [
            ('function', '=', 'scheduled_import_order_and_sync')], context=context)        
        if not cron_ids:
            _logger.error(
                'Procedure scheduled "scheduled_import_order_and_sync" '
                'not found')
            return False
        
        cron_proxy = cron_pool.browse(cr, uid, cron_ids, context=context)[0]
        parameters = eval(cron_proxy.args)
        return self.scheduled_import_order_and_sync(cr, uid, *parameters, 
            context={'only_name': current_proxy.name})
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
