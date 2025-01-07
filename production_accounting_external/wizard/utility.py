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


# Generic function
def get_product_from_template(self, cr, uid, tmpl_id, context=None):
    """ Return product (first) with that template ID
    """
    product_ids = self.pool.get('product.product').search(cr, uid, [
        ('product_tmpl_id', '=', tmpl_id)
        ], context=context)
    if product_ids:
        return product_ids[0]
    else:
        _logger.error('Error search product from template {}'.format(tmpl_id))
        # todo riattivare il prodotto cercando anche tra gli active false?
        # update product_product set active = 't' where product_tmpl_id = %s
        return False


def return_view(self, cr, uid, res_id, view_name, object_name, context=None):
    """Function that return dict action for next step of the wizard
    """
    if context is None:
        context = {}

    if not view_name:
        return {'type': 'ir.actions.act_window_close'}

    view_element = view_name.split(".")
    views = []

    if len(view_element)!= 2:
        return {'type': 'ir.actions.act_window_close'}

    model_id = self.pool.get('ir.model.data').search(
        cr, uid, [
            ('model', '=', 'ir.ui.view'),
            ('module', '=', view_element[0]),
            ('name', '=', view_element[1]),
            ], context=context)

    if model_id:
        view_id = self.pool.get('ir.model.data').read(
            cr, uid, model_id)[0]['res_id']
        views = [(view_id, 'form'), (False, 'tree'), ]

    if context.get('return', False):
        return {} # don't open production

    return {
        'view_type': 'form',
        'view_mode': 'form,tree',
        'res_model': object_name, # object linked to the view
        'views': views,
        'domain': [('id', 'in', res_id)],
        #'views': [(view_id, 'form')],
        #'view_id': False,
        'type': 'ir.actions.act_window',
        #'target': 'new',
        'res_id': res_id,  # IDs selected
       }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
