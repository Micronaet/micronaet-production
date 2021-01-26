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
import openerp.addons.decimal_precision as dp
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
import xlrd
import base64
import pdb

_logger = logging.getLogger(__name__)


class MrpWorkerStatsHistory(orm.Model):
    """ Store fixed data
    """
    _name = 'mrp.worker.stats.history'
    _description = 'Worker stats history'
    _order = 'family,name'

    _columns = {
        'name': fields.char('Codice', size=6),
        'family': fields.char('Famiglia', size=40),
        'workers': fields.integer('Workers'),
        'medium': fields.integer('Medium'),
    }


class MrpStatsExcelReportWizard(orm.TransientModel):
    """ Wizard for generate report
    """
    _name = 'mrp.stats.excel.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_import_stats_first(self, cr, uid, ids, context=None):
        """ Load medium as history
        """
        if context is None:
            context = {}

        context['first_load'] = 'media'
        return self.action_import_stats(cr, uid, ids, context=context)

    def action_import_stats(self, cr, uid, ids, context=None):
        """ Import and update medium data
        """
        if context is None:
            context = {}

        use_line = context.get('first_load', 'stored')

        history_pool = self.pool.get('mrp.worker.stats.history')
        current_proxy = self.browse(cr, uid, ids, context=context)[0]

        # ---------------------------------------------------------------------
        # Save file passed:
        # ---------------------------------------------------------------------
        if not current_proxy.file:
            raise osv.except_osv(
                _('No file:'),
                _('File non presente'),
                )
        b64_file = base64.decodestring(current_proxy.file)
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        filename = '/tmp/tx_%s.xlsx' % now.replace(':', '_').replace('-', '_')
        f = open(filename, 'wb')
        f.write(b64_file)
        f.close()

        # ---------------------------------------------------------------------
        # Clean all previous statistic:
        # ---------------------------------------------------------------------
        # TODO save previous?
        _logger.warning('Delete previous history')
        history_ids = history_pool.search(cr, uid, [], context=context)
        history_pool.unlink(cr, uid, history_ids, context=context)

        # ---------------------------------------------------------------------
        # Load force name (for web publish)
        # ---------------------------------------------------------------------
        try:
            _logger.warning('Reload from file: %s' % filename)
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Errore XLSX'),
                _('Impossibile aprire il file: %s' % filename),
                )

        error = ''
        WS = WB.sheet_by_index(0)
        worker_start = 6
        start = False
        workers = {}
        for row in range(WS.nrows):
            # ---------------------------------------------------------
            # Read product code:
            # ---------------------------------------------------------
            origin = WS.cell(row, 0).value
            if not start and origin == 'Origine':
                start = True
                # Read workers part:
                for col in range(worker_start, WS.ncols):
                    worker = WS.cell(row, col).value
                    if type(worker) != float:
                        continue
                    workers[worker] = col
                continue
            if not start:
                continue

            if origin != use_line:
                _logger.warning('Jump media line')
                continue

            family = WS.cell(row, 1).value
            default_code = WS.cell(row, 2).value
            for worker in workers:
                worker_col = workers[worker]
                medium = WS.cell(row, worker_col).value
                if type(medium) == float:
                    history_pool.create(cr, uid, {
                        'name': default_code,
                        'family': family,
                        'workers': int(worker),
                        'medium': int(medium),
                    }, context=context)

        return True

    def action_stats_print(self, cr, uid, ids, context=None):
        """ Event stats print
            context > collect_data for get only dict collected
        """
        # Utility:
        def get_family(parent_code, family_db):
            """ Extract family from code (2:5)
            """
            for char in range(6, 1, -1):
                part_code = parent_code[:char]
                if part_code in family_db:
                    return family_db[part_code]
            return False

        if context is None:
            context = {}
        collect_data = context.get('collect_data')

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('mrp.production.stats')
        template_pool = self.pool.get('product.template')
        history_pool = self.pool.get('mrp.worker.stats.history')

        # Load template mask:
        family_db = {}
        family_ids = template_pool.search(cr, uid, [
            ('is_family', '=', True),
        ], context=context)

        for family in template_pool.browse(
                cr, uid, family_ids, context=context):
            for code in (family.family_list or '').split('|'):
                family_db[code] = family.name

        # ---------------------------------------------------------------------
        #                           CREATE EXCEL FILE:
        # ---------------------------------------------------------------------
        code_limit = 5  # Max code char
        ws_name = _('Statistica pezzi')
        excel_pool.create_worksheet(ws_name)
        excel_pool.set_format()

        # Format type:
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text = excel_pool.get_format('text')
        f_text_right = excel_pool.get_format('text_right')
        f_text_right_green = excel_pool.get_format('text_right_green')
        f_text_right_red = excel_pool.get_format('text_right_red')
        f_number = excel_pool.get_format('number')

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        line_ids = line_pool.search(cr, uid, [
            # ('mrp_id.state', '!=', 'done'),
        ], context=context)

        # Title row:
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Statistiche di produzione, medie prodotti [codice a 5 car.]'),
            ], f_title)

        # Write Header line:
        row += 2
        header = [
            _('Origine'),
            _('Famiglia'),
            _('Prodotto'),
            _('Tot. pezzi'),
            _('Tempo (h.)'),
            _('Pz / H'),
            ]
        excel_pool.write_xls_line(ws_name, row, header, f_header)
        excel_pool.autofilter(ws_name, row, 0, row, 1)

        # Setup columns:
        excel_pool.column_width(ws_name, [
            10, 30, 30, 10, 8, 8,
            ])

        fixed_cols = len(header)
        excel_pool.freeze_panes(ws_name, row + 1, len(header))

        data = {}
        workers_list = []
        for record in line_pool.browse(cr, uid, line_ids, context=context):
            mrp = record.mrp_id
            if not record.line_ids:
                _logger.warning('Production stats %s with no data' % mrp.name)
                continue

            workers = int(record.workers)
            total = record.total
            hour = record.hour
            # workline = record.workcenter_id.name  # TODO maybe used?
            # date = excel_pool.format_date(record.date)
            # mrp = record.mrp_id.name
            # startup = record.startup

            if not hour:
                # Not time so no medium data
                _logger.warning('Prod. stats %s without duration' % mrp.name)
                continue

            rate = total / hour  # pz x hour
            if workers not in workers_list:
                workers_list.append(workers)

            for product_line in record.line_ids:
                default_code = product_line.default_code[:code_limit].strip()
                family = get_family(default_code, family_db)

                qty = product_line.qty
                key = (family, default_code, 'media')
                stored_key = (family, default_code, 'stored')

                if key not in data:
                    data[key] = [
                        {},  # Workers data
                        0.0,  # Total pz (all)
                        0.0,  # Total hours (all)
                    ]
                    # ---------------------------------------------------------
                    # Populate history part:
                    # ---------------------------------------------------------
                    data[stored_key] = [
                        {},  # Workers data (stored)
                        0.0,  # Total pz (all) << not used
                        0.0,  # Total hours (all) << not used
                    ]
                    history_ids = history_pool.search(cr, uid, [
                        ('family', '=', family),
                        ('name', '=', default_code),
                    ], context=context)
                    for history in history_pool.browse(
                            cr, uid, history_ids, context=context):
                        workers = history.workers
                        data[stored_key][0][workers] = [
                            history.medium,  # medium (total pz.)
                            1.0,  # always 1 (total time)
                        ]

                if workers not in data[key][0]:
                    data[key][0][workers] = [
                        0.0,  # total pz.
                        0.0,  # total time
                    ]
                product_time = qty / rate

                # Workers:
                data[key][0][workers][0] += qty
                data[key][0][workers][1] += product_time

                # Product:
                data[key][1] += qty
                data[key][2] += product_time
        workers_list.sort()

        # Extend header:
        excel_pool.write_xls_line(
            ws_name, row, workers_list, f_header,
            col=fixed_cols)
        # Setup extra cols width:
        excel_pool.column_width(ws_name, [
            6 for i in range(fixed_cols)
            ], col=fixed_cols)

        # ---------------------------------------------------------------------
        # Write data line:
        # ---------------------------------------------------------------------
        for key in sorted(data):
            row += 1
            family, default_code, origin = key
            workers_data, product_total, product_hour = data[key]
            product_rate = product_total / product_hour if product_hour else 0

            excel_pool.write_xls_line(ws_name, row, [
                origin,
                family,
                default_code,
                (int(product_total), f_text_right),
                (product_hour, f_number),
                (int(round(product_rate, 0)), f_text_right),
                ], f_text)

            rate_list = [
                workers_data[k][0] / workers_data[k][1]
                for k in workers_data
                if workers_data[k][1]]
            if rate_list:
                max_rate = int(round(max(rate_list), 0))
                min_rate = int(round(min(rate_list), 0))
            else:
                max_rate = min_rate = 0
            for workers in workers_data:
                col = fixed_cols + workers_list.index(workers)
                total, hour = workers_data[workers]

                # Rate in tot pz / hour
                rate = int(round(total / hour if hour else 0))
                if origin == 'media':
                    if rate >= max_rate:
                        f_color = f_text_right_green
                    elif rate <= min_rate:
                        f_color = f_text_right_red
                    else:
                        f_color = f_text_right
                else:
                    f_color = f_header
                excel_pool.write_xls_line(ws_name, row, [
                    (rate, f_color),  # Total rate
                    ], f_text, col=col)

        attachment = excel_pool.return_attachment(
                cr, uid, 'Statistiche e medie', context=context)
        if collect_data:
            return data
        else:
            return attachment

    _columns = {
        'from_date': fields.date('From date >='),
        'to_date': fields.date('To date <'),
        'sort': fields.selection([
            ('line', 'Line-Family-Date'),
            ('family', 'Family-Line-Date'),
            ], 'sort', required=True)
        # 'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter'),
        # TODO family
        # TODO line
        # Product?
        }

    def action_print(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {}

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]

        # Parameters:
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date
        sort = wiz_browse.sort
        # wc_id = wiz_browse.workcenter_id.id

        if sort == 'line':
            sort_key = lambda x: (
                x.workcenter_id.name,  # Line
                x.mrp_id.bom_id.product_tmpl_id.name,  # Family
                x.mrp_id.name,  # Data
                )
        else:  # family
            sort_key = lambda x: (
                x.mrp_id.bom_id.product_tmpl_id.name,  # Family
                x.workcenter_id.name,  # Line
                x.mrp_id.name,  # Data
                )

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('mrp.production.stats')

        # ---------------------------------------------------------------------
        #                           CREATE EXCEL FILE:
        # ---------------------------------------------------------------------
        ws_name = 'Statistica'
        excel_pool.create_worksheet(ws_name)

        excel_pool.set_format()

        # Format type:
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text = excel_pool.get_format('text')
        f_number = excel_pool.get_format('number')

        # Setup columns:
        excel_pool.column_width(ws_name, [
            10, 10, 10, 20, 10, 10, 10, 10, 10, 60,
            ])

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------

        # Domain depend on wizard parameters:
        domain = []
        wiz_filter = ''
        if from_date:
            domain.append(('date', '>=', from_date))
            wiz_filter += _('Dalla data: %s ') % excel_pool.format_date(
                from_date)
        if to_date:
            domain.append(('date', '<', to_date))
            wiz_filter += _('Alla data: %s ') % excel_pool.format_date(to_date)
        wiz_filter = wiz_filter or _('Tutti')

        line_ids = line_pool.search(cr, uid, domain, context=context)

        # Title row:
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Statistiche di produzione'),
            ], f_title)

        row += 1
        excel_pool.write_xls_line(ws_name, row, [
            'Filtro: %s' % wiz_filter,
            ], f_title)

        # Header line:
        row += 2
        excel_pool.write_xls_line(ws_name, row, [
            _('Linea'),
            _('Data'),
            _('Num. prod.'),
            _('Famiglia'),
            _('Lavoratori'),
            _('Appront.'),
            _('Tot. pezzi'),
            _('Tempo'),
            _('Pz / H'),
            _('Dettaglio')
            ], f_header)

        # Write data:
        # XXX Part for break code in report:
        # break_code = {
        #    'line': [False, 0],
        #    'date': [False, 0],
        #    'family': [False, 0],
        #    }

        for line in sorted(
                line_pool.browse(cr, uid, line_ids, context=context),
                key=sort_key):
            row += 1

            # Key data:
            data = {  # last key, last row
                'line': line.workcenter_id.name,
                'date': excel_pool.format_date(line.date),
                'family': line.mrp_id.bom_id.product_tmpl_id.name,
                }

            # for key in data:
            #    if break_code == False or break_code[key][0] != data[key]:
            #        break_code[key][0] = data[key]
            #        break_code[key][1] = row # Save start row
            #        # TODO merge previous
            #    else: # not wrote:
            #        data[key] = '' # Not wrote

            excel_pool.write_xls_line(ws_name, row, [
                data['line'],
                data['date'],
                line.mrp_id.name,
                data['family'],
                line.workers,
                (excel_pool.format_hour(line.startup), f_number),
                (line.total, f_number),
                (excel_pool.format_hour(line.hour), f_number),
                (line.total / line.hour if line.hour else '#ERR', f_number),
                line.total_text_detail or ''
                ], f_text)

        return excel_pool.return_attachment(
            cr, uid, 'Statistiche di produzione', context=context)

    _columns = {
        'from_date': fields.date('From date >='),
        'to_date': fields.date('To date <'),
        'sort': fields.selection([
            ('line', 'Line-Family-Date'),
            ('family', 'Family-Line-Date'),
            ], 'sort', required=True),
        'file': fields.binary(
            'XLSX file', filters=None,
            help='File con le medie forzate manualmente'),
        # 'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter'),
        # TODO family
        # TODO line
        # Product?
        }

    _defaults = {
        'from_date': lambda *x: '%s01' % (datetime.now() - relativedelta(
            months=1)).strftime(DEFAULT_SERVER_DATE_FORMAT)[:8],
        'to_date': lambda *x: '%s01' % datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        'sort': lambda *x: 'line',

        }
