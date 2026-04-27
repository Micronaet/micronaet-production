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
import pdb
import sys
import logging
import openerp
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


class MRPPivotReportWizard(orm.TransientModel):
    """ MRP Pivot report Wizard
    """
    _name = 'mrp.pivot.report.wizard'
    _description = 'MRP Pivot Report Wizard'

    def action_report(self, cr, uid, ids, context=None):
        """ Generate Wizard pivot report
        """
        if context is None:
            context = {}

        # Pool used:
        line_pool = self.pool.get('sale.order.line')
        excel_pool = self.pool.get('excel.writer')

        # --------------------------------------------------------------------------------------------------------------
        # Collect data:
        # --------------------------------------------------------------------------------------------------------------
        # Wizard proxy parameters:
        wizard = self.browse(cr, uid, ids, context=context)[0]

        domain = []
        domain_text = ''

        from_deadline = wizard.from_deadline
        to_deadline = wizard.to_deadline

        if from_deadline:
            domain_text += ' [Dalla scadenza {}]'.format(from_deadline)
            domain.append(('date_deadline', '>=', from_deadline))
        if to_deadline:
            domain_text += ' [Alla scadenza {}]'.format(to_deadline)
            domain.append(('date_deadline', '<=', to_deadline))
        if not domain_text:
            domain_text = 'Nessun filtro applicato'

        line_ids = pick_pool.search(cr, uid, domain, context=context)
        _logger.info('Domain for search: %s [Tot: %s]' % (domain, len(line_ids)))

        master_data = {}
        master_deadline = []
        for line in pick_pool.browse(cr, uid, line_ids, context=context):
            # Readability:
            family = line.family_id
            mrp = line.mrp_id
            default_code = (line.default_code or '').strip()
            frame = default_code[6:8] or 'Grezzo'

            # Deadline column:
            date_deadline = line.date_deadline[:7] or '1900-01'
            if date_deadline not in master_deadline:
                master_deadline.append(date_deadline)

            # Quantity:
            product_uom_qty = line.product_uom_qty
            product_uom_maked_sync_qty = line.product_uom_maked_sync_qty
            mx_assigned_qty = line.mx_assigned_qty
            # TODO Check data in:
            remain = max((product_uom_qty - product_uom_maked_sync_qty - mx_assigned_qty), 0)

            key = (family, mrp, frame)
            if key in master_data:
                master_data[key] = {}
            if date_deadline not in master_deadline[key][date_deadline]:
                master_data[key][date_deadline] = 0.0
            master_data[key][date_deadline] += remain

        # --------------------------------------------------------------------------------------------------------------
        # Excel File:
        # --------------------------------------------------------------------------------------------------------------
        ws_name = 'MRP Pivot'
        excel_pool.create_worksheet(ws_name)

        # Format:
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        format_number = excel_pool.get_format('number')

        # Column dimension:
        col_width = (20, 20, 20, 15,)
        excel_pool.column_width(ws_name, col_width)
        fixed_col = len(col_width)

        # Title
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            'Pivot Produzioni, filtro: {}'.format(domain_text),
        ], format_title)

        # Header
        row += 1
        header = ['Famiglia', 'Gruppo', 'MRP', 'Colore']
        excel_pool.write_xls_line(ws_name, row, header, format_header)

        # Integrate date block:
        master_deadline.sort()
        empty = [0 for item in len(master_deadline)]

        for key in master_deadline:
            family, mrp, frame = key
            line_data = empty[:]
            for deadline in master_deadline[key]:
                col = master_data.index(deadline)
                line_data[col] = master_deadline[key][deadline]

            # Write line:
            row_data = [
                (family, format_text),
                (mrp, format_text),
                (frame, format_text),
            ]
            row_data.extend(line_data)
            row += 1
            excel_pool.write_xls_line(ws_name, row, row_data, format_number)
        return excel_pool.return_attachment(cr, uid, 'mrp_pivot.xlsx', context=context)

    _columns = {
        'from_deadline': fields.date('Da data scadenza'),
        'to_deadline': fields.date('A data scadenza'),
        }
