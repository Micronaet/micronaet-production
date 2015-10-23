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

class MrpPartialProductionWizard(orm.TransientModel):
    ''' Wizard that assign partial lavoration to the selected order line
    '''    
    _name = "mrp.production.partial.wizard"

    # ---------
    # Onchange:
    # ---------
    def onchange_current_load(self, cr, uid, ids, current, remain, 
            context=None):
        ''' Test if don't pass total - partial
        '''
        sol_id = context.get('active_id', False)
        sol_proxy = self.pool.get("sale.order.line").browse(
            cr, uid, sol_id, context=context)
            
        total = sol_proxy.product_uom_qty    
        maked = sol_proxy.product_uom_maked_sync_qty    

        if remain: # compile remain quantity
            return {'value': {
                'maked_load': total - maked, }}    

        if not current: 
            return {}
            
        maximum = total - maked
        if current > maximum:
            return {'warning': {
                'title': _('Over limit'), 
                'message': _('Quantity must be max %s') % maximum,
                }}
        
    # --------------    
    # Button events:
    # --------------    
    def action_assign_order(self, cr, uid, ids, context=None):
        ''' Assign production to selected order line
        '''
        if context is None: 
            context = {}       

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]    
        sol_id = context.get('active_id', False)        
        q = wiz_proxy.maked_load
        self.pool.get('sale.order.line').write(
            cr, uid, sol_id, {
                'product_uom_maked_qty': q,
                'sync_state': 'partial',
                }, context=context)
        return {'type': 'ir.actions.act_window_close'}

    _columns = {
        'maked_load': fields.float('Partial load', 
            digits=(16, 2), help="Partial load to assign as producted", ),
        'remain': fields.boolean('Remain', required=False),    
        #'note': fields.text('Note'), # TODO default function for range!!!
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
