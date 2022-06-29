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
import pickle
import logging
import openerp
import xmlrpclib
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


class res_company(orm.Model):
    ''' Add XMLRPC parameters for connections
    '''

    _inherit = 'res.company'

    # Utility:
    def get_xmlrpc_is_manual(self, cr, uid, company_id=False, context=None):
        ''' Check if is a manual backup
        '''
        if not company_id:
            company_id = self.search(cr, uid, [], context=context)[0]
        elif type(company_id) in (list, tuple):
            company_id = company_id[0]

        return self.browse(cr, uid, company_id, context=context).manual

    def get_xmlrpc_socket(
            self, cr, uid, company_id=False, context=None):
        ''' Read element with company_id or passed
        '''
        if not company_id:
            company_id = self.search(cr, uid, [], context=context)[0]
        elif type(company_id) in (list, tuple):
            company_id = company_id[0]

        parameters = self.browse(cr, uid, company_id, context=context)
        try:
            xmlrpc_server = "http://%s:%s" % (
                parameters.accounting_sync_host,
                parameters.accounting_sync_port,
            )
            return xmlrpclib.ServerProxy(xmlrpc_server)
        except:
            raise osv.except_osv(
                _('Import CL error!'),
                _(
                'XMLRPC for calling importation is not response check'
                ' if program is open on XMLRPC server\n[%s]' % (
                    sys.exc_info(), ) ), )

    _columns = {
        'accounting_sync': fields.boolean('Sync via XMLRPC'),
        'accounting_sync_host': fields.char(
            'Accounting sync XMLRPC host',
            size=64,
            help="IP address: 10.0.0.2  or hostname: server.example.com"),
        'accounting_sync_port': fields.integer(
            'Acounting sync port',
            help="XMLRPC port, example: 8000"),
        'manual': fields.boolean('Manual sync',
            help='Manual confirmation set manual accounting sync'),
        }

    _defaults = {
        'accounting_sync': lambda *x: True,
        'accounting_sync_port': lambda *x: 8000,
        }

class MrpProduction(orm.Model):
    ''' Add extra field to manage connection with accounting
    '''

    _inherit = 'mrp.production'

    # Override function
    def accounting_sync(self, cr, uid, ids, context=None):
        ''' Read all line to sync in accounting and produce it for
            XMLRPC call
        '''
        return True  # XXX DEAD MODULE FUNCTION
        if self.pool.get('res.company').get_xmlrpc_is_manual(
                cr, uid, False, context=context):

            # TODO procedure for set syncronization that is manual
            _logger.info('Manual sync production!')
            for sol in self.browse(cr, uid, ids, context=context)[
                    0].order_line_ids:
                # Jump line sync
                if sol.sync_state == 'sync':
                    continue

                data = {
                    'product_uom_maked_sync_qty': sol.product_uom_maked_qty,
                    'product_uom_maked_qty': 0.0, # always reset q maked
                    }

                # Different behaviour depend on state:
                if sol.sync_state == 'closed':
                    data['sync_state'] = 'sync'

                if sol.sync_state == 'partial':
                    account_qty = (
                        sol.product_uom_maked_sync_qty +
                        sol.product_uom_maked_qty
                        )
                    data['product_uom_maked_sync_qty'] = account_qty
                    if account_qty == sol.product_uom_qty: # TODO approx?
                        data['sync_state'] = 'sync' # closed!

                # Correct line as account sync:
                self.pool.get('sale.order.line').write(cr, uid, sol.id, data,
                    context=context)
            return True

        # TODO no more used!!!:
        # ----------------------
        # Read all line to close
        # ----------------------
        sol_pool = self.pool.get('sale.order.line')

        sol_ids = sol_pool.search(cr, uid, [
            ('sync_state', 'in', ('partial', 'closed'))
            ],
            order='order_id', # TODO line sequence?
            context=context, )

        # --------------
        # Write in file:
        # --------------
        parameters = {} # replace transit file
        sol_lines = {} # for close OK lines  (only for partial use)
        parameters['transit_string'] = ''

        for line in sol_pool.browse(cr, uid, sol_ids, context=context):
            sol_lines[line.id] = [ # only for partial check
                line.sync_state,
                line.product_uom_maked_qty + line.product_uom_maked_sync_qty,
                line.product_uom_qty # total
                ]
            parameters['transit_string'] += "%1s%-18s%-18s%10s%10s%10sXX\n" % (
                'P' if line.sync_state == 'partial' else 'T', # Type (part/tot)
                line.order_id.name.split("-")[-1].split("/")[0], # Order
                line.product_id.default_code, # Code
                int(line.product_uom_maked_qty),
                line.date_deadline, # Deadline
                line.id,
                )

        # -------------------------------
        # XMLRPC call for import the file
        # -------------------------------
        try:
            XMLRPC = self.pool.get(
                'res.company').get_xmlrpc_socket(
                    cr, uid, False, context=context) # TODO company_id

            # TODO use pickle library!!!
            res = XMLRPC.sprix('production', parameters['transit_string'])
            #pickle.dumps(parameters)) # param serialized
        except:
            raise osv.except_osv(
                _('Sync error!'),
                _('XMLRPC error calling production procedure'), )

        # test if there's an error during importation:
        if res.startswith("#ERR"):
            raise osv.except_osv(
                _('Sync error!'),
                _('Error from accounting:\n%s') % res,
            )

        # Update odoo sol with sync informations:
        item_ids = eval(res[2:])
        for item_id in item_ids: # update sync value in accounting
            if item_id not in sol_lines:
                _logger.warning('Order line in production not sync because'
                    'not exist in odoo but only in accounting (jumped)')
                continue

            if sol_lines[item_id][0] == 'partial':
                # check if is complete (total = account + current):
                data = {
                    'sync_state': 'partial_sync', # completed
                    'product_uom_maked_sync_qty': sol_lines[item_id][1],
                    'product_uom_maked_qty': 0,
                    }
                if sol_lines[item_id][2] == sol_lines[item_id][1]:
                   data['sync_state'] = 'sync'
                sol_pool.write(cr, uid, item_id, data, context=context)

            else: # complete
                sol_pool.write(cr, uid, item_id, {
                    'sync_state': 'sync',
                    'product_uom_maked_sync_qty': sol_lines[item_id][2], # tot.
                    'product_uom_maked_qty': 0,
                    }, context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
