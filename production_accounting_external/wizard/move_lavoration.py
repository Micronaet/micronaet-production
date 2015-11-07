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

class MrpMoveLavoration(orm.TransientModel):
    ''' Move from one lavoration to end in another date (and recalculate 
        parameters)
    '''
    
    _name = "mrp.production.move.lavoration.wizard"

    # --------------
    # Wizard button:
    # --------------
    def move_lavoration_item(self, cr, uid, ids, context=None):
        ''' Assign production to selected order line
        '''
        if context is None: 
            context = {}        
        active_id = context.get('active_id', False)    
        
        # Read wizard parameters:
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        
        # Move lavoration after passed:
        lavoration_pool = self.pool.get('mrp.production.workcenter.line')
        

        return {'type':'ir.actions.act_window_close'}

    _columns = {
        # Split info_
        'datetime': fields.date('New date', required=True),
        'note': fields.text(
            'Note', 
            help='Add extra info to specify why lavoration are moved'),
        
        # Parameters:
        'workhour_id': fields.many2one('hr.workhour'),
        'bom_id': fields.many2one('mrp.bom'),
        'workcenter_id': fields.many2one('mrp.workcenter'),
        'workers': fields.integer('Workers'),
        'scheduled_lavoration_id': fields.many2one(
            'mrp.production.workcenter.line', 
            'Current start point'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
