# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.report import report_sxw
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

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_closed_object': self.get_closed_object,            
            'get_date': self.get_date,            
            })
    
    def get_date(self, ):
        ''' For report time
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def get_closed_object(self, ):
        ''' List of order
        '''
        sol_pool = self.pool.get('sale.order.line')
        
        sol_ids = sol_pool.search(self.cr, self.uid, [
            ('mrp_id.state', 'not in', ('cancel', 'done')),
            ('mrp_id', '!=', False),
            ('go_in_production', '=', True),
            ('mx_closed', '=', True),
            ])
        
        items = []
        for item in sorted(sol_pool.browse(
                self.cr, self.uid, sol_ids), 
                key=lambda x: (x.mrp_id.name,x.mrp_sequence)):
            if item.product_uom_qty > item.product_uom_maked_sync_qty:
                items.append(item)    
        return items
                
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
