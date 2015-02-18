# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import sys
import os
from openerp.osv import osv
from datetime import datetime, timedelta
from openerp.report import report_sxw
import logging, time
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)


# Global elements:
_logger = logging.getLogger(__name__)

class report_webkit_html(report_sxw.rml_parse):    
    def __init__(self, cr, uid, name, context):    
        # Set up private variables:
        self.rows = []
        self.cols = []
        self.minimum = {}
        self.table = {}
        self.error_in_print = ""

        super(report_webkit_html, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'cr': cr,
            'uid': uid,
            'start_up': self._start_up,
            'get_rows': self._get_rows,
            'get_cols': self._get_cols,
            'get_cel': self._get_cel,
            'has_negative': self._has_negative,
            'jump_is_all_zero': self._jump_is_all_zero,
        })

    def _has_negative(self, row, data=None):
        ''' ???
        '''
        return 
        
    def _jump_is_all_zero(self, row, data=None):
        ''' Test if line has all elements = 0 
            Response according with wizard filter
        '''
        if data is None:
            data = {}

            
        if data.get('active', False):  # only active lines?
            return not any(self.table[row]) # jump line (True)
        return False # write line

    def _start_up(self, data=None):
        ''' Master function for prepare report
        '''
        if data is None:
            data = {}
                    
        # initialize globals:
        self.rows = []
        self.cols = []
        self.minimum = {}
        self.table = {}
        self.error_in_print = "" # TODO manage for set printer
        
        lavoration_pool = self.pool.get("mrp.production.workcenter.line")
        
        # TODO optimize:
        product_pool = self.pool.get('product.product')        
        for product in product_pool.browse(
            self.cr, self.uid, product_pool.search(self.cr, self.uid, [])):
                 self.minimum[product.id] = product.minimum_qty or 0.0

        # Init parameters:
        col_ids = {}  
        range_date = data.get("days", 7) + 1
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days = range_date - 1)

        for i in range(0, range_date):        # 0 (<today), 1...n [today, today + total days], delta)
            if i == 0:                        # today
                d = start_date
                self.cols.append(d.strftime("%d/%m"))
                col_ids[d.strftime("%Y-%m-%d")] = 0
            elif i == 1:                      # before today
                d = start_date
                self.cols.append(d.strftime("< %d/%m")) 
                col_ids["before"] = 1         # not used!                    
            else:                             # other days
                d = start_date + timedelta(days = i - 1)
                self.cols.append(d.strftime("%d/%m"))
                col_ids[d.strftime("%Y-%m-%d")] = i

        # ---------------------------------------------------------------------
        #                   Get material list from Lavoration order
        # ---------------------------------------------------------------------
        # Populate cols
        lavoration_ids = lavoration_pool.search(self.cr, self.uid, [
            ('date_planned', '<=', end_date.strftime("%Y-%m-%d 23:59:59")),     # only < max date range
            ('state', 'not in', ('cancel','done'))] )                                # only open not canceled
        for lavoration in lavoration_pool.browse(self.cr, self.uid, lavoration_ids): # filtered BL orders
            # Read only lavoration with phase that unload material from stock
            if not lavoration.lavoration_id.phase_id.unload_material:
                continue
            # ----------------------------
            # Product in lavoration order:
            # ----------------------------
            element = ("P: %s [%s]" % (
                lavoration.product.name, 
                lavoration.product.code,
            ), lavoration.product.id)
            if element not in self.rows:
                # prepare data structure:
                self.rows.append(element)            
                self.table[element[1]] = [0.0 for item in range(0, range_date)]       
                self.table[element[1]][0] = lavoration.product.accounting_qty or 0.0

            if lavoration.date_planned[:10] in col_ids: # Product production
                self.table[element[1]][col_ids[lavoration.date_planned[:10]]] += lavoration.lavoration_qty or 0.0
            else: # < today  (element 1 - the second)
                self.table[element[1]][1] += lavoration.lavoration_qty or 0.0

            # ----------------
            # Material in BOM:
            # ----------------                  
            for material in lavoration.production_id.bom_id.bom_lines: #bom_material_ids:    
                if not material.product_id.show_in_status: # Jump "not in status" material
                    continue
                quantity = material.product_qty * lavoration.lavoration_qty
                #if with_medium and material.product_id:
                #    media = "%5.2f" % (material_mx.get(material.product_id.id, 0.0) / month_window / 1000) # t from Kg.
                #else:
                #    media = "??"
                media = "??"

                # Row element description:
                element=("M: %s [%s]%s" % (
                    material.product_id.name, 
                    material.product_id.default_code,
                    ' <b>%s t.</b>' % (media), ), material.product_id.id)
                if element not in self.rows:
                    self.rows.append(element)
                    self.table[element[1]] = [
                        0.0 for item in range(0,range_date)
                        ] # prepare data structure
                    self.table[element[1]][0] = material.product_id.accounting_qty or 0.0 # prepare data structure

                if lavoration.date_planned[:10] in col_ids:
                    self.table[element[1]][col_ids[lavoration.date_planned[:10]]] -= quantity or 0.0 
                else:    # < today
                    self.table[element[1]][1] -= quantity or 0.0 

        self.rows.sort()

        return True

    def _get_rows(self):
        ''' Rows list (generated by _start_up function)
        '''
        return self.rows

    def _get_cols(self):
        ''' Cols list (generated by _start_up function)
        '''
        return self.cols

    def _get_cel(self, col, row):
        ''' Cel value from col - row
            row=product_id
            col=n position
            return: (quantity, minimum value)
        '''
        # TODO get from table
        if row in self.table:
            return (self.table[row][col], self.minimum.get(row, 0.0))
        return (0.0, 0.0)

report_sxw.report_sxw(
    'report.webkitworkstatus',
    'mrp.production', 
    'addons/production_working_bom/report/status_work.mako',
    parser=report_webkit_html
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
