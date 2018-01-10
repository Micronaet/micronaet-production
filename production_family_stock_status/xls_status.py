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
import xlsxwriter
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


class ProductTemplate(orm.Model):
    """ Add button report event
    """
    
    _inherit = 'product.template'

    def template_print_family_stock_status(self, cr, uid, ids, context=None):
        ''' Print current family status XLSX report
        '''    
        
        # ---------------------------------------------------------------------
        #                           Excel file:
        # ---------------------------------------------------------------------
        # A. Create file:
        filename = '/tmp/family_stock_status_report_%s.xlsx' % ids[0]
        _logger.info('Start report status for family Temp file: %s' % filename)
        WB = xlsxwriter.Workbook(filename)
        
        # B. Format class:
        num_format = '#,##0'
        xls_format = {
            'title' : WB.add_format({
                'bold': True, 
                'font_name': 'Courier 10 pitch', # 'Arial'
                'font_size': 10,
                'align': 'left',
                }),
            'header': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'font_name': 'Courier 10 pitch', # 'Arial'
                'font_size': 9,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#cfcfcf', # gray
                'border': 1,
                #'text_wrap': True,
                }),
            'merge': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'font_name': 'Courier 10 pitch', # 'Arial'
                'font_size': 10,
                'align': 'center',
                #'vertical_align': 'center',
                'valign': 'vcenter',
                #'bg_color': '#cfcfcf', # gray
                'border': 1,
                }),
            'text': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                #'align': 'left',
                'border': 1,
                }),
            'text_number': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                }),
            'text_today': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                #'align': 'right',
                'border': 1,
                'bg_color': '#e6ffe6',
                }),
            'text_number_today': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'bg_color': '#e6ffe6',
                }),
            'text_number_total': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                #'bg_color': '#e6ffe6',
                }),
            'text_total': WB.add_format({
                'font_color': 'blue',
                'bold': True,
                'font_name': 'Courier 10 pitch',
                'font_size': 10,
                'align': 'right',
                'border': 1,
                }),
            'text_total_today': WB.add_format({
                'font_color': 'blue',
                'bold': True,
                'font_name': 'Courier 10 pitch',
                'font_size': 10,
                'align': 'right',
                'border': 1,
                'bg_color': '#e6ffe6',
                }),
            'text_center': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'center',
                'border': 1,
                
                }),
            'bg_red': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'bg_color': '#ff420e',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'left',
                'border': 1,
                }),
            'text_black': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'left',
                'border': 1,
                'text_wrap': True
                }),
            'number_total': WB.add_format({
                'bold': True, 
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'bg_color': '#DDDDDD',
                'border': 1,
                'num_format': num_format,
                }),
            }
            
        # ---------------------------------------------------------------------
        #               EXCEL: Product status component
        # ---------------------------------------------------------------------
        # Create WS: 
        WS = {
            'raw': [WB.add_worksheet('Stato componenti'), 1, {}],
            'hw': [WB.add_worksheet('Stato semilavorati'), 1, {}],
            'product': [WB.add_worksheet('Prodotti'), 1, {}],
            }

        # Setup columns:
        WS['raw'][0].set_column('A:C', 12)
        WS['raw'][0].set_column('B:B', 25)
        WS['raw'][0].set_column('D:D', 50)
        
        WS['hw'][0].set_column('A:C', 12)
        WS['hw'][0].set_column('B:B', 25)
        WS['hw'][0].set_column('D:D', 50)

        WS['product'][0].set_column('A:C', 12)
        WS['product'][0].set_column('B:B', 25)

        # Header:
        row = 0
        WS['raw'][0].write(row, 0, 'Codice', xls_format['header'])
        WS['raw'][0].write(row, 1, 'Nome', xls_format['header'])
        WS['raw'][0].write(row, 2, 'Netto', xls_format['header'])
        WS['raw'][0].write(row, 3, 'Lordo', xls_format['header'])
        WS['raw'][0].write(row, 4, 'Presenza', xls_format['header'])
        #WS['component'][0].write(row, 1, 'Future', xls_format['title'])

        WS['hw'][0].write(row, 0, 'Codice', xls_format['header'])
        WS['hw'][0].write(row, 1, 'Nome', xls_format['header'])
        WS['hw'][0].write(row, 2, 'Netto', xls_format['header'])
        WS['hw'][0].write(row, 3, 'Lordo', xls_format['header'])
        WS['hw'][0].write(row, 4, 'Presenza', xls_format['header'])
        #WS['component'][0].write(row, 1, 'Future', xls_format['title'])

        WS['product'][0].write(row, 0, 'Codice', xls_format['header'])
        WS['product'][0].write(row, 1, 'Nome', xls_format['header'])
        WS['product'][0].write(row, 2, 'Netto', xls_format['header'])
        WS['product'][0].write(row, 3, 'Lordo', xls_format['header'])
        #WS['component'][0].write(row, 1, 'Future', xls_format['title'])
                
        # ---------------------------------------------------------------------
        # Collect data:        
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')
        attachment_pool = self.pool.get('ir.attachment')
        product_ids = product_pool.search(cr, uid, [
            ('family_id', '=', ids[0]),
            ], context=None)

        # Database:
        raws = WS['raw'][2] # Level 1 and 2 raw material
        hws = WS['hw'][2] # Level 1 HW only
        products = WS['product'][2] # List of product
        
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):                
                
            if product not in products:
                products[product] = False # not used
                
            # XXX No dynamic bom in product is error         
            for l1 in product.dynamic_bom_line_ids:
                product_l1 = l1.product_id
                half_bom_ids = product_l1.half_bom_ids # Has HW BOM?
                
                if half_bom_ids: # is HW level 1 element
                    if product_l1 not in hws:
                        hws[product_l1] = []
                    hws[product_l1].append(product) # product precence
                        
                    for l2 in half_bom_ids: # Loop raw material level 2
                        product_l2 = l2.product_id
                        
                        if product_l2 not in raws:
                            raws[product_l2] = []
                        raws[product_l2].append(product)    

                else: # Is raw material level 1 element
                    if product_l1 not in raws:
                        raws[product_l1] = []
                    raws[product_l1].append(product)    
                        
                        
        cell_format = xls_format['text']
        for block in WS:
            table = sorted(WS[block][2], key=lambda x: x.default_code)
            for product in table:
                row = WS[block][1] # read current row
                WS[block][1] += 1                
                WS[block][0].write(row, 0, product.default_code, cell_format)
                WS[block][0].write(row, 1, product.name, cell_format)
                WS[block][0].write(row, 2, product.mx_net_mrp_qty, cell_format)
                WS[block][0].write(row, 3, product.mx_lord_qty, cell_format)
                if table[product]: # Write precence:
                    text = '%s' % ([p.default_code for p in sorted(
                        table[product]], key=lambda x: x.default_code), )
                    WS[block][0].write(row, 4, text, cell_format)                    
        WB.close()
        
        # Return XLSX file:       
        b64 = open(filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Stato magazzino famiglia',
            'datas_fname': 'Stato_magazzino_famiglia_selezionata.xlsx',
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
