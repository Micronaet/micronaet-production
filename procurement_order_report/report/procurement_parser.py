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
            'get_object_grouped_line': self.get_object_grouped_line,
            'get_orders_selected': self.get_orders_selected,

            'get_datetime': self.get_datetime,
            'get_date': self.get_date,
            
            'get_filter_description': self.get_filter_description,
            
            'get_general_total': self.get_general_total,
        })

    def get_general_total(self, ):
        '''
        '''
        return self.general_total
    
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

    # Utility for 2 report:
    def browse_order_line(self, data):
        ''' Return line (used from 2 report)
        '''
        _logger.info('Start report data: %s' % data)
        # Parameters for report management:
        sale_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')
        
        # Get wizard information:
        code_start = data.get('code_start', False)        
        only_remain = data.get('only_remain', False)

        #from_code = data.get('from_code', 0) - 1
        #to_code = from_code + data.get('code_length', 0)
        #if from_code > 0 and to_code > 0:
        #    grouped = True
        #else:
        # TODO remove:
        grouped = False

        from_date = data.get('from_date', False)
        to_date = data.get('to_date', False)
        from_deadline = data.get('from_deadline', False)
        to_deadline = data.get('to_deadline', False)
        code_from = int(data.get('code_from', 1))
        code_partial = data.get('code_partial', '')        

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
            self.filter_description += _(', date >= %s') % from_date
        if to_date:
            domain.append(('date_order', '<=', to_date))
            self.filter_description += _(', date < %s') % to_date
        
        if only_remain:
            self.filter_description += _(', only remain to produce')
        else:    
            self.filter_description += _(', all order line')
        
        order_ids = sale_pool.search(self.cr, self.uid, domain)
        _logger.info('Order filter domain used: [%s] order selected: %s' % (
            domain, len(order_ids)))

        # ---------------------------------------------------------------------
        #                      Sale order line filter
        # ---------------------------------------------------------------------
        domain = [('order_id', 'in', order_ids)]        

        if code_partial:
            self.filter_description += _(
                ', Partial code filter: %s (from char: %s) ') % ( 
                    code_partial, code_from)

        if from_deadline:
            domain.append(('date_deadline', '>=', from_deadline))
            self.filter_description += _(', deadline >= %s') % from_deadline
        if to_deadline:
            domain.append(('date_deadline', '<=', to_deadline))
            self.filter_description += _(', deadline <= %s') % to_deadline
            
        if code_start:  
            domain.append(('product_id.default_code', '=ilike', '%s%s' % (
                code_start, '%')))  
            self.filter_description += _(', code start %s') % code_start
        
        line_ids = line_pool.search(self.cr, self.uid, domain)
        _logger.info('Order line selected: %s' % (len(line_ids), ))
        
        return line_pool.browse(self.cr, self.uid, line_ids)
    
    def get_object_line(self, data):
        ''' Selected object + print object
        '''
        # Loop on order:
        products = {}
        browse_line = self.browse_order_line(data)
        
        # --------------------
        # Manage partial code:
        # --------------------
        code_from = int(data.get('code_from', 1))
        code_partial = data.get('code_partial', '')
        if code_partial:
            from_partial = code_from - 1
            to_partial = from_partial + len(code_partial)

        i = 0
        for line in browse_line:
            i += 1 
            # -------------------
            # Filter for partial:
            # -------------------
            if code_partial and line.product_id.default_code[
                    from_partial: to_partial] != code_partial:
                _logger.info('Code partial jumped: %s !% %s' % (
                code_partial, line.product_id.default_code[
                    from_partial: to_partial]))    
                continue # jump line
                
            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
            delivered_qty = line.delivered_qty
            
            if delivered_qty > product_uom_maked_sync_qty:
                mrp_remain = product_uom_qty - delivered_qty
            else:
                mrp_remain = product_uom_qty - product_uom_maked_sync_qty

            if data.get('only_remain', False) and mrp_remain <= 0:
                _logger.info('Jump only remain: mrp_remain: %s' % (
                    mrp_remain))
                continue # jump if no item or all produced

            code = line.product_id.default_code
            if code not in products:
                products[code] = []
            products[code].append(line)
            _logger.info('Code added: %s' % code)
        
        # create a res order by product code
        res = []
        codes = sorted(products)
        self.general_total = [0, 0, 0, 0]
        for code in codes:
            total = [0, 0, 0, 0]
            # Add product line:
            for line in products[code]:
                res.append(('P', line))
                
                # Quantity used:
                product_uom_qty = line.product_uom_qty
                product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
                delivered_qty = line.delivered_qty
                if delivered_qty > product_uom_maked_sync_qty:
                    remain = product_uom_qty - delivered_qty
                else:
                    remain = product_uom_qty - product_uom_maked_sync_qty
                
                # Block total:
                total[0] += product_uom_qty
                total[1] += product_uom_maked_sync_qty
                total[2] += remain
                total[3] += delivered_qty
                                
                # General Total:
                self.general_total[0] += product_uom_qty
                self.general_total[1] += product_uom_maked_sync_qty
                self.general_total[2] += remain
                self.general_total[3] += delivered_qty
    
            # Add total line:    
            res.append(('T', total))                
        return res

    def get_object_grouped_line(self, data):
        ''' Selected object + print object
        '''
        def clean_number(value):
            return ('%s' % value).replace('.', ',')
            
        filename = os.path.expanduser(os.path.join(
            '~', 'photo', 'log', 'frame.csv'))
        log_file = open(filename, 'w')
        log_file.write('READ|STATUS|ORDER|PARTNER|DEADLINE|PRODUCT|CODE|OC|MAKE|DELIVERY|S|B|TOT\n')
        mask = '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n'
        
        # Loop on order:
        products = {}
        browse_line = self.browse_order_line(data)
        self.order_ids = [] # list of order interessed from movement

        # Manage partial code
        code_from = int(data.get('code_from', 1))
        code_partial = data.get('code_partial', '')
        if code_partial:
            from_partial = code_from - 1
            to_partial = from_partial + len(code_partial)

        for line in browse_line:
            # Filter for partial:.
            if code_partial and line.product_id.default_code[
                    from_partial: to_partial] != code_partial:
                continue # jump line

            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
            delivered_qty = line.delivered_qty
            
            TOT = product_uom_qty - delivered_qty            
            if delivered_qty > product_uom_maked_sync_qty:
                B = 0
                status = 'STOCK'
            else:
                B = product_uom_maked_sync_qty - delivered_qty 
                status = 'PROD'                
            S = TOT - B

            #if data.get('only_remain', False) and S <= 0:
            #    continue # jump if no item or all produced
            code = '%s...%s' % (
                line.product_id.default_code[0:3],
                line.product_id.default_code[6:8],
                )
            if TOT == 0:
                log_file.write(mask % (
                    'NO',
                    status,
                    line.order_id.name,
                    line.order_id.partner_id.name,
                    line.date_deadline,
                    line.product_id.default_code,
                    code,
                    clean_number(product_uom_qty),
                    clean_number(product_uom_maked_sync_qty),
                    clean_number(delivered_qty),
                    clean_number(S),
                    clean_number(B),
                    clean_number(TOT),
                    ))
                continue
            
            log_file.write(mask % (
                'YES',
                status,
                line.order_id.name,
                line.order_id.partner_id.name,
                line.date_deadline,
                line.product_id.default_code,
                code,
                clean_number(product_uom_qty),
                clean_number(product_uom_maked_sync_qty),
                clean_number(delivered_qty),
                clean_number(S),
                clean_number(B),
                clean_number(TOT),
                ))
            if line.order_id.id not in self.order_ids:
                self.order_ids.append(line.order_id.id)
                
            if code not in products:
                products[code] = []
            products[code].append(line)
        
        # create a res order by product code
        res = []
        codes = sorted(products)
        last_parent = False
        parent_total = [0, 0, 0]
        code = ''

        for code in codes:
            if last_parent == False: 
                # XXX only for first line
                last_parent = code[:3] # first 3                
            elif code[:3] != last_parent:
                # Save previous code
                res.append(('T', last_parent, parent_total))
                last_parent = code[:3]
                parent_total = [0, 0, 0]
                
            total = [0, 0, 0]
            # Add product line:
            for line in products[code]:
                #res.append(('P', line))

                # Quantity used:
                product_uom_qty = line.product_uom_qty
                product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
                delivered_qty = line.delivered_qty

                TOT = product_uom_qty - delivered_qty                
                if delivered_qty > product_uom_maked_sync_qty:
                    B = 0
                else:
                    B = product_uom_maked_sync_qty - delivered_qty 
                S = TOT - B
                                
                # Line total:
                total[0] += S
                total[1] += B
                total[2] += TOT

                # Block total
                parent_total[0] += S
                parent_total[1] += B
                parent_total[2] += TOT

            # Add total line:    
            res.append(('L', code, total))                
        
        # last record_
        if last_parent:
            res.append(('T', last_parent, parent_total))
        return res

    def get_orders_selected(self):
        order_pool = self.pool.get('sale.order')
        return order_pool.browse(self.cr, self.uid, self.order_ids)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
