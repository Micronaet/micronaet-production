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

class ResPartnerDeadlineMandatory(orm.Model):
    """ Add extra information to partner for mandatory orders deadline
    """
    
    _inherit = 'res.partner'
    
    # Button events:
    def force_mandatory_order_line(self, cr, uid, ids, context=None):
        ''' Force in sale order line all mandatory for this partner
        '''
        line_pool = self.pool.get('sale.order.line')
        line_ids = line_pool.search(cr, uid, [
            ('partner_id', '=', ids[0])], context=context)
        line_pool.write(cr, uid, line_ids, {
            'has_mandatory_delivery': True}, context=context)    
        return True
        
    _columns = {
        'has_mandatory_delivery': fields.boolean('Mandatory delivery',
            help='This partner has always mandatory order'),
        }

class SaleOrderLineMandatory(orm.Model):
    """ Add extra information to order line for mandatory deadline
    """
    
    _inherit = 'sale.order.line'
    
    _columns = {
        'has_mandatory_delivery': fields.boolean('Mandatory delivery',
            help='This partner has always mandatory order'),
        }
        
class SaleOrderSql(orm.Model):
    """ Update basic obiect for import accounting elements
    """

    _inherit = "sale.order"

    # -------------------------------------------------------------------------
    #                                 Override function
    # -------------------------------------------------------------------------
    def schedule_etl_sale_order(self, cr, uid, context=None):
        """ Import order but after check partner as mandatory
        """
        # Import as usual orders:
        super(SaleOrderSql, self).schedule_etl_sale_order(
            cr, uid, context=context)
            
        # Update mandatory deadline:    
        _logger.info("Update order mandatory delivery")

        # CASE 1: Partner mandatory delivery:
        partner_pool = self.pool.get('res.partner')
        partner_ids = partner_pool.search(cr, uid, [
            ('has_mandatory_delivery', '=', True)], context=context)
        if partner_ids:
            # --------------------------------------------
            # Reset parameter for current imported orders:
            # --------------------------------------------
            line_pool = self.pool.get('sale.order.line')
            line_ids = line_pool.search(cr, uid, [
                ('has_mandatory_delivery', '=', True)], context=context)
            line_pool.write(cr, uid, line_ids, {
                'has_mandatory_delivery': False}, context=context)    
                
            # --------------------------------
            # Force all order of this partner:
            # --------------------------------
            order_pool = self.pool.get('sale.order')
            order_ids = order_pool.search(cr, uid, [
                ('partner_id', 'in', partner_ids),
                ('mandatory_order', '=', 'partner'), # only partner state
                ], context=context)
            line_ids = line_pool.search(cr, uid, [
                ('order_id', 'in', order_ids)], context=context)       
            line_pool.write(cr, uid, line_ids, {
                'has_mandatory_delivery': True}, context=context)                    
        # CASE 2: Force line with deadline from accounting TODO            
        return
    
    # ----------------
    # Button function:
    # ----------------
    # Utility:
    def _force_mandatory_state(self, cr, uid, ids, state, context=None):
        ''' Force / Unforce utility
            NOTE: 'partner' state will never come back!
        '''
        # Unforce order:
        self.write(cr, uid, ids, {
            'mandatory_order': 'yes' if state==True else 'not',
            }, context=context)
        
        # Unforce line:    
        line_pool = self.pool.get('sale.order.line')    
        line_ids = line_pool.search(cr, uid, [
            ('order_id', '=', ids[0])], context=context)
        line_pool.write(cr, uid, line_ids, {
            'has_mandatory_delivery': state,
            }, context=context)
        return True    
            
    # Events:        
    def unforce_mandatory_state(self, cr, uid, ids, context=None):
        ''' Unforce button
        '''
        return self._force_mandatory_state(
            cr, uid, ids, False, context=context)
        
    def force_mandatory_state(self, cr, uid, ids, context=None):
        ''' Unforce button
        '''
        return self._force_mandatory_state(
            cr, uid, ids, True, context=context)
    
    _columns = {
        'mandatory_order': fields.selection([
            ('partner', 'Depend on partner'),
            ('not', 'Not mandatory'),
            ('yes', 'Mandatory'),
            ], 'Mandatory order'),
        }    
    _defaults = {    
        # Default value:
        'mandatory_order': lambda *x: 'partner',
        }        
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
