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

class SaleOrderProcurementReportWizard(orm.TransientModel):
    ''' Procurements depend on sale
    '''    
    _name = 'sale.order.procurement.report.wizard'
    _description = 'Sale produrement wizard'
    
    # --------------
    # Button events:
    # --------------
    def print_report(self, cr, uid, ids, context=None):
        ''' Redirect to report passing parameters
        ''' 
        wiz_proxy = self.browse(cr, uid, ids)[0]
            
        datas = {}
        datas['wizard'] = True # started from wizard
        
        if wiz_proxy.report_type == 'detail':
            report_name = 'mx_procurement_report' 
        else:
            report_name = 'mx_procurement_report' # TODO change
               
        datas['from_date'] = wiz_proxy.from_date or False
        datas['to_date'] = wiz_proxy.to_date or False
        datas['from_deadline'] = wiz_proxy.from_deadline or False
        datas['to_deadline'] = wiz_proxy.to_deadline or False
        
        datas['code_from'] = wiz_proxy.code_from
        datas['code_length'] = wiz_proxy.code_length

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'mx_procurement_report',
            'datas': datas,
            }
        
    _columns = {
        'report_type': fields.selection([
            ('detail', 'Detail'),
            ('summary', 'Summary'),
            ], 'Report type', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        
        'from_date': fields.date('From', help='Date >='),
        'to_date': fields.date('To', help='Date <'),
        'from_deadline': fields.date('From deadline', help='Date deadline >='),
        'to_deadline': fields.date('To deadline', help='Date deadline <'),
        
        'code_from': fields.integer('Code from char', required=True), 
        'code_length': fields.integer('Code from char', required=True), 
        }
        
    _defaults = {
        'report_type': lambda *x: 'detail',
        #'to_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
