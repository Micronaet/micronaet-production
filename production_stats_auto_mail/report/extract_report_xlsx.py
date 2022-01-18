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
import pdb


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
        """ Send report to partner in group with dashboard statistics
            In scheduled report reload data from stats because need extra
            field not present in mixed query information
        """
        _logger.info('Start sending MRP report')

        # ---------------------------------------------------------------------
        #                               UTILITY:
        # ---------------------------------------------------------------------
        def extract_delta(workers, clean_data, detail, real):
            """ Extract delta t. from medium
            """
            medium_time = 0.0
            medium_detail = ''
            error = False
            for item in detail.replace('[ ', '').replace('[', '').split(']'):
                part = item.split(' >> ')
                if len(part) != 2:
                    # _logger.warning('Not part: %s' % item)
                    continue
                code = part[0].strip()[1:-1].strip()
                pieces = eval(part[1])  # x hour

                if code not in clean_data:
                    medium_detail += '[%s non ha media] ' % code
                    error = True
                    continue

                if workers in clean_data[code][0]:
                    total, time = clean_data[code][0][workers]
                    comment = ''
                else:
                    total, time = clean_data[code][1], clean_data[code][2]
                    comment = '*'

                if time and total:
                    piece_x_hour = total / time
                    medium_time += pieces / piece_x_hour  # m(x) t. x code
                    medium_detail += '[%s media: %s%s] ' % (
                        code, int(round(piece_x_hour, 0)), comment)
                else:
                    medium_detail += \
                        '[%s dati per la media non presenti] ' % code
                    error = True
                    continue

            if error or not medium_time:
                return medium_detail, False
            else:
                return medium_detail, real - medium_time  # Delta(t)

        def clean_extra_detail(value):
            """ Add extra detail total common
            """
            if not value:
                return value

            value = value.strip().replace('[', '')
            value_ids = value.split(']')
            res_ids = {}
            for v in value_ids:
                if not v:
                    continue  # jump last row
                v2 = v.split('>>')
                v2[0] = v2[0].strip()
                if v2[0] not in res_ids:
                    res_ids[v2[0]] = 0.0
                res_ids[v2[0]] += int(v2[1].strip())
            res = ''
            for code in sorted(res_ids):
                res += '[%s >> %s] ' % (code, res_ids[code])
            return res

        def format_date(value):
            """ Format hour DD:MM:YYYY
            """
            if not value:
                return ''
            return '%s/%s/%s' % (
                value[8:10],
                value[5:7],
                value[:4],
                )

        def format_hour(value):
            """ Format hour HH:MM
            """
            if not value:
                return '00:00'
            negative = value < 0

            value = abs(value)
            hour = int(value)
            minute = int((value - hour) * 60)
            return '%s%02d:%02d' % ('-' if negative else '', hour, minute)

        # ---------------------------------------------------------------------
        #                  Collect stats data in database:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        # Load statistic data form stored history (not from medium)
        history_pool = self.pool.get('mrp.worker.stats.history')
        clean_data = {}
        history_ids = history_pool.search(cr, uid, [], context=context)
        for record in history_pool.browse(
                cr, uid, history_ids, context=context):
            code = record.name
            workers = record.workers
            medium = record.medium
            if code not in clean_data:
                clean_data[code] = [{}, 0.0, 0.0]
            if workers not in clean_data[code][0]:
                clean_data[code][0][workers] = [medium, 1.0]

        # ---------------------------------------------------------------------
        #                  Collect stats data in database:
        # ---------------------------------------------------------------------
        res = {}
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        # TODO Collect data in res
        now_0 = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        now_1 = (datetime.now() - timedelta(days=1)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        now_9 = (datetime.now() - timedelta(days=9)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        # Add extra period for not get empty data in extra info
        now_11 = (datetime.now() - timedelta(days=11)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        # Statistic 20 days page:
        now_20 = (datetime.now() - timedelta(days=20)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        now_6_month = (datetime.now() - timedelta(days=180)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)

        # ---------------------------------------------------------------------
        #                           Excel file:
        # ---------------------------------------------------------------------
        # A. Create file:
        filename = '/tmp/send_stats_mrp_report.xlsx'
        _logger.info('Temp file: %s' % filename)
        WB = xlsxwriter.Workbook(filename)

        # B. Format class:
        num_format = '0.#0'
        xls_format = {
            'title': WB.add_format({
                'bold': True,
                'font_name': 'Courier 10 pitch',  # 'Arial'
                'font_size': 10,
                'align': 'left',
                }),
            'header': WB.add_format({
                'bold': True,
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',  # 'Arial'
                'font_size': 9,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#cfcfcf',  # gray
                'border': 1,
                # 'text_wrap': True,
                }),
            'merge': WB.add_format({
                'bold': True,
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',  # 'Arial'
                'font_size': 10,
                'align': 'center',
                # 'vertical_align': 'center',
                'valign': 'vcenter',
                # 'bg_color': '#cfcfcf', # gray
                'border': 1,
                }),
            'text': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                # 'align': 'left',
                'border': 1,
                }),
            'text_number': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                }),
            'text_red': WB.add_format({
                'font_color': 'black',
                'bg_color': '#e5a69f',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                # 'align': 'left',
                'border': 1,
                }),
            'text_red_gap': WB.add_format({
                'font_color': 'black',
                'bg_color': '#dd4c3b',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                # 'align': 'left',
                'border': 1,
                }),
            'text_number_red': WB.add_format({
                'font_color': 'black',
                'bg_color': '#e5a69f',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                }),
            'text_number_white': WB.add_format({
                'font_color': 'black',
                'bg_color': '#e5a69f',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            'text_today': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                # 'align': 'right',
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
                # 'bg_color': '#e6ffe6',
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
        #                 EXCEL: SHEET 1 Week total statistic:
        # ---------------------------------------------------------------------
        # Pool used:
        line_pool = self.pool.get('mrp.production.stats')

        # Collect data for extra info:
        extra_detail = {}

        line_ids = line_pool.search(cr, uid, [
            ('date', '>=', now_11),  # last 11 days (for cover 9 days)
            ], context=context)
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            key = (
                line.workcenter_id.id,
                line.date,
                line.mrp_id.id,
                )
            if key not in extra_detail:
                extra_detail[key] = ''
            extra_detail[key] += line.total_text_detail

        # Collect data for stats mixed:
        line_ids = self.search(cr, uid, [  # Filter yet present in query
            # ('date_planned', '>=', now_9),
            # ('date_planned', '<=', now_0),
            ], context=context)
        for line in self.browse(cr, uid, line_ids, context=context):
            if line.date_planned not in res:
                res[line.date_planned] = {}
            if line.workcenter_id not in res[line.date_planned]:
                res[line.date_planned][line.workcenter_id] = []
            res[line.date_planned][line.workcenter_id].append(line)

        WS = WB.add_worksheet('Settimanali')
        WS.set_column('A:A', 12)
        WS.set_column('B:D', 15)
        WS.set_column('E:I', 8)
        WS.set_column('J:M', 60)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Produzioni settimana passata, data rif.: %s' % now,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Data'), xls_format['header'])
        WS.write(row, 1, _('Linea'), xls_format['header'])
        WS.write(row, 2, _('Num. prod.'), xls_format['header'])  # MRP
        WS.write(row, 3, _('Famiglia'), xls_format['header'])
        WS.write(row, 4, _('Lavoratori'), xls_format['header'])
        WS.write(row, 5, _('Appront.'), xls_format['header'])
        WS.write(row, 6, _('Tot. pezzi'), xls_format['header'])
        WS.write(row, 7, _('Tempo'), xls_format['header'])
        WS.write(row, 8, _('Delta t.'), xls_format['header'])
        # WS.write(row, 9, _('Dettaglio lav.'), xls_format['header'])
        WS.write(row, 9, _('Dettaglio medie'), xls_format['header'])
        WS.write(row, 10, _('Dettaglio'), xls_format['header'])

        # Write data:
        cell_format = xls_format['text']
        cell_number_format = xls_format['text_number_today']
        for date_planned in sorted(res, reverse=True):
            planned_start = row
            for wc in sorted(res[date_planned], key=lambda x: x.name):
                wc_start = row
                for line in res[date_planned][wc]:
                    row += 1
                    # Total depend:
                    if line.is_total:
                        if line.is_today:
                            cell_format = xls_format['text_total_today']
                        else:
                            cell_format = xls_format['text_total']
                        cell_number_format = cell_format  # same of text

                        WS.merge_range(
                            row, 2, row, 4, _('TOTALE'), cell_format)
                        WS.write(row, 4, '', cell_format)  # No total workers
                        WS.write(row, 8, '', cell_format)  # Empty detail
                    else:
                        if line.is_today:
                            cell_format = xls_format['text_today']
                            cell_number_format = xls_format[
                                'text_number_today']
                        else:
                            cell_format = xls_format['text']
                            cell_number_format = xls_format[
                                'text_number_total']

                        # worker_list = ', '.join(
                        #    [w.name for w in line.operators_ids])
                        WS.write(row, 2, line.production_id.name, cell_format)
                        WS.write(row, 3, line.product_id.name, cell_format)
                        WS.write(row, 4, line.workers, cell_format)

                        # TODO Medium delta difference:
                        detail = extra_detail.get(
                            (wc.id, date_planned, line.production_id.id), '')
                        delta_comment, delta = extract_delta(
                            line.workers, clean_data, detail,
                            line.hour)
                        delta = '/' if delta == False else format_hour(delta)
                        WS.write(row, 8, delta, cell_number_format)
                        # WS.write(row, 9, worker_list, cell_format)
                        WS.write(row, 9, delta_comment, cell_format)
                        WS.write(
                            row, 10, clean_extra_detail(detail), cell_format)

                    # Common part:
                    WS.write(
                        row, 5, format_hour(line.startup),
                        cell_number_format)
                    WS.write(
                        row, 6, line.maked_qty,
                        cell_number_format)
                    WS.write(
                        row, 7, format_hour(line.hour),
                        cell_number_format)
                wc_end = row
                WS.merge_range(
                    wc_start + 1, 1, wc_end, 1,
                    wc.name,
                    xls_format['merge'])

            planned_end = row
            WS.merge_range(
                planned_start + 1, 0, planned_end, 0,
                format_date(date_planned),
                xls_format['merge'])

        # ---------------------------------------------------------------------
        #                   EXCEL: SHEET 1 Detail last 14 days
        # ---------------------------------------------------------------------
        #    sort_key = lambda x: (
        #        x.workcenter_id.name, # Line
        #        x.mrp_id.bom_id.product_tmpl_id.name, # Family
        #        x.mrp_id.name, # Data
        #        )
        sort_key = lambda x: (
            x.mrp_id.bom_id.product_tmpl_id.name,  # Family
            x.workcenter_id.name,  # Line
            x.mrp_id.name,  # Data
            )

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        line_ids = line_pool.search(cr, uid, [
            ('date', '>=', now_6_month),
            ], context=context)

        WS_month = {}
        for line in sorted(
                line_pool.browse(cr, uid, line_ids, context=context),
                key=sort_key, reverse=True):
            mrp_line = line.workcenter_id.name
            if mrp_line in WS_month:
                WS = WS_month[mrp_line][0]
            else:
                # -------------------------------------------------------------
                # Create WS for line:
                # -------------------------------------------------------------
                WS = WB.add_worksheet('Dett. %s' % mrp_line)

                # Setup columns:
                WS.set_column('A:C', 10)
                WS.set_column('D:D', 20)
                WS.set_column('E:I', 10)
                WS.set_column('J:K', 60)

                WS_month[mrp_line] = [
                    WS,
                    0,
                ]

                # Title row:
                WS.write(
                    WS_month[mrp_line][1], 0,
                    'Dettaglio statistiche %s (ultimi 180 gg.)' % mrp_line,
                    xls_format['title'],
                    )

                # Header line:
                WS_month[mrp_line][1] += 2
                row = WS_month[mrp_line][1]
                WS.write(row, 0, _('Linea'), xls_format['header'])
                WS.write(row, 1, _('Data'), xls_format['header'])
                WS.write(row, 2, _('Num. prod.'), xls_format['header'])
                WS.write(row, 3, _('Famiglia'), xls_format['header'])
                WS.write(row, 4, _('Lavoratori'), xls_format['header'])
                WS.write(row, 5, _('Appront.'), xls_format['header'])
                WS.write(row, 6, _('Tot. pezzi'), xls_format['header'])
                WS.write(row, 7, _('Tempo'), xls_format['header'])
                WS.write(row, 8, _('Pz / H'), xls_format['header'])
                WS.write(row, 9, _('Dett. operatori'), xls_format['header'])
                WS.write(row, 10, _('Dett. prod.'), xls_format['header'])
                WS.autofilter(row, 0, row, 5)  # Till columns 6
                WS.freeze_panes(3, 1)

                # Setup again:
                cell_format = xls_format['text']
                cell_number_format = xls_format['text_number_today']

            WS_month[mrp_line][1] += 1
            row = WS_month[mrp_line][1]

            # Key data:
            data = {  # last key, last row
                'line': line.workcenter_id.name,
                'date': format_date(line.date),
                'family': line.mrp_id.bom_id.product_tmpl_id.name,
                }

            worker_list = ', '.join(
                [w.name for w in line.operator_ids])

            WS.write(row, 0, data['line'], cell_format)
            WS.write(row, 1, data['date'], cell_format)
            WS.write(row, 2, line.mrp_id.name, cell_format)
            WS.write(row, 3, data['family'], cell_format)
            WS.write(row, 4, line.workers, cell_format)
            WS.write(row, 5, format_hour(line.startup), cell_format)
            WS.write(row, 6, line.total, cell_number_format)
            WS.write(row, 7, format_hour(line.hour), cell_format)
            WS.write(
                row, 8, line.total / line.hour if line.hour else '#ERR',
                cell_number_format)
            WS.write(row, 9, worker_list, cell_format)
            WS.write(row, 10, line.total_text_detail, cell_format)

        # ---------------------------------------------------------------------
        #                   EXCEL: SHEET 2 Today statistic:
        # ---------------------------------------------------------------------
        # Collect data:
        line_ids = line_pool.search(cr, uid, [
            ('date', '=', now_1),
            ], context=context)

        WS = WB.add_worksheet('Ieri')
        WS.set_column('A:C', 10)
        WS.set_column('D:D', 20)
        WS.set_column('E:I', 10)
        WS.set_column('J:J', 60)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Produzione di ieri, data rif.: %s' % now_1,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Linea'), xls_format['header'])
        WS.write(row, 1, _('Data'), xls_format['header'])
        WS.write(row, 2, _('Num. prod.'), xls_format['header'])  # MRP
        WS.write(row, 3, _('Famiglia'), xls_format['header'])
        WS.write(row, 4, _('Lavoratori'), xls_format['header'])
        WS.write(row, 5, _('Appront.'), xls_format['header'])
        WS.write(row, 6, _('Tot. pezzi'), xls_format['header'])
        WS.write(row, 7, _('Tempo'), xls_format['header'])
        WS.write(row, 8, _('Pz / H'), xls_format['header'])
        WS.write(row, 9, _('Dettaglio'), xls_format['header'])

        # Write data:
        for line in sorted(
                line_pool.browse(cr, uid, line_ids, context=context),
                key=lambda x: (
                    x.workcenter_id.name,  # Line
                    x.mrp_id.name,  # Data
                    x.mrp_id.bom_id.product_tmpl_id.name,  # Family
                    )):
            row += 1
            WS.write(row, 0, line.workcenter_id.name, cell_format)
            WS.write(row, 1, format_date(line.date), cell_format)
            WS.write(row, 2, line.mrp_id.name, cell_format)
            WS.write(
                row, 3, line.mrp_id.bom_id.product_tmpl_id.name,
                cell_format)
            WS.write(row, 4, line.workers, cell_format)
            WS.write(row, 5, format_hour(line.startup), cell_format)
            WS.write(row, 6, line.total, cell_number_format)
            WS.write(row, 7, format_hour(line.hour), cell_format)
            if line.hour:
                WS.write(row, 8, line.total / line.hour, cell_number_format)
            else:
                WS.write(row, 8, '#ERR', cell_number_format)
            WS.write(row, 9, line.total_text_detail, cell_number_format)

        # ---------------------------------------------------------------------
        #                           Industria 4.0
        # ---------------------------------------------------------------------
        # SALDATRICE:
        # ---------------------------------------------------------------------
        medium_data = {}
        job_pool = self.pool.get('industria.job')
        # Collect data:
        job_ids = job_pool.search(cr, uid, [
            ('source_id.code', '=', 'SALD01'),
            ('created_at', '>=', '%s 00:00:00' % now_20),
            # ('created_at', '<=', '%s 23:59:59' % now_1),
            ], context=context)
        WS = WB.add_worksheet('GIMAF')
        WS.set_column('A:C', 25)
        WS.set_column('D:I', 15)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Job saldatrice GIMAF dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Dalla data'), xls_format['header'])
        WS.write(row, 2, _('Alla data'), xls_format['header'])
        WS.write(row, 3, _('Durata'), xls_format['header'])
        WS.write(row, 4, _('Cambio totale'), xls_format['header'])
        WS.write(row, 5, _('Cambio gap'), xls_format['header'])
        WS.write(row, 6, _('Attrezzaggio'), xls_format['header'])
        WS.write(row, 7, _('Non cons.'), xls_format['header'])
        WS.write(row, 8, _('Nuova'), xls_format['header'])

        WS.freeze_panes(2, 1)

        # Write data:
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            duration_not_considered = job.duration_not_considered
            job_duration = job.job_duration
            duration_change_total = job.duration_change_total
            duration_change_gap = job.duration_change_gap
            duration_setup = job.duration_setup
            program = job.program_id

            if duration_not_considered:
                cell_format = xls_format['text_red']
            else:
                cell_format = xls_format['text']

            created_at = self.get_user_time(
                cr, uid, job.created_at, context=context)
            ended_at = self.get_user_time(
                cr, uid, job.ended_at, context=context)

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, created_at, cell_format)
            WS.write(row, 2, ended_at, cell_format)
            WS.write(row, 3, format_hour(job_duration), cell_format)
            WS.write(row, 4, format_hour(duration_change_total), cell_format)
            WS.write(row, 5, format_hour(duration_change_gap), cell_format)
            WS.write(row, 6, format_hour(duration_setup), cell_format)
            WS.write(
                row, 7,
                'X' if duration_not_considered else '', cell_format)
            WS.write(
                row, 8, 'X' if job.duration_need_setup else '', cell_format)

            # Medium data:
            if not duration_not_considered:
                if program not in medium_data:
                    medium_data[program] = [
                        0,  # counter
                        0.0,  # duration
                        0.0,  # total change
                        0.0,  # gap change
                        0.0,  # setup
                    ]
                medium_data[program][0] += 1
                medium_data[program][1] += job_duration
                medium_data[program][2] += duration_change_total
                medium_data[program][3] += duration_change_gap
                medium_data[program][4] += duration_setup

        # ---------------------------------------------------------------------
        # Saldatrice media:
        # ---------------------------------------------------------------------
        WS = WB.add_worksheet('GIMAF medie')
        WS.set_column('A:A', 25)
        WS.set_column('B:I', 12)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Medie per GIMAF dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Cont.'), xls_format['header'])
        WS.write(row, 2, _('Durata'), xls_format['header'])
        WS.write(row, 3, _('Cambio totale'), xls_format['header'])
        WS.write(row, 4, _('Cambio gap'), xls_format['header'])
        WS.write(row, 5, _('Attrezzaggio'), xls_format['header'])

        # Medie:
        WS.write(row, 6, _('Dur. med.'), xls_format['header'])
        WS.write(row, 7, _('Cambio tot. med.'), xls_format['header'])
        WS.write(row, 8, _('Cambio gap med.'), xls_format['header'])

        WS.freeze_panes(2, 1)
        # Write data:
        cell_format = xls_format['text']
        for program in sorted(medium_data, key=lambda k: k.name):
            (total, job_duration, duration_change_total, duration_change_gap,
             duration_setup) = medium_data[program]
            if total:
                mx_duration = job_duration / total
                mx_change_total = duration_change_total / total
                mx_change_gap = duration_change_gap / total
            else:
                mx_duration = mx_change_total = mx_change_gap = 0.0

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, total, cell_format)
            WS.write(row, 2, format_hour(job_duration), cell_format)
            WS.write(row, 3, format_hour(duration_change_total), cell_format)
            WS.write(row, 4, format_hour(duration_change_gap), cell_format)
            WS.write(row, 5, format_hour(duration_setup), cell_format)

            WS.write(row, 6, format_hour(mx_duration), cell_format)
            WS.write(row, 7, format_hour(mx_change_total), cell_format)
            WS.write(row, 8, format_hour(mx_change_gap), cell_format)

            # todo write expected medium

        # ---------------------------------------------------------------------
        # TAGLIATUBI:
        # ---------------------------------------------------------------------
        medium_data = {}
        cut_pool = self.pool.get('industria.pipe.file.stat')
        # Collect data:
        cut_ids = cut_pool.search(cr, uid, [
            ('file_id.robot_id.code', '=', 'TAGL01'),
            ('timestamp', '>=', '%s 00:00:00' % now_20),
            ], context=context)
        WS = WB.add_worksheet('ADIGE')
        WS.set_column('A:C', 25)
        WS.set_column('D:I', 15)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Job tagliabuti ADIGE dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Dalla data'), xls_format['header'])
        WS.write(row, 2, _('Alla data'), xls_format['header'])
        WS.write(row, 3, _('Durata'), xls_format['header'])
        WS.write(row, 4, _('Cambio totale'), xls_format['header'])
        WS.write(row, 5, _('Cambio gap'), xls_format['header'])
        WS.write(row, 6, _('Attrezzaggio'), xls_format['header'])
        WS.write(row, 7, _('Non cons.'), xls_format['header'])
        WS.write(row, 8, _('Nuova'), xls_format['header'])

        WS.freeze_panes(2, 1)

        # Write data:
        for cut in cut_pool.browse(cr, uid, cut_ids, context=context):
            if cut.state != 'CAMBIO BARRA':  # todo if no need other go search!
                continue
            duration_not_considered = False  # todo Not used for this?
            bar_duration = cut.duration_bar
            program = cut.program_id

            # todo Data not present for now:
            duration_change_total = duration_change_gap = duration_setup = 0
            duration_need_setup = False

            if duration_not_considered:
                cell_format = xls_format['text_red']
            else:
                cell_format = xls_format['text']

            timestamp = self.get_user_time(
                cr, uid, cut.timestamp, context=context)

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, timestamp, cell_format)
            WS.write(row, 2, '/', cell_format)  # not used for now
            WS.write(row, 3, format_hour(bar_duration), cell_format)
            WS.write(row, 4, format_hour(duration_change_total), cell_format)
            WS.write(row, 5, format_hour(duration_change_gap), cell_format)
            WS.write(row, 6, format_hour(duration_setup), cell_format)
            WS.write(
                row, 7,
                'X' if duration_not_considered else '', cell_format)
            WS.write(
                row, 8, 'X' if duration_need_setup else '', cell_format)

            # Medium data:
            if not duration_not_considered:
                if program not in medium_data:
                    medium_data[program] = [
                        0,  # counter
                        0.0,  # duration
                        0.0,  # total change
                        0.0,  # gap change
                        0.0,  # setup
                    ]
                medium_data[program][0] += 1
                medium_data[program][1] += bar_duration
                medium_data[program][2] += duration_change_total
                medium_data[program][3] += duration_change_gap
                medium_data[program][4] += duration_setup

        # ---------------------------------------------------------------------
        # Tagliatubi media:
        # ---------------------------------------------------------------------
        WS = WB.add_worksheet('ADIGE medie')
        WS.set_column('A:A', 25)
        WS.set_column('B:I', 12)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Medie per ADIGE dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Cont.'), xls_format['header'])
        WS.write(row, 2, _('Durata'), xls_format['header'])
        WS.write(row, 3, _('Cambio totale'), xls_format['header'])
        WS.write(row, 4, _('Cambio gap'), xls_format['header'])
        WS.write(row, 5, _('Attrezzaggio'), xls_format['header'])

        # Medie:
        WS.write(row, 6, _('Dur. med.'), xls_format['header'])
        WS.write(row, 7, _('Cambio tot. med.'), xls_format['header'])
        WS.write(row, 8, _('Cambio gap med.'), xls_format['header'])

        WS.freeze_panes(2, 1)
        # Write data:
        cell_format = xls_format['text']
        for program in sorted(medium_data, key=lambda k: k.name):
            (total, job_duration, duration_change_total, duration_change_gap,
             duration_setup) = medium_data[program]
            if total:
                mx_duration = job_duration / total
                mx_change_total = duration_change_total / total
                mx_change_gap = duration_change_gap / total
            else:
                mx_duration = mx_change_total = mx_change_gap = 0.0

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, total, cell_format)
            WS.write(row, 2, format_hour(job_duration), cell_format)
            WS.write(row, 3, format_hour(duration_change_total), cell_format)
            WS.write(row, 4, format_hour(duration_change_gap), cell_format)
            WS.write(row, 5, format_hour(duration_setup), cell_format)

            WS.write(row, 6, format_hour(mx_duration), cell_format)
            WS.write(row, 7, format_hour(mx_change_total), cell_format)
            WS.write(row, 8, format_hour(mx_change_gap), cell_format)

            # todo write expected medium

        # ---------------------------------------------------------------------
        # FORNO:
        # ---------------------------------------------------------------------
        medium_data = {}
        job_pool = self.pool.get('industria.job')
        # Collect data:
        job_ids = job_pool.search(cr, uid, [
            ('source_id.code', '=', 'FORN01'),
            ('created_at', '>=', '%s 00:00:00' % now_20),
            ], context=context)
        WS = WB.add_worksheet('ELETTROFRIGO')
        WS.set_column('A:C', 25)
        WS.set_column('D:I', 15)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Job Forno ELETTROFRIGO dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Dalla data'), xls_format['header'])
        WS.write(row, 2, _('Alla data'), xls_format['header'])
        WS.write(row, 3, _('Durata'), xls_format['header'])
        WS.write(row, 4, _('Cambio totale'), xls_format['header'])
        WS.write(row, 5, _('Cambio gap'), xls_format['header'])
        WS.write(row, 6, _('Attrezzaggio'), xls_format['header'])
        WS.write(row, 7, _('Non cons.'), xls_format['header'])
        WS.write(row, 8, _('Nuova'), xls_format['header'])

        WS.freeze_panes(2, 1)

        # Write data:
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            duration_not_considered = False  # todo Not used for this?
            job_duration = 8  # ended_at created_at
            program = job.program_id

            # todo Data not present for now:
            duration_change_total = duration_change_gap = duration_setup = 0
            duration_need_setup = False

            if duration_not_considered:
                cell_format = xls_format['text_red']
            else:
                cell_format = xls_format['text']

            row += 1

            created_at = self.get_user_time(
                cr, uid, job.created_at, context=context)
            ended_at = self.get_user_time(
                cr, uid, job.ended_at, context=context)

            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, created_at, cell_format)
            WS.write(row, 2, ended_at or '/', cell_format)  # not used
            WS.write(row, 3, format_hour(job_duration), cell_format)
            WS.write(row, 4, format_hour(duration_change_total), cell_format)
            WS.write(row, 5, format_hour(duration_change_gap), cell_format)
            WS.write(row, 6, format_hour(duration_setup), cell_format)
            WS.write(
                row, 7,
                'X' if duration_not_considered else '', cell_format)
            WS.write(
                row, 8, 'X' if duration_need_setup else '', cell_format)

            # Medium data:
            if not duration_not_considered:
                if program not in medium_data:
                    medium_data[program] = [
                        0,  # counter
                        0.0,  # duration
                        0.0,  # total change
                        0.0,  # gap change
                        0.0,  # setup
                    ]
                medium_data[program][0] += 1
                medium_data[program][1] += job_duration
                medium_data[program][2] += duration_change_total
                medium_data[program][3] += duration_change_gap
                medium_data[program][4] += duration_setup

        # ---------------------------------------------------------------------
        # Tagliatubi media:
        # ---------------------------------------------------------------------
        WS = WB.add_worksheet('ELETTRIFRIGO medie')
        WS.set_column('A:A', 25)
        WS.set_column('B:I', 12)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Medie forno per ELETTRIFRIGO dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Cont.'), xls_format['header'])
        WS.write(row, 2, _('Durata'), xls_format['header'])
        WS.write(row, 3, _('Cambio totale'), xls_format['header'])
        WS.write(row, 4, _('Cambio gap'), xls_format['header'])
        WS.write(row, 5, _('Attrezzaggio'), xls_format['header'])

        # Medie:
        WS.write(row, 6, _('Dur. med.'), xls_format['header'])
        WS.write(row, 7, _('Cambio tot. med.'), xls_format['header'])
        WS.write(row, 8, _('Cambio gap med.'), xls_format['header'])

        WS.freeze_panes(2, 1)
        # Write data:
        cell_format = xls_format['text']
        for program in sorted(medium_data, key=lambda k: k.name):
            (total, job_duration, duration_change_total, duration_change_gap,
             duration_setup) = medium_data[program]
            if total:
                mx_duration = job_duration / total
                mx_change_total = duration_change_total / total
                mx_change_gap = duration_change_gap / total
            else:
                mx_duration = mx_change_total = mx_change_gap = 0.0

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, total, cell_format)
            WS.write(row, 2, format_hour(job_duration), cell_format)
            WS.write(row, 3, format_hour(duration_change_total), cell_format)
            WS.write(row, 4, format_hour(duration_change_gap), cell_format)
            WS.write(row, 5, format_hour(duration_setup), cell_format)

            WS.write(row, 6, format_hour(mx_duration), cell_format)
            WS.write(row, 7, format_hour(mx_change_total), cell_format)
            WS.write(row, 8, format_hour(mx_change_gap), cell_format)

            # todo write expected medium

        # ---------------------------------------------------------------------
        # PIEGATUBI:
        # ---------------------------------------------------------------------
        medium_data = {}
        job_pool = self.pool.get('industria.job')
        # Collect data:
        job_ids = job_pool.search(cr, uid, [
            ('source_id.code', '=', 'PIEG01'),
            ('created_at', '>=', '%s 00:00:00' % now_20),
            # ('created_at', '<=', '%s 23:59:59' % now_1),
            ], context=context)
        WS = WB.add_worksheet('FLECTE')
        WS.set_column('A:C', 25)
        WS.set_column('D:H', 10)
        WS.set_column('I:I', 40)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Job piegatubi FLECTE dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Dalla data'), xls_format['header'])
        WS.write(row, 2, _('Alla data'), xls_format['header'])
        WS.write(row, 3, _('Durata'), xls_format['header'])
        WS.write(row, 4, _('Prossimo gap'), xls_format['header'])
        WS.write(row, 5, _('Attrezzaggio'), xls_format['header'])
        WS.write(row, 6, _('Non cons.'), xls_format['header'])
        WS.write(row, 7, _('Nuova'), xls_format['header'])
        WS.write(row, 8, _('Note'), xls_format['header'])

        WS.freeze_panes(2, 1)

        # Write data:
        gap_limit = 1.0
        medium_cache = {}
        last = {
            'start': False,
            'program': False,
            'day': False,
        }
        counter = 0
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            counter += 1
            note = ''
            duration_not_considered = job.duration_not_considered
            job_duration = job.job_duration

            # Gap from 2 relevation:
            # duration_change_gap = job.duration_change_gap  todo not used

            created_at = self.get_user_time(
                cr, uid, job.created_at, context=context)
            day = created_at[:10]
            ended_at = self.get_user_time(
                cr, uid, job.ended_at, context=context)
            duration_setup = job.duration_setup
            program = job.program_id

            # -----------------------------------------------------------------
            # Check last:
            # -----------------------------------------------------------------
            if last['day'] != day:
                note += '[fine giorno] '
                change_day = True
                last['day'] = day
            else:
                change_day = False

            if last['program'] != program:
                note += '[fine programma] '
                change_program = True
                last['program'] = program
            else:
                change_program = False

            if last['start'] and not change_day:
                duration_change_gap = (
                    datetime.strptime(
                        last['start'], DEFAULT_SERVER_DATETIME_FORMAT) -
                    datetime.strptime(
                        ended_at, DEFAULT_SERVER_DATETIME_FORMAT)
                ).seconds / 60.0
            else:
                duration_change_gap = 0  # Not the first
            last['start'] = created_at

            # Consider setup with change gap if new program
            if change_program and not change_day:
                duration_setup = duration_change_gap

            if program not in medium_cache:
                medium_cache[program] = (
                    program.medium * 0.5, program.medium * 1.5)
            range_min, range_max = medium_cache[program]

            # -----------------------------------------------------------------
            # Color for cell:
            # -----------------------------------------------------------------
            if duration_change_gap > gap_limit:
                cell_gap_format = xls_format['text_red']
                note += '[gap alto > 1 min.] '

            else:
                cell_gap_format = xls_format['text']

            if range_min < job_duration < range_max:
                cell_format = xls_format['text']
            else:
                note += '[lavorazione alta (range 50% - 150%)] '
                cell_format = xls_format['text_red']
                duration_not_considered = True

            row += 1
            WS.write(row, 0, program.name, xls_format['text'])
            WS.write(row, 1, created_at, xls_format['text'])
            WS.write(row, 2, ended_at, xls_format['text'])
            WS.write(row, 3, format_hour(job_duration), cell_format)
            WS.write(row, 4, format_hour(duration_change_gap), cell_gap_format)
            WS.write(row, 5, format_hour(duration_setup), xls_format['text'])
            WS.write(
                row, 6,
                'X' if duration_not_considered else '', xls_format['text'])
            WS.write(
                row, 7, 'X' if job.duration_need_setup else '',
                xls_format['text'])
            WS.write(row, 8, note if counter != 1 else '', xls_format['text'])

            # Medium data:
            if not duration_not_considered:
                if program not in medium_data:
                    medium_data[program] = [
                        0,  # counter
                        0.0,  # duration
                        0.0,  # gap change
                        0.0,  # setup
                    ]
                medium_data[program][0] += 1
                medium_data[program][1] += job_duration
                medium_data[program][2] += duration_change_gap
                medium_data[program][3] += duration_setup

        # ---------------------------------------------------------------------
        # Piegatubi media:
        # ---------------------------------------------------------------------
        WS = WB.add_worksheet('FLECTE medie')
        WS.set_column('A:A', 25)
        WS.set_column('B:I', 12)

        # Write title row:
        row = 0
        WS.write(
            row, 0,
            'Medie per FLECTE dalla data di rif.: %s' % now_20,
            xls_format['title'],
            )

        # Header line:
        row += 1
        WS.write(row, 0, _('Programma'), xls_format['header'])
        WS.write(row, 1, _('Cont.'), xls_format['header'])
        WS.write(row, 2, _('Durata'), xls_format['header'])
        WS.write(row, 3, _('Cambio gap'), xls_format['header'])
        WS.write(row, 4, _('Attrezzaggio'), xls_format['header'])

        # Medie:
        WS.write(row, 5, _('Dur. med.'), xls_format['header'])
        WS.write(row, 6, _('Cambio gap med.'), xls_format['header'])

        WS.freeze_panes(2, 1)
        # Write data:
        cell_format = xls_format['text']
        for program in sorted(medium_data, key=lambda k: k.name):
            (total, job_duration, duration_change_gap, duration_setup) = \
                medium_data[program]
            if total:
                mx_duration = job_duration / total
                mx_change_gap = duration_change_gap / total
            else:
                mx_duration = mx_change_gap = 0.0

            row += 1
            WS.write(row, 0, program.name, cell_format)
            WS.write(row, 1, total, cell_format)
            WS.write(row, 2, format_hour(job_duration), cell_format)
            WS.write(row, 3, format_hour(duration_change_gap), cell_format)
            WS.write(row, 4, format_hour(duration_setup), cell_format)

            WS.write(row, 5, format_hour(mx_duration), cell_format)
            WS.write(row, 6, format_hour(mx_change_gap), cell_format)
            # todo write expected medium

        WB.close()

        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        now = now.replace('-', '_').replace(':', '.')
        result = open(filename, 'rb').read()  # xlsx raw
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

    def get_user_time(self, cr, uid, dt_value, context=None):
        """ Get user TZ time
        """
        if not dt_value:
            return False
        return fields.datetime.context_timestamp(
            cr, uid,
            datetime.strptime(
                dt_value,
                DEFAULT_SERVER_DATETIME_FORMAT),
            context=context).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
