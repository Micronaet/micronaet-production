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
            
            'get_object_with_total': self.get_object_with_total,
            'get_object_with_total_cut': self.get_object_with_total_cut,
            'get_pre_production': self.get_pre_production,
            'get_frames': self.get_frames,
            
            # remain report:
            'get_object_remain': self.get_object_remain,
            'previous_record': self.previous_record,
            'clean_order': self.clean_order,
        })

    def get_pre_production(self):
        ''' List of family with order to do and order planned (open)
        '''
        res = {}
        mrp_pool = self.pool.get('mrp.production')
        sol_pool = self.pool.get('sale.order.line')

        # ---------------------------------------------------------------------
        # Read open productions:
        # ---------------------------------------------------------------------
        mrp_family = {}
        mrp_ids = mrp_pool.search(self.cr, self.uid, [
            ('state','not in', ('cancel', 'done'))])
            
        for mrp in mrp_pool.browse(self.cr, self.uid, mrp_ids):
            family_id = mrp.product_id.id
            # bom_id.product_tmpll_id
            if family_id not in mrp_family:
                mrp_family[family_id] = [0.0, 0.0] # OC, Done
                            
            for line in mrp.order_line_ids:
                mrp_family[family_id][0] += line.product_uom_qty
                mrp_family[family_id][1] += line.product_uom_maked_sync_qty
            
        # ---------------------------------------------------------------------
        # Open line not linked:
        # ---------------------------------------------------------------------
        sol_ids = sol_pool.search(self.cr, self.uid, [
            ('mrp_id', '=', False),
            ('pricelist_order', '=', False),
            ('go_in_production', '=', True),
            ('is_manufactured', '=', True),
            ('mx_closed', '=', False),
            ])
        
        for line in sol_pool.browse(self.cr, self.uid, sol_ids):
            family = line.product_id.family_id 
            if family in res:
                res[family][1] += line.product_uom_qty
                res[family][2] += line.product_uom_maked_sync_qty                
            else:
                res[family] = [
                    family.name,
                    line.product_uom_qty,
                    line.product_uom_maked_sync_qty,
                    line.mrp_similar_info,
                    line.mrp_similar_total,
                    mrp_family.get(family.id, [0.0, 0.0]), 
                    ]
        r = [res[k] for k in res]      
        return sorted(r)            

    def clean_order(self, name):
        ''' Clean order:
        '''
        try:
            if name.startswith('MX'):
                return name.split('-')[-1].split('/')[0]
            else:    
                return name.split('/')[-1]
        except:
            return name        
            

    def previous_record(self, value=False):
        ''' Save passed value as previouse record
            value: 'init' for setup first False record
                   data for set up this record
                   Nothing for get element
        '''
        if value == 'init':
            self.previous_record_value = False            
            return ''
        if value: # set operation
            self.previous_record_value = value
            return '' 
        else: # get operation
            return self.previous_record_value 

    def get_date(self, ):
        ''' For report time
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def get_frames(self, ):    
        ''' Return frames object:
        '''
        return self.frames

    def get_object_with_total_cut(self, o):
        ''' Get object with totals for normal report
            Sort for [4:6]-[9:12]
            Break on 2 block for total
        '''
        lines = []
        for line in sorted(
                o.order_line_ids, 
                key=lambda item: (
                    item.product_id.default_code[3:6], 
                    item.product_id.default_code[8:12], 
                    item.product_id.default_code[0:3],
                    )):
            lines.append(line)
        print lines

        # Total for code break:
        code1 = code2 = False
        total1 = total2 = 0.0
        records = []

        self.frames = {}
        for line in lines:
            # -------------
            # Check Frames:
            # -------------
            # France total:
            frame = line.default_code.replace(' ', '.')[6:8]
            if frame not in self.frames:
                self.frames[frame] = 0.0
            self.frames[frame] += line.product_uom_qty
            
            # -----------------
            # Check for totals:
            # -----------------
            # Color total:
            color = line.default_code[8:12].rstrip()
            if code1 == False: # XXX first loop
                total1 = 0.0
                code1 = color
                
            if code1 == color:
                total1 += line.product_uom_qty
            else:
                code1 = color
                records.append(('T1', line, total1))
                total1 = line.product_uom_qty

            # Code general total:
            if code2 == False: # XXX first loop
                total2 = 0.0
                code2 = line.default_code
                
            if code2 == line.default_code:
                total2 += line.product_uom_qty
            else: 
                code2 = line.default_code
                records.append(('T2', line, total2))
                total2 = line.product_uom_qty

            # -------------------
            # Append record line:
            # -------------------
            records.append(('L', line, False))

        # Append last totals if there's records:
        if records:                
            records.append(('T1', line, total1))
            records.append(('T2', line, total2))
        return records

    def get_object_with_total(self, o, data=None):
        ''' Get object with totals for normal report
        '''
        if data is None:
            data = {}
        mode = data.get('mode', 'clean')    
        
        lines = []
        for line in o.sort_order_line_ids: # jet ordered:
            lines.append(line)

        # Total for code break:
        code1 = code2 = False
        total1 = total2 = 0.0
        records = []

        self.frames = {}
        old_line = False
        for line in lines:
            # Variable:
            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty            
            default_code = line.default_code
            
            if mode == 'clean': # remove delivered qty (OC and Maked)
                delivered_qty = line.delivered_qty
                product_uom_qty -= delivered_qty
                product_uom_maked_sync_qty -= delivered_qty
                if not product_uom_qty:
                    continue # jump empty line
                    
                if product_uom_maked_sync_qty < 0: # remain 0 if negative
                    product_uom_maked_sync_qty = 0.0
                elif product_uom_maked_sync_qty > 0: # clean ordered with done
                    product_uom_qty -= product_uom_maked_sync_qty
                    if not product_uom_qty:
                        continue # jump empty line
                    product_uom_maked_sync_qty = 0.0                    
            
            # -------------
            # Check Frames:
            # -------------
            # Frames total:
            frame = default_code.replace(' ', '.')[6:8]
            if frame not in self.frames:
                self.frames[frame] = 0.0
            self.frames[frame] += product_uom_qty
            
            # -----------------
            # Check for totals:
            # -----------------
            # Color total:
            color = default_code[8:12].rstrip()
            if code1 == False: # XXX first loop
                total1 = 0.0
                code1 = color
                
            if code1 == color:
                total1 += product_uom_qty
            else:
                code1 = color
                records.append(('T1', old_line, total1))
                total1 = product_uom_qty

            # Code general total:
            if code2 == False: # XXX first loop
                total2 = 0.0
                code2 = default_code
                
            if code2 == default_code:
                total2 += product_uom_qty
            else: 
                code2 = default_code
                records.append(('T2', old_line, total2))
                total2 = product_uom_qty

            # -------------------
            # Append record line:
            # -------------------
            records.append(
                ('L', line, (
                    product_uom_qty, product_uom_maked_sync_qty,
                    )))
            old_line = line

        # Append last totals if there's records:
        if records:                
            records.append(('T1', old_line, total1))
            records.append(('T2', old_line, total2))
            
        return records
        
    def get_object_remain(self, ):
        ''' Get as browse obj all record with unsync elements
        '''
        line_ids = self.pool.get('sale.order.line').search(self.cr, self.uid, [
            ('product_uom_maked_qty', '>', 0.0)], order='order_id')
        return self.pool.get('sale.order.line').browse(
            self.cr, self.uid, line_ids)

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
