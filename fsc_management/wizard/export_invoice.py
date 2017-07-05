# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################


import os
import sys
import logging
import openerp
import xlsxwriter
import openerp.addons.decimal_precision as dp
from calendar import monthrange
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class ExportXlsxFscReportWizard(orm.TransientModel):
    ''' Wizard export invoice data
    '''
    _name = 'export.xlsx.fsc.report.wizard'

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------    
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def xls_write_row(WS, row, row_data, format_cell):
            ''' Print line in XLS file            
            '''
            ''' Write line in excel file
            '''
            col = 0
            for item in row_data:
                WS.write(row, col, item, format_cell)
                col += 1
            return True

        if context is None: 
            context = {}
        
        # Pool used:
        invoice_pool = self.pool.get('account.invoice')
        
        # Read parameters:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Export XLSX file:
        # ---------------------------------------------------------------------
        xls_filename = '/tmp/fsc_pefc_report.xlsx'
        _logger.info('Start FSC and PEFC invoice export on %s' % xls_filename)
        
        # Open file and write header
        WB = xlsxwriter.Workbook(xls_filename)
        WS_fsc = WB.add_worksheet(_('FSC'))
        WS_pefc = WB.add_worksheet(_('PEFC'))

        # Format:
        format_title = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': 'gray',
            'border': 1,
            'text_wrap': True,
            })

        format_text = WB.add_format({
            'font_name': 'Arial',
            'font_size': 9,
            #'align': 'right',
            #'bg_color': 'c1e7b3',
            'border': 1,
            #'num_format': '0.00',
            })        
        
        header = [
            _('Cliente'),
            _('Fattura'),
            _('Data'),
            _('Product'),
            _('Name'),
            _('Q.'),
            _('Price'),
            _('Discount'),            
            _('Subtotal'),            
           ]

        # Column dimension:
        for WS in (WS_fsc, WS_pefc):
            WS.set_column(0, 0, 40)
            WS.set_column(1, 1, 12)
            WS.set_column(2, 2, 8)
            WS.set_column(3, 3, 11)
            WS.set_column(4, 4, 35)
            WS.set_column(6, 6, 10)
            WS.set_column(7, 7, 10)
            WS.set_column(8, 8, 10)
            WS.set_column(9, 9, 10)
        
        # Export Header:
        xls_write_row(WS_fsc, 0, header, format_title)        
        xls_write_row(WS_pefc, 0, header, format_title)        
        
        # Export data:
        order = 'number'
        domain = [('state', 'in', ('open', 'paid'))]
        if partner_id:
            domain.append(('partner_id', '=', partner_id))
        if from_date:
            domain.append(('date_invoice', '>=', from_date))
        if to_date:     
            domain.append(('date_invoice', '<=', to_date))

        account_ids = invoice_pool.search(
            cr, uid, domain, order=order, context=context)        
        i = 0
        for invoice in invoice_pool.browse(
                cr, uid, account_ids, context=context):
            for line in invoice.invoice_line:    
                # Check FSC or PEFC
                i += 1
                product = line.product_id
                fsc = product.fsc_certified
                pefc = product.pefc_certified
                if not fsc and not pefc:
                    continue
                    
                data = [
                    invoice.partner_id.name,
                    invoice.number,
                    invoice.date_invoice, 
                    product.default_code,
                    product.name,
                    line.quantity,
                    line.price_unit,
                    line.multi_discount_rates or '',
                    line.price_subtotal,
                    ]
                if fsc:
                    xls_write_row(WS_fsc, i, data, format_text)
                else:    
                    xls_write_row(WS_pefc, i, data, format_text)

        _logger.info('End FIDO invoice export on %s' % xls_filename)
        WB.close()

        attachment_pool = self.pool.get('ir.attachment')
        b64 = open(xls_filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'FIDO invoice report',
            'datas_fname': 'fsc_pefc_invoice_report.xlsx',
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model':'res.partner',
            'res_id': 1,
            }, context=context)
        
        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }   

    _columns = {
        'partner_id': fields.many2one(
            'res.partner', 'Partner'),
        'from_date': fields.date('From date'),    
        'to_date': fields.date('To date'),    
        }
        
    _defaults = {
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


