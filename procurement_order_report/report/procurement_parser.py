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
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _


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
            
            'level_break': self.level_break,
            'is_last': self.is_last,
            'get_totals': self.get_totals,
            
            'get_filter_description': self.get_filter_description,
        })
        
        # Paramters for report management:
        self.level_break_last = False
        self.counters = {}
        self.last = False
    
    def get_filter_description(self, ):
        '''
        '''
        return self.filter_description or ''
        
    def add_totals(self, totals, reset=False): 
        i = 0
        for item in totals:
            if reset:
                self.totals[i] = totals[i]
            else:
                self.totals[i] += totals[i]
            i += 1                 
      
    def get_totals(self, item):
        ''' return elements
        '''
        return self.last_totals[item]
        
    def is_last(self, line):
        ''' Check if last line is current
        '''        
        if self.last == line:
            self.last_totals = tuple(self.totals)            
            return True
        else:
            return False    
            
    def level_break(self, code, totals):
        ''' Check if code break level and update totals
        '''
        if self.level_break_last == False:
            self.level_break_last = code
            self.totals = list(totals) # Start up total counters
            return False
        
        if self.level_break_last == code:
            # Add passed totals to total:
            self.add_totals(totals)
            return False
        else:
            self.level_break_last == code
            self.last_totals = tuple(self.totals)
            self.add_totals(totals, reset=True)
            return True    
        
    def get_datetime(self):
        ''' Return datetime obj
        '''
        return datetime

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
        # Parameters for report management:
        self.level_break_last = False
        self.counters = {}
        self.last = False

        products = {}
        res = []
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
            domain.append(('default_code', '=ilike', '%s%s' % (
                code_start, '%')))  
            self.filter_description += _(', code start %s') % code_start
        
        line_ids = line_pool.search(self.cr, self.uid, domain)

        # Loop on order:
        for line in line_pool.browse(
                self.cr, self.uid, line_ids): 
            # ------------------
            # Quantity analysis:
            # ------------------
            mrp_remain = line.product_uom_qty - \
                line.product_uom_maked_sync_qty
            delivery_remain = line.product_uom_qty - \
                line.delivered_qty    
            
            # if no production remaon or all delivered:    
            if mrp_remain <= 0 or delivery_remain <= 0: # TODO use <=
                continue # jump line

            # --------------
            # Code analysis:
            # --------------
            if grouped:
                code = line.product_id.default_code[from_code: to_code]
            else:   
                code = line.product_id.default_code # all code
                
            if code not in products:
                products[code] = []
                
            #res.append(line) # unsorted
            products[code].append(line)
        
        # create a res order by product code
        for code in sorted(products):
            res.extend(products[code])        
        
        # Save last for print total at the end    
        if len(res):    
            self.last = res[-1]
            
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
