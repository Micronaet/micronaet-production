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


class SaleOrderLine(orm.Model):
    """ Model name: Sale line
    """
    _inherit = 'sale.order.line'

    def button_next_line(self, cr, uid, ids, context=None):
        """ Call next from sale line
        """
        mrp_pool = self.pool.get('mrp.production')
        line = self.browse(cr, uid, ids, context=context)
        return mrp_pool.button_next_line(
            cr, uid, [line.mrp_id.id], context=context)


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

    def get_first_line_undone(self, cr, uid, ids, context=None):
        """ Return first undone line to be produced,
            context: extra_line_item = extra line ID returned
        """
        if context is None:
            context = {}
        # Extra line management (for next line preview)
        extra_line_item = context.get('extra_line_item')
        if extra_line_item < 0:
            extra_line_item = False

        # Extract uncomplete line (and extra line):
        mrp = self.browse(cr, uid, ids, context=context)[0]
        this_line_id = False
        sorted_line = sorted(mrp.order_line_ids, key=lambda x: x.sequence)
        i = 0
        for line in sorted_line:
            if line.product_uom_maked_sync_qty >= (
                    line.product_uom_qty + line.mx_assigned_qty):
                continue  # All done

            # A. Default run:
            this_line_id = line.id

            # B. Extra line run mode:
            if extra_line_item:
                return [
                    item.id for item in sorted_line[i, i + extra_line_item]]
            i += 1

        # A. Default run
        if not this_line_id:
            raise osv.except_osv(
                _('Error'),
                _('End of production, please close and confirm statistic!'),
                )
        return this_line_id

    def button_next_line(self, cr, uid, ids, context=None):
        """ Next line operation
        """
        model_pool = self.pool.get('ir.model.data')
        line_id = self.get_first_line_undone(
            cr, uid, ids, context=context)

        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'sale_order_label_online_view_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Production Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': line_id,
            'res_model': 'sale.order.line',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    def start_block_start_label(self, cr, uid, ids, context=None):
        """ Launch stats start action and open view for production start
        """
        self.start_blocking_stats(cr, uid, ids, context=context)
        return self.button_next_line(cr, uid, ids, context=context)

    def my_production_for_label_server_action(
            self, cr, uid, ids, context=None):
        """ My production list
        """
        model_pool = self.pool.get('ir.model.data')
        tree_view_id = model_pool.get_object_reference(
            cr, uid,
            'mrp_online_label', 'online_label_mrp_view_tree')[1]

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        label_workcenter_id = user.label_workcenter_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id': ,
            'res_model': 'mrp.production',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree')],
            'domain': [
                ('label_workcenter_id', '=', label_workcenter_id),
                ('state', 'not in', ('cancel', 'done'))
            ],
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

