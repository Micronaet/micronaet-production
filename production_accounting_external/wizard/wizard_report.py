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


class MrpProductionReportWizard(orm.TransientModel):
    """ Procurements depend on sale
    """
    _name = 'mrp.production.report.wizard'
    _description = 'Production report wizard'

    # --------------
    # Button events:
    # --------------
    def print_report_production_extra_file(self, cr, uid, ids, context=None):
        """ Call original with redirect
        """
        mrp_pool = self.pool.get('mrp.production')

        if context is None:
            context = {}
        ctx = context.copy()
        mrp_id = context.get('active_id')
        mrp = mrp_pool.browse(cr, uid, mrp_id, context=context)

        path = os.path.expanduser('~/NAS/industria40/MRP')
        filename = os.path.join(path, '%s.xlsx' % mrp.name)

        ctx['force_data'] = {
            'report_name': 'mrp',  # For extract
            'report_filename': filename,
            'context': context,
        }

        return self.print_report_production(cr, uid, ids, context=ctx)

    def print_report_production(self, cr, uid, ids, context=None):
        """ Redirect to report passing parameters
        """
        if context is None:
            context = {}

        wiz_proxy = self.browse(cr, uid, ids)[0]

        datas = {}
        datas['wizard'] = True  # started from wizard

        datas['mode'] = wiz_proxy.mode
        datas['wizard_show_lavoration'] = wiz_proxy.show_lavoration
        datas['wizard_show_sale'] = wiz_proxy.show_sale
        datas['wizard_show_frame'] = wiz_proxy.show_frame
        datas['wizard_show_note'] = wiz_proxy.show_note
        datas['wizard_job_id'] = wiz_proxy.job_id.id

        if 'force_data' in context:
            datas.update(context['force_data'])

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'production_report',
            'datas': datas,
            'context': context,
            }

    def print_report_cut(self, cr, uid, ids, context=None):
        """ Redirect to report passing parameters
        """
        wiz_proxy = self.browse(cr, uid, ids)[0]

        datas = {}
        datas['wizard'] = True  # started from wizard
        datas['mode'] = wiz_proxy.mode

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'production_cut_report',
            'datas': datas,
            'context': context,
            }

    _columns = {
        'mode': fields.selection([
            ('clean', 'Clean from delivery and maked'),
            ('all', 'Normal mode'),
            ], 'Report mode', required=True),

        'show_lavoration': fields.boolean('A. Show lavoration'),
        'show_sale': fields.boolean('B. Show sale part'),
        'show_frame': fields.boolean('C. Show frame part'),
        'show_note': fields.boolean('Mostra sistema note'),
        'job_id': fields.many2one('mrp.production.stats', 'Job'),
        }

    _defaults = {
        'mode': lambda *x: 'clean',
        'show_lavoration': lambda *x: True,
        'show_sale': lambda *x: True,
        'show_frame': lambda *x: True,
        'show_note': lambda *x: True,
        }
