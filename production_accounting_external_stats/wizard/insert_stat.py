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

class CreateMrpProductionStatsWizard(orm.TransientModel):
    ''' Create statistic for production
    '''    
    _name = 'mrp.production.create.stats.wizard'
    
    # --------------
    # Wizard button:
    # --------------
    def action_create_mrp_production_stats(self, cr, uid, ids, context=None):
        ''' Add statistic record
        '''
        if context is None:
           context = {}

        # Wizard proxy:
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        mrp_id = wiz_proxy.mrp_id.id
        if not mrp_id: 
            raise osv.except_osv(
                _('Error'),
                _('No parent production!'))
            
        # Pool used:
        stats_pool = self.pool.get('mrp.production.stats')

        stats_pool.create(               
            cr, uid, {
                'date': wiz_proxy.date,
                'total': wiz_proxy.total,
                'workers': wiz_proxy.workers,
                'hour': wiz_proxy.hour,
                'startup': wiz_proxy.startup,
                'mrp_id': mrp_id,
                }, context=context)
        return True

    _columns = {
        'date': fields.date('Date', required=True),
        'total': fields.integer('Total', required=True), 
        'workers': fields.integer('Workers'),
        'hour': fields.float('Tot. H'),
        'startup': fields.float('Start up time', digits=(16, 3)),     
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade'),    
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', readonly=True), 
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
