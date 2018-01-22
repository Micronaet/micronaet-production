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
    ''' Wizard for
    '''
    _name = 'mrp.stats.excel.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        
        # Parameters:
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date
        #wc_id = wiz_browse.workcenter_id.id
        
        excel_pool = self.pool.get('excel.writer')
        
        # ---------------------------------------------------------------------
        # Create XLSX file:
        # ---------------------------------------------------------------------
        WS_name = 'Statistica'
        excel_poool.create_worksheet(WS_name)
        
        #column_width
        #set_format
        f_title = get_format('title')
        f_header = get_format('header')
        f_line = get_format('line')
        #excel_pool.write_xls_line(WS_name, row, line, default_format=False)


        # Collect data:
        line_pool = self.pool.get('mrp.production.stats')
    
        # Domain depend on wizard parameters:
        domain = []
        if from_date:
            domain.append(('date', '>=', from_date))
        if to_date:
            domain.append(('date', '<', to_date))
        
            
        line_ids = line_pool.search(cr, uid, domain, context=context)
        
        # Title row:
        row = 0
        excel_pool.write_xls_line(WS_name, row, [
            'Statistiche di produzione, filtro: %s' % wiz_filter,
            ], f_title)
            
        # Header line:
        row = 1
        excel_pool.write_xls_line(WS_name, row, [
            _('Linea'),
            _('Data'),
            _('Num. prod.'),
            _('Famiglia'),
            _('Lavoratori'),
            _('Appront.'),
            _('Tot. pezzi'),
            _('Tempo'),
            _('Pz / H'),
            ], f_header)

        # Write data:
        for line in sorted(
                line_pool.browse(cr, uid, line_ids, context=context), 
                key=lambda x: (
                    x.workcenter_id.name, # Line
                    x.mrp_id.name, # Data
                    x.mrp_id.bom_id.product_tmpl_id.name, # Family
                    )):
            row += 1
        excel_pool.write_xls_line(WS_name, row, [
            line.workcenter_id.name,
            excel_pool.format_date(line.date),
            line.mrp_id.name,
            line.mrp_id.bom_id.product_tmpl_id.name,
            line.workers,
            excel_pool.format_hour(line.startup),
            line.total,
            excel_pool.format_hour(line.hour),
            line.total / line.hour if line.hour else '#ERR',
            ], f_line)

        return excel_pool.return_attachment(cr, uid, 
            'Statistiche di produzione', context=context)
        
    _columns = {        
        'from_date': fields.date('From date >='),
        'to_date': fields.date('From date <'),
        #'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter'),
        # TODO family
        # TODO line
        # Product?
        }
        
    _defaults = {
        'from_date': lambda *x: '%s01' % datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        'to_date': lambda *x: '%s01' % (datetime.now() - reletivedelta(
            months=1)).strftime(DEFAULT_SERVER_DATE_FORMAT)[:8],
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
