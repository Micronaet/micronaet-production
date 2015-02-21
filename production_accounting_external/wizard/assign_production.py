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

class MrpProductionAssignWizard(orm.TransientModel):
    ''' Wizard that assign lavoration to the selected order line
    '''
    
    _name = "mrp.production.assign.wizard"

    # Wizard button:
    def action_unassign_order(self, cr, uid, ids, context=None):
        if context is None:
            context = {}        
        sale_order_line_id = context.get("active_id",0)        
        mod = self.pool.get('sale.order.line').write(
            cr, uid, sale_order_line_id, {
                'mrp_production_id': False, }, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def action_assign_order(self, cr, uid, ids, context=None):
        ''' Assign production to selected order line
        '''
        if context is None: context={}        
        
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        sale_order_line_id = context.get("active_id",0)
        production_id = wizard_browse.production_id.id if wizard_browse.production_id else False
        mod = self.pool.get('sale.order.line').write(
            cr, uid, sale_order_line_id, {
                'mrp_production_id': production_id, }, context=context)

        return {'type':'ir.actions.act_window_close'}

    # default function:        
    def default_product_id(self, cr, uid, context=None):
        ''' Get default value
        '''
        sol_pool = self.pool.get('sale.order.line')
        sol_browse = sol_pool.browse(cr, uid, context.get(
            "active_id", 0), context=context)
        return sol_browse.product_id.id 

    def default_note(self, cr, uid, context=None):
        ''' Get default value for note (list of MO with particulars)
        '''
        if context is None: context={}        

        production_pool = self.pool.get('mrp.production')
        product_id = context.get('product_id', False)
        search_ids = production_pool.search(
            cr, uid, [
                ('accounting_state','not in',('close','cancel',)),
                ('product_id','=',product_id)
                ],context=context)
        if search_ids:
            res=""
            for mo in production_pool.browse(
                    cr, uid, search_ids, context=context):
                res+= "Production: [%s] Status: %s" % (
                    mo.name, mo.state_info, )
        else:
            return "No lavoration open for this product is found! (create one with wizard procedure)"

    _columns = {
        'product_id': fields.many2one(
            'product.product', 
            'Product', 
            help='Product selected in sale order line'),
        'production_id': fields.many2one(
            'mrp.production', 
            'Production', 
            help='Production assigned to the order line',),
        'note': fields.text(
            'Annotation', 
            help='Annotation about production opened with selected product'),
        }
        
    _defaults = {
        'product_id': lambda s, cr, uid, c: s.default_product_id(cr, uid, context=c),
        'note': lambda s, cr, uid, c: s.default_note(cr, uid, context=c),
    }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
