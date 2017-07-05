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

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    
    _inherit = 'res.company'
    
    def check_certification_from_product_line(
            self, cr, mode, line, date, company, context=None):
        ''' Check certification present for product in line passed
            Evaluation for print:
            1. there's one product with *_certified in the item list
            2. the document date must be > from certified date in company            
        '''        
        mode = mode.lower()
        if mode not in ('fsc', 'pefc'):
            _logger.error('Mode must be: fsc or pefc!')
            return False # No show!
        
        field = '%s_certified' % mode    
        #if date
        return True
    
    _columns = {
        'fsc_certified': fields.boolean('FSC Certified'),
        'fsc_code': fields.char('FSC Code', size=50),
        'fsc_from_date': fields.date('FSC from date'),
        'fsc_report_text': fields.char('FSC report text', size=120, 
            translate=True),
        'fsc_logo': fields.binary(
            'FSC Logo', help='FSC document logo bottom part'),

        'pefc_certified': fields.boolean('PEFC Certified'),
        'pefc_code': fields.char('PEFC Code', size=50),
        'pefc_from_date': fields.date('PEFC from date'),
        'pefc_report_text': fields.char('PEFC report text', size=120, 
            translate=True),
        'pefc_logo': fields.binary(
            'PEFC Logo', help='PEFC document logo bottom part'),
        
        'xfc_document_note': fields.text('FSC, PEFC Document note'),    
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'fsc_certified': fields.boolean('FSC Certified'),
        'pefc_certified': fields.boolean('PEFC Certified'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
