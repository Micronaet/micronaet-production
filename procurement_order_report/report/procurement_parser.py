#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    counters = {}
    last_record = 0
    
    def __init__(self, cr, uid, name, context):
        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_counter': self.get_counter,
            'set_counter': self.set_counter,

            'get_object_line': self.get_object_line,
            'get_datetime': self.get_datetime,
            'get_date': self.get_date,
            
            'get_filter_description': self.get_filter_description,
        })
    
    def get_filter_description(self, ):
        '''
        '''
        return self.filter_description or ''
        
    def get_datetime(self):
        ''' Return datetime obj
        '''
        return datetime

    def get_date(self):
        ''' Return datetime obj
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_counter(self, name):
        ''' Get counter with name passed (else create an empty)
        '''
        if name not in self.counters:
            self.counters[name] = False
        return self.counters[name]

    def set_counter(self, name, value):
        ''' Set counter with name with value passed
        '''
        self.counters[name] = value
        return "" # empty so no write in module

    def get_object_line(self, data):
        ''' Selected object + print object
        '''
        _logger.info('Start report data: %s' % data)
        
        # Parameters for report management:
        sale_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')

        # Get wizard information:
        code_start = data.get('code_start', False)

        #from_code = data.get('from_code', 0) - 1
        #to_code = from_code + data.get('code_length', 0)
        #if from_code > 0 and to_code > 0:
        #    grouped = True
        #else:
        grouped = False     

        from_date = data.get('from_date', False)
        to_date = data.get('to_date', False)
        from_deadline = data.get('to_deadline', False)
        to_deadline = data.get('to_deadline', False)

        # ---------------------------------------------------------------------
        #                      Sale order filter
        # ---------------------------------------------------------------------
        # Default:
        domain = [
            # Order confirmed or forecast:
            '|',
            ('state', 'not in', ('cancel', 'draft', 'sent')), # 'done'
            ('forecasted_production_id', '!=', False), # include forecast order
            
            # Order for send pricelist:
            ('pricelist_order', '=', False), 
            ]

        # -------------------------
        # Start filter description:
        # -------------------------
        self.filter_description = _('Order open, not pricelist order')

        # TODO domain.append(('order_closed', '=', False)) << all delivered
        
        if from_date:
            domain.append(('date_order', '>=', from_date))
            self.filter_description += _(', date >= %') % from_date
        if to_date:
            domain.append(('date_order', '<', from_date))
            self.filter_description += _(', date < %') % to_date
        
        order_ids = sale_pool.search(self.cr, self.uid, domain)
        
        # ---------------------------------------------------------------------
        #                      Sale order line filter
        # ---------------------------------------------------------------------
        domain = [('order_id', 'in', order_ids)]        

        if from_deadline:
            domain.append(('date_deadline', '>=', from_deadline))
            self.filter_description += _(', deadline >= %') % from_deadline
        if to_deadline:
            domain.append(('date_deadline', '<', to_deadline))
            self.filter_description += _(', deadline < %') % to_deadline
            
        if code_start:  
            domain.append(('product_id.default_code', '=ilike', '%s%s' % (
                code_start, '%')))  
            self.filter_description += _(', code start %s') % code_start
        
        line_ids = line_pool.search(self.cr, self.uid, domain)

        # Loop on order:
        products = {}
        for line in line_pool.browse(self.cr, self.uid, line_ids):             
            # ------------------
            # Quantity analysis:
            # ------------------
            mrp_remain = line.product_uom_qty - line.product_uom_maked_sync_qty
            delivery_remain = line.product_uom_qty - line.delivered_qty    
            
            # if no production remaon or all delivered:    
            if mrp_remain <= 0 or delivery_remain <= 0: # TODO use <=
                continue # jump line
            code = line.product_id.default_code    

            if code not in products:
                products[code] = []
            products[code].append(line)
        
        # create a res order by product code
        res = []
        keys = sorted(products)
        _logger.info('Product group: %s' % len(keys))
        for key in keys:
            total = [0, 0, 0]
            # Add product line:
            for line in products[key]:
                res.append(('P', line))
                total[0] += line.product_uom_qty
                total[1] += line.product_uom_maked_sync_qty
                total[2] += line.product_uom_qty - \
                    line.product_uom_maked_sync_qty

            # Add total line:    
            res.append(('T', total))
                
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
