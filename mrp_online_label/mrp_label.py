#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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


class ResUsers(orm.Model):
    """ Model name: Res Users
    """
    _inherit = 'res.users'

    _columns = {
        'label_workcenter_id': fields.many2one(
            'mrp.workcenter', 'Default Line',
        )
    }


class MrpProduction(orm.Model):
    """ Model name: MRP Production
    """
    _inherit = 'mrp.production'

    def my_production_for_label_server_action(
            self, cr, uid, ids, context=None):
        """ My production list
        """
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        label_workcenter_id = user.label_workcenter_id.id
        view_id = False
        item_id = ids[0]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': item_id,
            'res_model': 'mrp.production',
            'view_id': view_id,
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [('label_workcenter_id', '=', label_workcenter_id)],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def open_production_detail(self, cr, uid, ids, context=None):
        """ Open form
        """
        # model_pool = self.pool.get('ir.model.data')
        # view_id = model_pool.get_object_reference(
        #     'module_name', 'view_name')[1]
        view_id = False
        item_id = ids[0]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': item_id,
            'res_model': 'mrp.production',
            'view_id': view_id,
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'label_workcenter_id': fields.many2one(
            'mrp.workcenter', 'Linea di lavorazione',
        )
    }

