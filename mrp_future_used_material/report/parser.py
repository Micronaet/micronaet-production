##############################################################################
#
# Copyright (c) 2008-2010 SIA "KN dati". (http://kndati.lv) All Rights Reserved.
#                    General contacts <info@kndati.lv>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID#, api
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
        self.counters = {}
        self.localcontext.update({
            'get_objects': self.get_objects,
        })

    def get_objects(self, data):
        ''' All available halfwork
        '''
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        
        # Parameter:
        department_select = ('cut', )

        res = []
        product_pool = self.pool.get('product.product')
        
        # Set inventory status: 
        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)
        
        # ---------------------------------------------------------------------
        # 1. Select product with future move:
        # ---------------------------------------------------------------------
        # list of product of 'cut' category department, no placeholder:
        bom_pool = self.pool.get('mrp.bom.line')
        bom_ids = bom_pool.search(cr, uid, [
            ('bom_id.bom_category', '=', 'dynamic'),
            ], context=context)

        product_ids = []    
        for line in bom_pool.browse(cr, uid, bom_ids, context=context):                
            if not line.category_id or not line.category_id.department or \
                    line.category_id.department not in department_select:
                continue # jump department not used
            cmpt = line.product_id        
            if cmpt.bom_placeholder or cmpt.bom_alternative:
                continue # jump placeholder
            if cmpt.id not in product_ids:
                product_ids.append(cmpt.id)

        # ---------------------------------------------------------------------
        # 2. Search product with available quantity:
        # ---------------------------------------------------------------------
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            net = product.mx_net_mrp_qty
            future = product.mx_mrp_future_qty
            difference = net - future
            # All records also difference negative
            if difference > 0.0:
                res.append((product, net, future, difference))

        # Restore status no_inventory_status:
        user_pool.set_no_inventory_status(
            cr, uid, value=previous_status, context=context)            
        # ---------------------------------------------------------------------
        # 3. Sort product                
        # ---------------------------------------------------------------------        
        all_object = sorted(res, key=lambda x: x[0].default_code)
        top10_object = sorted(res, key=lambda x: x[3], reverse=True)[:10]
        return all_object, top10_object
        #sorted(res, key=lambda x: x[0].default_code)
