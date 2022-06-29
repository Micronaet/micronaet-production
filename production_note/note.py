# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
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


class MrpProductionNote(orm.Model):
    """ Model name: MRP Note
    """
    _name = 'mrp.production.note'
    _description = 'Note di produzione'
    _order = 'create_date desc'

    _columns = {
        'create_uid': fields.many2one('res.users', 'Inserito da'),
        'create_date': fields.datetime('Inserita il'),

        'name': fields.char('Nota', size=120),
        'note': fields.text('Dettaglio'),

        'mrp_id': fields.many2one('mrp.production', 'Produzione'),
        'line_id': fields.many2one('sale.order.line', 'Riga ordine'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'manager_id': fields.many2one('res.users', 'Responsabile'),
        'stats_id': fields.many2one(
            'mrp.production.stats', 'Statistica di prod.'),

        'state': fields.selection([
            ('draft', 'Bozza'),
            ('confirmed', 'Confermata'),
            ('cancel', 'Annullata'),
            ], 'Stato'),
        }

    _defaults = {
        'state': lambda *x: 'draft',
        'create_uid': lambda s, cr, uid, ctx: uid,
        'create_date': lambda *x: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT)
    }


class SaleOrderLine(orm.Model):
    """ Sale line
    """
    _inherit = 'sale.order.line'

    def new_mrp_production_note_line(self, cr, uid, ids, context=None):
        """ Open new note linked to this resource
        """
        if context is None:
            context = {}
        # note_pool = self.pool.get('mrp.production.note')
        line_id = ids[0]
        current = self.browse(cr, uid, line_id, context=context)

        # model_pool = self.pool.get('ir.model.data')
        # view_id = model_pool.get_object_reference(
        #    'module_name', 'view_name')[1]
        view_id = False

        ctx = context.copy()
        ctx['default_partner_id'] = current.order_id.partner_id.id
        ctx['default_line_id'] = line_id
        ctx['default_mrp_id'] = current.mrp_production_id.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuova nota'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id': 1,
            'res_model': 'mrp.production.note',
            'view_id': view_id,
            'views': [(False, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }
