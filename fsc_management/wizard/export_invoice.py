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

    # ---------------------------------------------------------------------
    # Utility:
    # ---------------------------------------------------------------------
    def xls_write_row(self, WS, row, row_data, format_cell):
        ''' Print line in XLS file            
        '''
        ''' Write line in excel file
        '''
        col = 0
        for item in row_data:
            WS.write(row, col, item, format_cell)
            col += 1
        return True

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------    
    def action_print_registry(self, cr, uid, ids, context=None):
        ''' Event for button registry
        '''
        def get_extra_data(report, text):
            ''' Extra text depend in report mode
            ''' 
            if report == 'fsc':
                if text == 'material':
                    return u'' # TODO 
                elif text == 'type':
                    return u'' # TODO 
            else: # pefc
                if text == 'material':
                    return u'Robina Pseudoacacia'
                elif text == 'type':
                    return u'09012 Garden Furnitures'
            return 'ERR'


        if context is None: 
            context = {}
        
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        invoice_pool = self.pool.get('account.invoice')
        
        # Read parameters:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Export XLSX file:
        # ---------------------------------------------------------------------
        WS_name = {
            'fsc': 'FSC',
            'pefc': 'PEFC',            
            }
        excel_pool.create_worksheet(WS_name['fsc'])
        excel_pool.create_worksheet(WS_name['pefc'])

        # ---------------------------------------------------------------------
        # Format:
        # ---------------------------------------------------------------------
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        format_number = excel_pool.get_format('number')
        
        # ---------------------------------------------------------------------
        # Column dimension:
        # ---------------------------------------------------------------------
        col_width = (50, 18, 18, 18, 10, 30, 20, 20, 20, 20, 40, 10, 10)
        excel_pool.column_width(WS_name['fsc'], col_width)
        excel_pool.column_width(WS_name['pefc'], col_width)

        # ---------------------------------------------------------------------
        #                               Export Header:
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        # Row 1
        # ---------------------------------------------------------------------
        row = {
            'fsc': 0,
            'pefc': 0,
            }
        header = [u'PRODUZIONE / VENDITE', '', '', '', '', '', '', '', '',
            '', '', '', '']
        excel_pool.write_xls_line(
            WS_name['fsc'], row['fsc'], header, format_header)        
        excel_pool.write_xls_line(
            WS_name['pefc'], row['pefc'], header, format_header)
        # Merge cells:
        excel_pool.merge_cell(
            WS_name['fsc'], [row['fsc'], 0, row['fsc'], 12])
        excel_pool.merge_cell(
            WS_name['pefc'], [row['pefc'], 0, row['pefc'], 12])

        # ---------------------------------------------------------------------
        # Row 2
        # ---------------------------------------------------------------------
        row['fsc'] += 1
        row['pefc'] += 1
        header = [
            'CLIENTE', 'DETTAGLI FATTURE VENDITE', '', '', '', '',
            'CODIFICA PRODOTTI', '', '', '', '', '', '']
        # Merge cells:
        excel_pool.merge_cell(
            WS_name['fsc'], [row['fsc'], 0, row['fsc'] +1, 0])
        excel_pool.merge_cell(
            WS_name['pefc'], [row['pefc'], 0, row['pefc'] +1, 0])
        excel_pool.merge_cell(
            WS_name['fsc'], [row['fsc'], 1,row['fsc'], 5])
        excel_pool.merge_cell(
            WS_name['pefc'], [row['pefc'], 1, row['pefc'], 5])
        excel_pool.merge_cell(
            WS_name['fsc'], [row['fsc'], 6, row['fsc'], 12])
        excel_pool.merge_cell(
            WS_name['pefc'], [row['pefc'], 6, row['pefc'], 12])
        # Write data:
        excel_pool.write_xls_line(
            WS_name['fsc'], row['fsc'], header, format_header)        
        excel_pool.write_xls_line(
            WS_name['pefc'], row['pefc'], header, format_header)        

        # ---------------------------------------------------------------------
        # Row 3
        # ---------------------------------------------------------------------
        row['fsc'] += 1
        row['pefc'] += 1
        header = [
            _(u''),

            _(u'N. Ordine Fiam'),
            _(u'N. Ordine Vendita'),
            _(u'N. Fattura Vendita'),
            _(u'Data'),
            _(u'Dichiarazione FSC'),
            
            _(u'Specie vegetali'),            
            _(u'Gruppo di Prodotto'),
            _(u'Codice Articolo Semilavorato da cui deriva'),
            _(u'Codice Articolo PF'),
            _(u'Descrizione'),
            _(u'Quantità'),            
            _(u'Un. di Mis.'),            
           ]
        # Write data:
        excel_pool.write_xls_line(
            WS_name['fsc'], row['fsc'], header, format_header)        
        header[5] = _(u'Dichiarazione PEFC')
        excel_pool.write_xls_line(
            WS_name['pefc'], row['pefc'], header, format_header)        
        
        # ---------------------------------------------------------------------
        # Export data:
        # ---------------------------------------------------------------------
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
        _logger.info('Domain for search: %s [Tot: %s]' % (
            domain, len(account_ids)))

        bom = {}
        total = {
            'fsc': {},
            'pefc': {},                        
            }
        for invoice in invoice_pool.browse(
                cr, uid, account_ids, context=context):
            for line in invoice.invoice_line:
                # Check FSC or PEFC
                product = line.product_id
                fsc = product.fsc_certified_id
                pefc = product.pefc_certified_id
                if not fsc and not pefc:
                    continue

                if product not in bom: 
                    bom[product] = {
                        'fsc': [],
                        'pefc': [],
                        }                        
                    for component in product.dynamic_bom_line_ids:
                        cmpt_product = component.product_id
                        if cmpt_product.fsc_certified_id:
                            bom[product]['fsc'].append(component)
                            _logger.info(
                                'FSC: %s' % component.product_id.default_code)# XXX
                        if cmpt_product.pefc_certified_id:
                            bom[product]['pefc'].append(component)
                            _logger.info(
                                'PEFC: %s' % component.product_id.default_code)# XXX

                data = [
                    invoice.partner_id.name,
                    '',
                    '',
                    invoice.number,
                    invoice.date_invoice, 
                    '', # 5. fsc / pefc
                    '', # Material 
                    '', # Type
                    product.default_code, # TODO HW change if component
                    product.default_code,
                    product.name,
                    [line.quantity, format_number],
                    'pezzi',
                    ]

                # Cert dependent data:
                if fsc:
                    report = 'fsc'
                    data[5] = product.fsc_certified_id.name
                else: # PEFC
                    report = 'pefc'
                    data[5] = product.pefc_certified_id.name

                # Extra text:
                data[6] = get_extra_data(report, 'material')
                data[7] = get_extra_data(report, 'type')
                # TODO need in the loop for FSC depent on product? 

                if bom[product][report]: # With BOM:
                    for component in bom[product][report]:
                        row[report] += 1
                        data[8] = component.product_id.default_code
                        data[11][0] = line.quantity * component.product_qty
                        excel_pool.write_xls_line(
                            WS_name[report], row[report], data, 
                            format_text)
                        if component.product_id in total[report]:
                             total[report][component.product_id] += data[11][0]
                        else:    
                            total[report][component.product_id] = data[11][0]
                            
                else: # Without BOM (direct sale):
                    row[report] += 1
                    excel_pool.write_xls_line(
                        WS_name[report], row[report], data, format_text)
                    if product in total[report]: 
                         total[report][product] += data[11][0]
                    else:    
                         total[report][product] = data[11][0]
        _logger.info('Totals: PEFC %s  FSC %s' % (row['pefc'], row['fsc']))

        # ---------------------------------------------------------------------
        # Total block:
        # ---------------------------------------------------------------------
        col = 5 # move 4 col right

        row['pefc'] += 3
        row['fsc'] += 3
        header = [
            _(u'Gruppo di Prodotto'),
            _(u'Dichiarazione FSC'),
            _(u'Specie vegetali'),            
            _(u'Codice Articolo Semilavorato da cui deriva'),
            _(u'Descrizione'),
            _(u'Quantità venduta'),            
            _(u'Giacenza magazzino'),
            _(u'Un. di Mis.'),            
           ]           
        # Write data:
        excel_pool.write_xls_line(
            WS_name['fsc'], row['fsc'], header, format_header, col=col)
        header[1] = _(u'Dichiarazione PEFC')
        excel_pool.write_xls_line(
            WS_name['pefc'], row['pefc'], header, format_header, col=col)
        
        for report in total:
            for component in sorted(
                    total[report], key=lambda p: p.default_code):            
                row[report] += 1

                data = [
                    get_extra_data(report, 'type'),                    
                    component.__getattribute__(
                        '%s_certified_id' % report).name,
                    get_extra_data(report, 'material'),
                    component.default_code,
                    component.name,
                    (total[report][component], format_number),
                    '',
                    'PZ',
                    ]

                excel_pool.write_xls_line(
                    WS_name[report], row[report], data, format_text, col=col)

        return excel_pool.return_attachment(
            cr, uid, 'registry.xlsx', context=context)

    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''

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
            _('Prodotto'),
            _('Nome'),
            _('Certif.'),
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
            WS.set_column(10, 10, 10)
        
        # Export Header:
        self.xls_write_row(WS_fsc, 0, header, format_title)        
        self.xls_write_row(WS_pefc, 0, header, format_title)        
        
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
        _logger.info('Domain for search: %s [Tot: %s]' % (
            domain, len(account_ids)))
        i_fsc = 0
        i_pefc = 0
        for invoice in invoice_pool.browse(
                cr, uid, account_ids, context=context):
            for line in invoice.invoice_line:    
                # Check FSC or PEFC
                product = line.product_id
                fsc = product.fsc_certified_id
                pefc = product.pefc_certified_id
                if not fsc and not pefc:
                    continue
                    
                data = [
                    invoice.partner_id.name,
                    invoice.number,
                    invoice.date_invoice, 
                    product.default_code,
                    product.name,
                    False,
                    line.quantity,
                    line.price_unit,
                    line.multi_discount_rates or '',
                    line.price_subtotal,
                    ]
                if fsc:
                    i_fsc += 1
                    data[5] = product.fsc_certified_id.name
                    self.xls_write_row(WS_fsc, i_fsc, data, format_text)
                else: # pefc
                    i_pefc += 1
                    data[5] = product.pefc_certified_id.name
                    self.xls_write_row(WS_pefc, i_pefc, data, format_text)

        _logger.info('Totals: PEFC %s  FSC %s' % (i_pefc, i_fsc))
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
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }   

    def action_print_bf(self, cr, uid, ids, context=None):
        ''' Event for button done for BF
        '''
        if context is None: 
            context = {}
        
        # Pool used:
        pick_pool = self.pool.get('stock.picking')
        
        # Read parameters:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        partner_id = wiz_browse.partner_id.id
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Export XLSX file:
        # ---------------------------------------------------------------------
        xls_filename = '/tmp/fsc_pefc_report_bf.xlsx'
        _logger.info('Start FSC and PEFC invoice export BF: %s' % xls_filename)
        
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
            _('BF'),
            _('Data'),
            _('Prodotto'),
            _('Nome'),
            _('Certif.'),
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
            WS.set_column(10, 10, 10)
        
        # Export Header:
        self.xls_write_row(WS_fsc, 0, header, format_title)        
        self.xls_write_row(WS_pefc, 0, header, format_title)        
        
        # Export data:
        order = 'date'
        domain = [
            ('bf_number', 'ilike', 'BF'),
            ('state', 'in', ('done', )),
            ]
        if partner_id:
            domain.append(('partner_id', '=', partner_id))
        if from_date:
            domain.append(('date', '>=', from_date))
        if to_date:     
            domain.append(('date', '<=', to_date))
        pick_ids = pick_pool.search(
            cr, uid, domain, order=order, context=context)        
        _logger.info('Domain for search: %s [Tot: %s]' % (
            domain, len(pick_ids)))
        i_fsc = 0
        i_pefc = 0

        for pick in pick_pool.browse(
                cr, uid, pick_ids, context=context):
            for line in pick.move_lines:
                # Check FSC or PEFC
                product = line.product_id
                fsc = product.fsc_certified_id
                pefc = product.pefc_certified_id
                if not fsc and not pefc:
                    continue
                    
                data = [
                    pick.partner_id.name,
                    pick.bf_number,#pick.name,
                    pick.date, 
                    product.default_code,
                    product.name,
                    False,
                    line.product_uom_qty,
                    '', # line.price_unit,
                    '', # line.multi_discount_rates or '',
                    '', # line.price_subtotal,
                    ]
                if fsc:
                    i_fsc += 1
                    data[5] = product.fsc_certified_id.name
                    self.xls_write_row(WS_fsc, i_fsc, data, format_text)
                else: # pefc
                    i_pefc += 1
                    data[5] = product.pefc_certified_id.name
                    self.xls_write_row(WS_pefc, i_pefc, data, format_text)
        _logger.info('Totals: PEFC %s  FSC %s' % (i_pefc, i_fsc))
        _logger.info('End FIDO BF export on %s' % xls_filename)
        WB.close()

        attachment_pool = self.pool.get('ir.attachment')
        b64 = open(xls_filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'FIDO BF report',
            'datas_fname': 'fsc_pefc_invoice_report_bf.xlsx',
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

    def action_print_inventory(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        
        # ---------------------------------------------------------------------
        # Export XLSX file:
        # ---------------------------------------------------------------------
        xls_filename = '/tmp/fsc_pefc_inventory_report.xlsx'
        _logger.info(
            'Start FSC and PEFC inventory export on %s' % xls_filename)
        
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
            _('Codice'),
            _('Nome'),
            _('Commento'),
            _('Disponibilità'),
           ]

        # Column dimension:
        for WS in (WS_fsc, WS_pefc):
            WS.set_column(0, 0, 12)
            WS.set_column(1, 1, 40)
            WS.set_column(1, 1, 30)
            WS.set_column(2, 2, 8)
        
        # Export Header:
        self.xls_write_row(WS_fsc, 0, header, format_title)        
        self.xls_write_row(WS_pefc, 0, header, format_title)        
        
        # Export data:
        product_ids = product_pool.search(cr, uid, ['|', 
                ('fsc_certified_id', '!=', False),
                ('pefc_certified_id', '!=', False),                
                ], order='default_code', context=context)
                
        _logger.info('Product find: [Tot: %s]' % len(product_ids))
        i_fsc = 0
        i_pefc = 0
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            data = [
                product.default_code,
                product.name,
                False, # TODO replace (depend on certification)
                product.mx_net_mrp_qty, 
                ]

            if product.fsc_certified_id:
                i_fsc += 1
                data[2] = product.fsc_certified_id.name
                self.xls_write_row(WS_fsc, i_fsc, data, format_text)
                
            if product.pefc_certified_id:                    
                i_pefc += 1
                data[2] = product.pefc_certified_id.name                
                self.xls_write_row(WS_pefc, i_pefc, data, format_text)

        _logger.info('Totals: PEFC %s  FSC %s' % (i_pefc, i_fsc))
        _logger.info('End inventory file export on %s' % xls_filename)
        WB.close()

        attachment_pool = self.pool.get('ir.attachment')
        b64 = open(xls_filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Wood Cert. inventory report',
            'datas_fname': 'fsc_pefc_inventory_report.xlsx',
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

    _columns = {
        'partner_id': fields.many2one(
            'res.partner', 'Partner'),
        'from_date': fields.date('From date'),    
        'to_date': fields.date('To date'),    
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


