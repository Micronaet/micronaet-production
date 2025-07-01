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

class SaleOrderProcurementReportWizard(orm.TransientModel):
    """ Procurements depend on sale
    """
    _name = 'sale.order.procurement.report.wizard'
    _description = 'Sale produrement wizard'
    
    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def extract_report_grouped_in_excel(
            self, cr, uid, data=None, context=None):
        """ Extract XLSX mode for groupe report (used for frames)
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def write_xls_mrp_line(WS, row, line):
            """ Write line in excel file
            """
            col = 0
            for item, format_cell in line:
                WS.write(row, col, item, format_cell)
                col += 1
            return True

        # Create file:
        filename = '/tmp/production_status.xlsx'
        _logger.info('Start export status on %s' % filename)
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet(_('Frame'))

        # Format for cell:            
        num_format = '#,##0'
        format_title = WB.add_format({
            'bold': True, 
            'font_name': 'Courier 10 pitch', # 'Arial'
            'font_size': 11,
            'align': 'left',
            })
        format_header = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Courier 10 pitch', # 'Arial'
            'font_size': 9,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': 'gray',
            'border': 1,
            #'text_wrap': True,
            })
        format_text = WB.add_format({
            'font_color': 'black',
            'font_name': 'Courier 10 pitch',
            'font_size': 9,
            'align': 'left',
            #'bg_color': 'gray',
            'border': 1,
            #'text_wrap': True,
            })
        format_number = WB.add_format({
            'font_name': 'Courier 10 pitch',
            'font_size': 9,
            'align': 'right',
            #'bg_color': 'white',
            'border': 1,
            'num_format': num_format,
            })
        format_text_total = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Courier 10 pitch',
            'font_size': 9,
            'align': 'left',
            'bg_color': '#DDDDDD',
            'border': 1,
            #'text_wrap': True,
            })
        format_number_total = WB.add_format({
            'bold': True, 
            'font_name': 'Courier 10 pitch',
            'font_size': 9,
            'align': 'right',
            'bg_color': '#DDDDDD',
            'border': 1,
            'num_format': num_format,
            })
        
        # --------------------------------------------------------------------------------------------------------------
        #                     EXPORT EXCEL REPORT
        # --------------------------------------------------------------------------------------------------------------
        order_pool = self.pool.get('sale.order')
        attachment_pool = self.pool.get('ir.attachment')

        # Call parser function for get data:
        res, mrp_date_db = order_pool._report_procurement_grouped_get_objects(cr, uid, data=data, context=context)

        # ---------------------------------------------------------------------
        # Write header block:
        # ---------------------------------------------------------------------
        #WS.set_row(0, 20) # Row height
        WS.set_column ('A:A', 15) # Col width        
        WS.set_column ('E:E', 1) # Col width 

        # 0. Title of report:
        write_xls_mrp_line(WS, 0, [
            (_('REPORT APPROVVIGIONAMENTI SU ORDINATO'), format_title),
            ])

        # 3. Header line:    
        header = [
            (_('Item'), format_header),
            (_('TODO'), format_header),
            (_('Done'), format_header),
            (_('Total'), format_header),
            ('', format_header), # Empty col before MRP
            ]
            
        # Add header date:    
        get_col_date = {}
        pos = len(header)
        for date in mrp_date_db:
            get_col_date[date] = pos
            if not date:
                date = _('No date')
            header.append((date, format_header))
            pos += 1
        total_columns = pos # used for get max col
                
        write_xls_mrp_line(WS, 3, header)

        # 1. Filter applied:
        write_xls_mrp_line(WS, 1, [
            (_('Filtro: %s') % order_pool._report_procurement_get_filter_description(
                cr, uid, context=context), format_title),
            ])
            
        # --------------------------------------------------------------------------------------------------------------
        # Write body:
        # --------------------------------------------------------------------------------------------------------------
        i = 3 # Last line written

        mrp_total = {}
        for mode, key, line in res:
            i += 1
            if mode == 'L':
                body = [
                    (key, format_text),
                    (line[0], format_number),
                    (line[1], format_number),
                    (line[2], format_number),
                    ]
                # Add extra column for format border    
                body.extend([
                    ('', format_number) for c in range(0, total_columns - len(body))])
                        
                write_xls_mrp_line(WS, i, body)
                # Add directly extra total for date of MRP production
                for date in mrp_date_db:
                    if key in mrp_date_db[date]:
                        col = get_col_date[date]
                        S = mrp_date_db[date][key]
                        WS.write(i, col, S, format_number)
                        if col not in mrp_total:
                             mrp_total[col] = 0.0
                        mrp_total[col] += S

            elif mode == 'T':
                body = [
                    (_('Total fam. %s') % key, format_text_total),
                    (line[0], format_number_total),
                    (line[1], format_number_total),
                    (line[2], format_number_total),                    
                    ]
                # Add extra column for format border    
                body.extend([
                    ('', format_number_total) for c in range(0, total_columns - len(body))])
                write_xls_mrp_line(WS, i, body)
                
                # Write MRP totals:
                for col, S in mrp_total.iteritems():
                    WS.write(i, col, S, format_number_total)

                i += 1
                mrp_total = {}
        
        WB.close()
        _logger.info('End generation frame status report %s' % filename)

        # Creaet attachment for return XLSX file as download:
        b64 = open(filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Frame MRP status',
            'datas_fname': 'frame_mrp_status.xlsx',
            'type': 'binary',
            'datas': b64,
            #'partner_id': 1,
            'res_model':'res.partner',
            'res_id': 1,
            }, context=context)
        
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }   
        
    # --------------
    # Button events:
    # --------------
    def print_report(self, cr, uid, ids, context=None):
        """ Redirect to report passing parameters
        """

        wiz_proxy = self.browse(cr, uid, ids)[0]
            
        datas = {}
        datas['wizard'] = True # started from wizard
        datas['xlsx'] = False
        
        if wiz_proxy.report_type == 'detailed':
            report_name = 'mx_procurement_report' 
        elif wiz_proxy.report_type == 'grouped': # grouped
            report_name = 'mx_procurement_grouped_report' 
        elif wiz_proxy.report_type == 'family':
            report_name = 'mx_procurement_grouped_family_report' # TODO change
        else: 
            datas['xlsx'] = True # frame XLS mode
               
        datas['from_date'] = wiz_proxy.from_date or False
        datas['to_date'] = wiz_proxy.to_date or False
        datas['from_deadline'] = wiz_proxy.from_deadline or False
        datas['to_deadline'] = wiz_proxy.to_deadline or False

        datas['family_id'] = wiz_proxy.family_id.id or False
        datas['family_name'] = wiz_proxy.family_id.name or ''
        
        datas['code_start'] = wiz_proxy.code_start
        datas['code_partial'] = wiz_proxy.code_partial
        
        datas['no_forecast'] = wiz_proxy.no_forecast
        datas['with_extract_dimension'] = wiz_proxy.with_extract_dimension
        datas['code_from'] = wiz_proxy.code_from

        datas['record_select'] = wiz_proxy.record_select
        
        if datas['xlsx']: # Export in XLSX file 
            return self.extract_report_grouped_in_excel(
                cr, uid, data=datas, context=context)
        else: # Normal report:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': datas,
                }                

    _columns = {
        'report_type': fields.selection([
            ('detailed', 'Order in detail'),
            ('grouped', 'Order grouped by frame'),
            ('frame', 'Frame for color (XLSX)'),
            ('family', 'Order family grouped'),
            ], 'Report type', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'family_id': fields.many2one('product.template', 'Family', 
            domain=[('is_family', '=', True)]),
            
        'no_forecast':fields.boolean('No forecast'),
        'with_extract_dimension': fields.boolean('Estrai dimensione', 
            help='Estrae la dimensione dal nome e la mette nelle note'),
        'record_select': fields.selection([
            ('all', 'Tutti'),
            ('mrp', 'Rimanenti da produrre'),
            ('delivery', 'Rimanenti da consegnare'),
            ], 'Selezione record', required=True),
            
        'from_date': fields.date('From', help='Date >='),
        'to_date': fields.date('To', help='Date <'),
        'from_deadline': fields.date('From deadline', help='Date deadline >='),
        'to_deadline': fields.date('To deadline', help='Date deadline <='),

        # Code filter:
        'code_start': fields.char('Code start', size=20), 
        'code_partial': fields.char('Code partial', size=20), 

        # Group option:        
        'code_from': fields.integer('Code from char'), 
        }
        
    _defaults = {
        'report_type': lambda *x: 'detailed',
        'no_forecast': lambda *x: True,
        'record_select': lambda *x: 'all',
        
        #'to_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
