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


class CreateMrpProductionStatsWizard(orm.TransientModel):
    """ Create statistic for production
    """
    _name = 'mrp.production.create.stats.wizard'

    # --------------
    # Wizard button:
    # --------------
    def action_create_mrp_production_stats(self, cr, uid, ids, context=None):
        """ Add statistic record
            Context parameters: update_mode_id = ID of yet present stats
        """
        if context is None:
            context = {}

        update_mode_id = context.get('update_mode_id')

        # Pool used:
        stats_pool = self.pool.get('mrp.production.stats')
        line_pool = self.pool.get('mrp.production.stats.line')
        mrp_pool = self.pool.get('mrp.production')

        # Wizard proxy:
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        mrp_id = wiz_proxy.mrp_id.id
        if not mrp_id:
            raise osv.except_osv(
                _('Error'),
                _('No parent production!'))

        # Create header:
        stat_date = {
                'date': wiz_proxy.date,
                'total': wiz_proxy.total,
                'workers': wiz_proxy.workers,
                'hour': wiz_proxy.hour,
                'startup': wiz_proxy.startup,
                'mrp_id': mrp_id,
                'workcenter_id': wiz_proxy.workcenter_id.id,
                }
        if update_mode_id:
            # New management:
            stat_date.update({
                'crono_stop': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'working_done': True,
            })

            stats_pool.write(
                cr, uid, [update_mode_id], stat_date, context=context)
            stat_id = update_mode_id
        else:
            stat_id = stats_pool.create(cr, uid, stat_date, context=context)

        # Create details:
        for line in wiz_proxy.detail_ids:
            line_pool.create(cr, uid, {
                'stat_id': stat_id,
                'default_code': line.default_code,
                'qty': line.qty,
                }, context=context)

        # Reset old total
        mrp_pool.write(cr, uid, mrp_id, {
            'stat_start_total': '',
            'stat_start_datetime': False,
            }, context=context)
        return True

    _columns = {
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', required=True),
        'date': fields.date('Date', required=True),
        'total': fields.integer('Total', required=True),
        'workers': fields.integer('Workers'),
        'hour': fields.float('Tot. H'),
        'startup': fields.float('Start up time', digits=(16, 3)),
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade'),
        'operator_ids': fields.many2many(
            'res.partner', 'mrp_operator_stats_wiz_rel',
            'stat_id', 'partner_id',
            'Operatore', domain="[('is_operator', '=', True)]",
            context={'default_is_operator': True}),
        }

    _defaults = {
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }


class CreateMrpProductionStatsWizard(orm.TransientModel):
    """ Create statistic for production
    """
    _name = 'mrp.production.create.stats.detail.wizard'

    _columns = {
        'wizard_id': fields.many2one(
            'mrp.production.create.stats.wizard', 'Wizard'),
        'default_code': fields.char('Codice rif.', size=18),
        'qty': fields.integer('Q.'),
        }


class CreateMrpProductionStatsWizard(orm.TransientModel):
    """ Create statistic for production
    """
    _inherit = 'mrp.production.create.stats.wizard'

    _columns = {
        'detail_ids': fields.one2many(
            'mrp.production.create.stats.detail.wizard',
            'wizard_id', 'Dettagli'),
        }
