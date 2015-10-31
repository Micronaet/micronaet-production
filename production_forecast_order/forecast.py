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

class SaleOrderLine(orm.Model):
    ''' Auto link to the production
    '''    
    _inherit = 'sale.order.line'
        
    # default function:
    def _get_mrp_id_default(self, cr, uid, context=None):
        ''' Auto link the production if is a forecast order
        '''
        if context is None:
            context = {}
        res = False
        res_id = context.get('active_id')
        active_model =  context.get('active_model', False)
        
        if res_id and active_model == 'mrp.production':
            return res_id
        else:
            return False    
        
    _columns = {
        # override for default computation:
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='set null', ),
        }
    
    _defaults = {
        'mrp_id': lambda s, cr, uid, ctx: s._get_mrp_id_default(cr, uid, ctx),
        }    

class SaleOrder(orm.Model):
    ''' Link the forecast order to the production
    '''    
    _inherit = 'sale.order'
    
    _columns = {
        'forecasted_production_id': fields.many2one('mrp.production', 
            'Forecasted production', ondelete='cascade'),
        }

class MrpProduction(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''    
    _inherit = 'mrp.production'

    # Button event:
    def create_open_forecast_order(self, cr, uid, ids, context=None):
        ''' Create if not present the forecast order and open (if exist only
            open)
        '''
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]
        if mrp_proxy.forecast_order_id:
            order_id = mrp_proxy.forecast_order_id.id
        else:    
            # Create a forecast order and associate, after open
            sale_pool = self.pool.get('sale.order')
            order_id = sale_pool.create(cr, uid, {
                'name': 'FC-%s' % mrp_proxy.name,
                'partner_id': mrp_proxy.company_id.partner_id.id,
                'date_order': datetime.now(),
                'forecasted_production_id': mrp_proxy.id,
                # TODO 'date_deadline': # end of year?
                
                # TODO remove when there's no importation
                'accounting_order': True, # Like an order from account
                }, context=context)
                
            # Update ref in production    
            self.write(cr, uid, ids, {
                'forecast_order_id': order_id, 
                }, context=context)    

        # Open order for adding lines:        
        return {
            'name': 'Previsional sale',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
            'res_id': order_id,
            #'domain': [],
            #'target': 'new',
            #'search_view_id': sale_order_tree,
            }
        
    _columns = {
        'forecast_order_id': fields.many2one('sale.order', 'Forecast order',
            ondelete='set null'),        
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
