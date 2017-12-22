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

class MrpProductionStatsMixed(orm.Model):
    """ Send statistic from fields:
        'is_today': boolean 'Is today'
        'is_total': boolean 'Day total'
        
        'date_planned': date 'Date planned'
        'product_id': many2one 'product.product' 'Family'
        'production_id': many2one 'mrp.production' 'Production'
        'workcenter_id': many2one 'mrp.workcenter' 'Line' 
        'lavoration_qty': float 'Lavoration q.' 
        'hour': float 'Tot. H.'
        'workers': integer 'Workers'
        'startup': float 'Startup'
        
        # sale.order.line:
        # >>> 'todo_qty': float 'Total q.'
        'maked_qty': integer 'Done q.'
        # >>> 'remain_qty': float 'Remain q.'
    """
    
    _inherit = 'mrp.production.stats.mixed'
    
    # -------------------------------------------------------------------------
    # Scheduled actions:
    # -------------------------------------------------------------------------
    def scheduled_send_stats_report(self, cr, uid, context=None):
        ''' Send report to partner in group with dashboard statistics
        '''
        _logger.info('Start sending MRP report')
        
        # ---------------------------------------------------------------------
        #                  Collect stats data in database:
        # ---------------------------------------------------------------------
        res = {}
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        # TODO Collect data in res
        now_0 = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        now_9 = (datetime.now() - timedelta(days=9)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        stats_ids = self.search(cr, uid, [
            #('date_planned', '>=', now_9),
            #('date_planned', '<=', now_0),            
            ], context=context)
        for line in self.browse(cr, uid, stats_ids, context=context):
            if line.workcenter_id not in res:
                res[line.workcenter_id] = {}
            if line.date_planned not in res[line.workcenter_id]:
                res[line.workcenter_id][line.date_planned] = []
            res[line.workcenter_id][line.date_planned].append(line)
        
        # ---------------------------------------------------------------------
        #                           Excel file:
        # ---------------------------------------------------------------------
        # A. Create file:
        filename = '/tmp/send_stats_mrp_report.xlsx'
        _logger.info('Temp file: %s' % filename)        

        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Statistiche')
        
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
            'text_today': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                #'align': 'left',
                'border': 1,
                'bg_color': '#e6ffe6',
                }),
            'text_total': WB.add_format({
                'font_color': 'blue',
                'bold': True,
                'font_name': 'Courier 10 pitch',
                'font_size': 10,
                #'align': 'left',
                'border': 1,
                }),
            'text_total_today': WB.add_format({
                'font_color': 'blue',
                'bold': True,
                'font_name': 'Courier 10 pitch',
                'font_size': 10,
                #'align': 'left',
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
            
        # C. Prepare file layout:
        WS.set_column('A:A', 12)
        WS.set_column('B:D', 15)
        WS.set_column('E:H', 8)
        
        # ---------------------------------------------------------------------
        # Write data on file:
        # ---------------------------------------------------------------------
        # Write title row:
        row = 0
        WS.write(row, 0, 
            'Produzioni settimana passata, data rif.: %s' % now, 
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Linea'), xls_format['header'])
        WS.write(row, 1, _('Data'), xls_format['header'])
        WS.write(row, 2, _('Num. prod.'), xls_format['header']) # MRP
        WS.write(row, 3, _('Famiglia'), xls_format['header']) 
        WS.write(row, 4, _('Appront.'), xls_format['header']) 
        WS.write(row, 5, _('Lavoratori'), xls_format['header'])
        WS.write(row, 6, _('Tot. pezzi'), xls_format['header'])
        WS.write(row, 7, _('Tempo'), xls_format['header'])

        # Write data:
        for wc in sorted(res, key=lambda x: x.name):
            wc_start = row
            for date_planned in sorted(res[wc]):
                dp_start = row
                for line in res[wc][date_planned]:
                    row += 1     
                    # Total depend:                        
                    if line.is_total:
                        if line.is_today:
                            cell_format = xls_format['text_total_today']
                        else:    
                            cell_format = xls_format['text_total']
                        WS.merge_range(
                            row, 2, row, 3, _('TOTALE'), cell_format)
                    else:
                        if line.is_today:
                            cell_format = xls_format['text_today']
                        else:    
                            cell_format = xls_format['text']
                        WS.write(row, 2, line.production_id.name, cell_format)
                        WS.write(row, 3, line.product_id.name, cell_format) 

                    #Common part:                        
                    WS.write(row, 4, line.startup, cell_format) 
                    WS.write(row, 5, line.workers, cell_format)
                    WS.write(row, 6, line.lavoration_qty, cell_format)
                    WS.write(row, 7, line.hour, cell_format)
                dp_end = row
                WS.merge_range(dp_start + 1, 1, dp_end, 1, date_planned, 
                    xls_format['merge'])
                    
            wc_end = row
            WS.merge_range(wc_start + 1, 0, wc_end, 0, wc.name, 
                xls_format['merge'])
        
        WB.close()
        
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        now = now.replace('-', '_').replace(':', '.')
        result = open(filename, 'rb').read() #xlsx raw        
        attachments = [('Statistiche_Produzioni_%s.xlsx' % now, result)]
        
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        
        group_id = model_pool.get_object_reference(
            cr, uid, 
            'production_stats_auto_mail', 
            'group_mrp_stats_manager',
            )[1]
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)            
        _logger.info('Sending report, partner: %s' % (partner_ids, ))
        
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body='Statistica produzione giornaliera', 
            subject='Invio automatico statistiche di produzione: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments,
            context=context,
            )            
        return True
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
