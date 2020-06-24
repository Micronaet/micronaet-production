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

_logger = logging.getLogger(__name__)


class MrpStatsExcelReportWizard(orm.TransientModel):
    """ Wizard for
    """
    _name = 'mrp.stats.excel.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_stats_print(self, cr, uid, ids, context=None):
        """ Event stats print
        """
        if context is None:
            context = {}

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('mrp.production.stats')

        # ---------------------------------------------------------------------
        #                           CREATE EXCEL FILE:
        # ---------------------------------------------------------------------
        ws_name = _('Statistica pezzi')
        excel_pool.create_worksheet(ws_name)
        excel_pool.set_format()

        # Format type:
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text = excel_pool.get_format('text')
        f_number = excel_pool.get_format('number')

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        line_ids = line_pool.search(cr, uid, [], context=context)

        # Title row:
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            _('Statistiche di produzione (medie sui prodotti a padre 5 cifre'),
            ], f_title)

        # Write Header line:
        row += 2
        header = [
            _('Famiglia'),
            _('Prodotto'),
            _('Tot. pezzi'),
            _('Tempo'),
            _('Pz / H'),
            ]
        excel_pool.write_xls_line(ws_name, row, header, f_header)

        # Setup columns:
        excel_pool.column_width(ws_name, [
            30, 30, 10, 8, 8,
            ])

        fixed_cols = len(header)

        data = {}
        workers_list = []
        for record in line_pool.browse(cr, uid, line_ids, context=context):
            family = record.mrp_id.bom_id.product_tmpl_id.name
            workers = int(record.workers)
            total = record.total
            hour = record.hour
            # workline = record.workcenter_id.name  # TODO maybe used?
            # date = excel_pool.format_date(record.date)
            # mrp = record.mrp_id.name
            # startup = record.startup

            rate = total / hour if hour else 0  # Rate in tot pz / hours
            if workers not in workers_list:
                workers_list.append(workers)

            for product_line in record.line_ids:
                default_code = product_line.default_code
                qty = product_line.qty
                key = (family, default_code)

                if key not in data:
                    data[key] = [
                        {},  # Workers data
                        0.0,  # Total pz (all)
                        0.0,  # Total hours (all)
                    ]
                if workers not in data[key][0]:
                    data[key][0][workers] = [
                        0.0,  # total pz.
                        0.0,  # total time
                    ]
                product_hour = qty * rate
                # Workers:
                data[key][0][workers][0] += qty
                data[key][0][workers][1] += product_hour
                # Product:
                data[key][1] += qty
                data[key][2] += product_hour
        workers_list.sort()

        # Extend header:
        excel_pool.write_xls_line(
            ws_name, row, workers_list, f_header,
            col=fixed_cols)
        # Setup extra cols width:
        excel_pool.column_width(ws_name, [
            6 for i in range(fixed_cols)
            ])

        # Write data line:
        for key in data:
            row += 1
            family, default_code = key
            workers_data, product_total, product_hour = data[key]
            product_rate = total / hour if hour else 0  # Rate in tot pz / hour

            excel_pool.write_xls_line(ws_name, row, [
                family,
                default_code,
                (product_total, f_number),
                (product_hour, f_number),
                (product_rate, f_number),
                ], f_text)

            for workers in workers_data:
                col = fixed_cols + workers_list.index(workers)
                total, hour = workers_data[workers]
                rate = total / hour if hour else 0  # Rate in tot pz / hour

                excel_pool.write_xls_line(ws_name, row, [
                    (rate, f_number),  # Total rate
                    ], f_text, col=col)

        return excel_pool.return_attachment(
            cr, uid, 'Statistiche e medie', context=context)

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
            ], 'sort', required=True)
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
