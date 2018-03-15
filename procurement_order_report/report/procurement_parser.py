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
from openerp.osv import fields, osv, expression, orm
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleOrder(orm.Model):
    ''' Utility function moved in sale order
    '''
    _inherit = 'sale.order'
    
    # -------------------------------------------------------------------------
    # Report Utility:
    # -------------------------------------------------------------------------
    def _report_procurement_get_filter_description(
            self, cr, uid, context=None):
        ''' Return filter for object
        '''
        return self.filter_description or ''

    def _report_procurement_get_orders_selected(self, cr, uid, context=None):
        ''' Moved function here
        '''        
        return self.browse(cr, uid, self.order_ids, context=context)
        
    def _report_procurement_browse_order_line(
            self, cr, uid, data=None, context=None):
        ''' Return line (used from 2 report)
        '''
        _logger.info('Start report data: %s' % data)
        
        # Parameters for report management:
        line_pool = self.pool.get('sale.order.line')
        
        # Get wizard information:
        code_start = data.get('code_start', False)        
        no_forecast = data.get('no_forecast', False)        

        record_select = data.get('record_select', 'all')
        only_remain = record_select != 'all'

        family_id = data.get('family_id', False)
        family_name = data.get('family_name', '?')

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
        if only_remain:
            domain.append(('mx_closed', '=', False))
        _logger.warning('Domain for order filter: %s' % domain)

        if no_forecast:
            domain.append(('forecasted_production_id', '=', False))
            
        # -------------------------
        # Start filter description:
        # -------------------------
        self.filter_description = _('Order open, not pricelist order')

        # TODO domain.append(('order_closed', '=', False)) << all delivered
        if no_forecast:
            self.filter_description += _(', no forecast')
        else:
            self.filter_description += _(', forecast')
                    
        if from_date:
            domain.append(('date_order', '>=', from_date))
            self.filter_description += _(', date >= %s') % from_date
        if to_date:
            domain.append(('date_order', '<=', to_date))
            self.filter_description += _(', date < %s') % to_date
                
        self.filter_description += _(', Selezione record: %s' % record_select)
        #if only_remain:
        #    self.filter_description += _(', only remain to produce')
        #else:    
        #    self.filter_description += _(', all order line')
        
        order_ids = self.search(cr, uid, domain)
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

        if family_id:
            domain.append(('product_id.family_id', '=', family_id))  
            self.filter_description += _(', family %s') % family_name
        
        line_ids = line_pool.search(cr, uid, domain, context=context)
        _logger.info('Order line selected: %s' % len(line_ids))
        
        return line_pool.browse(cr, uid, line_ids, context=context)
        
    def _report_procurement_grouped_get_objects(
            self, cr, uid, data=None, context=None):
        ''' Used here parser report function, lauched also for XLSX files 
            data extract
        '''         
        def clean_number(value):
            return ('%s' % value).replace('.', ',')
            
        # Loop on order:
        products = {}
        browse_line = self._report_procurement_browse_order_line(
            cr, uid, data, context=context)
        self.order_ids = [] # list of order interessed from movement

        record_select = data.get('record_select', 'all')
        only_remain = record_select != 'all'
        xlsx = data.get('xlsx', False) # Mode XLSX

        # Manage partial default_code
        code_from = int(data.get('code_from', 1))
        code_partial = data.get('code_partial', '')
        if code_partial:
            from_partial = code_from - 1
            to_partial = from_partial + len(code_partial)

        mrp_date_db = {}
        for line in browse_line:
            # First test for speed up:
            if only_remain and line.mx_closed:
                continue # jump if no item or all produced

            # Filter for partial:.
            if code_partial and line.product_id.default_code[
                    from_partial: to_partial] != code_partial:
                continue # jump line

            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
            delivered_qty = line.delivered_qty

            TOT = product_uom_qty - delivered_qty            
            if delivered_qty > product_uom_maked_sync_qty:
                B = 0 # use stock
            else:
                B = product_uom_maked_sync_qty - delivered_qty # use prod.
            S = TOT - B

            code = '%s...%s' % (
                line.product_id.default_code[0:3],
                line.product_id.default_code[6:8],
                )
            if TOT == 0:
                continue
            
            if line.order_id.id not in self.order_ids:
                self.order_ids.append(line.order_id.id)
                
            if code not in products:
                products[code] = []
            products[code].append(line)
            
            if xlsx:
                try:
                    date_planned = line.mrp_id.date_planned[:10]
                except:
                    date_planned = False
                if date_planned not in mrp_date_db:
                    mrp_date_db[date_planned] = {}
                if code not in mrp_date_db[date_planned]:
                    mrp_date_db[date_planned][code] = 0
                    
                #TODO (Suspended):     
                mrp_date_db[date_planned][code] += S
        
        # create a res order by product code
        res = []
        codes = sorted(products)
        last_parent = False
        parent_total = [0, 0, 0]
        code = ''

        for code in codes:
            # Check if is the same parent code:
            if last_parent == False: 
                # XXX only for first line
                last_parent = code[:3] # first 3                
            elif code[:3] != last_parent:
                # Save previous code
                res.append(('T', last_parent, parent_total))
                last_parent = code[:3]
                parent_total = [0, 0, 0] # Parent total
                
            total = [0, 0, 0] # Current code total
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

                # Block total (for parent code)
                parent_total[0] += S
                parent_total[1] += B
                parent_total[2] += TOT

            # Add total line:    
            res.append(('L', code, total))                
        
        # last record_
        if last_parent:
            res.append(('T', last_parent, parent_total))
            
        if xlsx: # for xlsx call
            return res, mrp_date_db
        else: # for normal report call
            return res        

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
            'get_object_grouped_family_line': 
                self.get_object_grouped_family_line,
            'get_orders_selected': self.get_orders_selected,

            'get_datetime': self.get_datetime,
            'get_date': self.get_date,
            
            'get_filter_description': self.get_filter_description,
            
            'get_general_total': self.get_general_total,
        })

    def get_general_total(self, ):
        ''' Return instance general total
        '''
        return self.general_total
    
    def get_filter_description(self, ):
        ''' Moved in sale order
        '''
        return self.pool.get(
            'sale.order')._report_procurement_get_filter_description(
                self.cr, self.uid)
        
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

    # -------------------------------------------------------------------------
    # Utility for 3 report:
    # -------------------------------------------------------------------------
    def browse_order_line(self, data):
        ''' Move here function in sale order
        '''
        return self.pool.get(
            'sale.order')._report_procurement_browse_order_line(
            self.cr, self.uid, data=data)
    
    def get_object_line(self, data):
        ''' Selected object + print object
        '''
        # TODO Move in sale.order?
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

        record_select = data.get('record_select', 'all') #
        only_remain = record_select != 'all'
        no_forecast = data.get('no_forecast', False)
        
        i = 0
        self.general_total = [0, 0, 0, 0]

        for line in browse_line:
            i += 1
            # First test for speed up: added 17 giu 2016 (for speed up)
            #if record_select != 'all' and line.mx_closed:
            if only_remain and line.mx_closed:
                # State: mrp and delivery are empty in mx_closed line
                _logger.info('Jump only remain: line is closed')
                continue # jump if no item or all produced

            # -------------------
            # Filter for partial:
            # -------------------
            default_code = line.product_id.default_code
            if not default_code:                
                raise osv.except_osv(
                    'Data error', 
                    'Default code not found: %s\n' % (
                        line.product_id.name))

            if code_partial and \
                    default_code[from_partial: to_partial] != code_partial:
                _logger.info('Code partial jumped: %s ! %s' % (
                code_partial, 
                default_code[from_partial: to_partial]))    
                continue # jump line
                
            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
            delivered_qty = line.delivered_qty
            to_delivery_qty = product_uom_qty - delivered_qty
            
            if delivered_qty > product_uom_maked_sync_qty:
                mrp_remain = product_uom_qty - delivered_qty
            else:
                mrp_remain = product_uom_qty - product_uom_maked_sync_qty

            # Record selection:
            if record_select == 'mrp':
                if mrp_remain <= 0:
                    _logger.info('Jump no remain production remain: %s' % (
                        mrp_remain))
                    continue # jump if no item or all produced
                    
            elif record_select == 'delivery':     
                if to_delivery_qty <= 0:
                    _logger.info('Jump no delivery: remain: %s' % (
                        to_delivery_qty))
                    continue # jump if no item or all produced
            else: # 'all'
                pass # nothing for all

            code = default_code
            if default_code not in products:
                products[default_code] = []
            products[default_code].append(line)
            _logger.info('Code added: %s' % default_code)
        
        # create a res order by product default_code
        res = []
        codes = sorted(products)
        self.general_total = [0, 0, 0, 0]
        for default_code in codes:
            total = [0, 0, 0, 0, 
                '', # Use stock without locked
                ]
            # Add product line:
            product_proxy = False
            for line in products[default_code]:
                if product_proxy == False:
                    product_proxy = line.product_id

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
    
            # Stock status available:
            if product_proxy:
                stock_total = int(product_proxy.mx_net_mrp_qty)
                stock_available = int(stock_total - \
                    product_proxy.mx_mrp_b_locked)
                if stock_available > 0:
                    net_to_produce = int(total[2] - stock_available)
                    total[4] = '[%s] (usabili %s mag. %s)' % (
                        net_to_produce if net_to_produce > 0 else '0', 
                        stock_available,
                        stock_total,
                        )
                else:        
                    total[4] = '[%s] (usabili 0 mag. %s)' % (
                        int(total[2]),
                        stock_total,
                        )

            # Add total line:    
            res.append(('T', total))                
        return res

    def get_object_grouped_line(self, data):
        ''' Moved in sale.order: Selected object + print object 
        ''' 
        return self.pool.get(
            'sale.order')._report_procurement_grouped_get_objects(
                self.cr, self.uid, data=data)

    def get_object_grouped_family_line(self, data):
        ''' Selected object + print object
        '''
        # TODO Move in sale.order?
        def clean_number(value):
            return ('%s' % value).replace('.', ',')
        
        # Loop on order:
        fathers = {}
        browse_line = self.browse_order_line(data)
        self.order_ids = [] # list of order interessed from movement

        # Manage partial code
        code_from = int(data.get('code_from', 1))
        code_partial = data.get('code_partial', '')
        #families = {} # Database for family
 
        record_select = data.get('record_select', 'all')
        only_remain = record_select != 'all'
       
        if code_partial:
            from_partial = code_from - 1
            to_partial = from_partial + len(code_partial)

        for line in browse_line:
            # First test for speed up: added 17 giu 2016
            if only_remain and line.mx_closed:
                _logger.info('Jump only remain: line is closed')
                continue # jump if no item or all produced

            default_code = line.product_id.default_code
            if not default_code:
                raise osv.except_osv(
                    'Data error', 
                    'Default code not found: %s\n' % (
                        line.product_id.name))                        
                
            # Filter for partial:.
            if code_partial and default_code[
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

            # XXX Put in first test:
            #if only_remain and ( # added 17 giu 2016
            #        line.mx_closed or mrp_remain <= 0):
            #    _logger.info('Jump only remain: mrp_remain: %s' % (
            #        mrp_remain))
            #    continue # jump if no item or all produced
            family = line.product_id.family_id.name or _('???')
            father = default_code[:3]
            key = (family, father)
            if TOT == 0:
                continue
            
            if line.order_id.id not in self.order_ids:
                self.order_ids.append(line.order_id.id)
                
            if key not in fathers:
                fathers[key] = []
            fathers[key].append(line)
        
        # create a res order by product parent
        res = []
        fathers_list = sorted(fathers)
        last_family = False
        family_total = [0, 0, 0]

        for key in fathers_list:
            family, father = key
            if last_family == False: 
                last_family = family
            elif last_family != family:
                # Save previous code
                res.append(('T', last_family, family_total))
                last_family = family
                family_total = [0, 0, 0]
                
            total = [0, 0, 0]
            # Add product line:
            for line in fathers[key]:
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
                family_total[0] += S
                family_total[1] += B
                family_total[2] += TOT

            # Add total line:    
            res.append(('L', father, total))                
        
        # last record_
        if last_family:
            res.append(('T', last_family, family_total))
        return res

    def get_orders_selected(self):
        ''' Moved in sale.order function            
        '''
        # TODO used also in other reports?
        return self.pool.get(
            'sale.order')._report_procurement_get_orders_selected(
                self.cr, self.uid)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
