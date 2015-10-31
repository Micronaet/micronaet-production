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
            'get_date': self.get_date,
            
            # production report:
            'get_hour': self.get_hour,
            
            # remain report:
            'get_object_remain': self.get_object_remain,            
        })

    def get_date(self, ):
        ''' For report time
        '''
        return datetime.now()

    def get_object_remain(self, ):
        ''' Get as browse obj all record with unsync elements
        '''
        self.cr.execute(''' 
            SELECT distinct mrp_id 
            FROM sale_order_line 
            WHERE product_uom_maked_qty != 0;
            ''')
        mrp_ids = [item[0] for item in self.cr.fetchall()]
        mrp_ids = self.pool.get('mrp.production').search (
            self.cr, self.uid, [('id', 'in', mrp_ids)], order='name')
        return self.pool.get('mrp.production').browse(
            self.cr, self.uid, mrp_ids)

    def get_hour(self, value):
        ''' Format float with H:MM format
        '''
        try:
            return "%s:%s" % (
                int(value),
                int(60 * (value - int(value))),
                )
        except:
            return "0:00"
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
