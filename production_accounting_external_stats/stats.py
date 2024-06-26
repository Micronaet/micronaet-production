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
import pdb
import sys
from openerp import netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools.sql import drop_view_if_exists
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


class ResPartner(orm.Model):
    """ Statistic data
    """
    _inherit = 'res.partner'

    _columns = {
        'is_operator': fields.boolean(
            'Operatore', help='Operatore di produzione'),
    }


class MrpProductionStat(orm.Model):
    """ Statistic data
    """
    _name = 'mrp.production.stats'
    _description = 'MRP stats'
    _order = 'date desc'
    _rec_name = 'date'

    def _function_start_total_text(
            self, cr, uid, ids, fields, args,
            context=None):
        """ Fields function for calculate detail in text mode
        """
        res = {}
        for stat in self.browse(cr, uid, ids, context=context):
            res[stat.id] = ''
            for line in stat.line_ids:
                res[stat.id] += '[\'%s\' >> %s] ' % (
                    line.default_code, line.qty)
        return res

    _columns = {
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', required=True),
        'date': fields.date('Date', required=True),
        'total': fields.integer('Total'),  # Removed for line:, required=True),
        'workers': fields.integer('Workers'),
        'operator_ids': fields.many2many(
            'res.partner', 'mrp_operator_stats_rel',
            'stat_id', 'partner_id',
            'Operatore'),
        'hour': fields.float('Tot. H'),
        'startup': fields.float('Start up time', digits=(16, 3)),
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', ondelete='cascade'),
        'stat_start_total': fields.text('Ref. Total',
            help='Blocked per code[:6] totals'),

        'total_text_detail': fields.function(
            _function_start_total_text, method=True,
            type='text', string='Dettaglio', store=False),
        }

    _defaults = {
        'date': lambda *x: datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }


class MrpProductionStatLine(orm.Model):
    """ Statistic data
    """
    _name = 'mrp.production.stats.line'
    _description = 'MRP stats line'

    _columns = {
        'stat_id': fields.many2one(
            'mrp.production.stats', 'Stat.'),
        'default_code': fields.char('Codice rif.', size=18),
        'qty': fields.integer('Q.'),
        }


class MrpProductionStatInherit(orm.Model):
    """ Statistic data
    """
    _inherit = 'mrp.production.stats'

    _columns = {
        'line_ids': fields.one2many(
            'mrp.production.stats.line', 'stat_id', 'Righe'),
        }


class MrpProductionStatMixed(osv.osv):
    """ Create view object for Dashboard (query not table!)
    """
    _name = 'mrp.production.stats.mixed'
    _description = 'MRP stats mixed'
    _order = 'date_planned desc,workcenter_id,is_total'
    _rec_name = 'date_planned'
    _auto = False

    # Button event:
    def nothing(self, cr, uid, ids, context=None):
        """ Dummy button
        """
        return True

    _columns = {
        # mrp.production.workcenter.line:
        # 'name': fields.char('MRP name', readonly=True),
        'is_today': fields.boolean('Is today', readonly=True),
        'is_total': fields.boolean('Day total', readonly=True),
        'date_planned': fields.date('Date planned', readonly=True),
        'product_id': fields.many2one(
            'product.product', 'Family', readonly=True),
        'production_id': fields.many2one(
            'mrp.production', 'Production', readonly=True),
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Line', readonly=True),
        'lavoration_qty': fields.float('Lavoration q.', readonly=True),
        'hour': fields.float('Tot. H.', readonly=True),
        'workers': fields.integer('Workers', readonly=True),
        # 'operator_ids': fields.many2many(
        #    'res.partner', 'mrp_operator_stats_mix_rel',
        #    'stat_id', 'partner_id',
        #    'Operatore'),
        'startup': fields.float('Startup', readonly=True),

        # sale.order.line:
        'todo_qty': fields.float('Total q.', readonly=True),
        'maked_qty': fields.integer('Done q.', readonly=True),
        'remain_qty': fields.float('Remain q.', readonly=True),
        }

    def init(self, cr):
        drop_view_if_exists(cr, 'mrp_production_stats_mixed')
        cr.execute("""
            CREATE or REPLACE view mrp_production_stats_mixed as (
                SELECT 
                    min(st.id) as id,
                    False as is_total,
                    st.date as date_planned,
                    sum(st.total) as maked_qty,
                    sum(st.startup) as startup,
                    sum(st.workers) as workers,
                    sum(st.hour) as hour,
                    st.workcenter_id as workcenter_id,
                    mrp.id as production_id,

                    mrp.product_id as product_id,

                    DATE(st.date) = DATE(now()) as is_today,

                    '' as name,
                    0 as todo_qty,
                    0 as remain_qty,
                    0 as lavoration_qty
                FROM 
                        mrp_production mrp
                    JOIN 
                        mrp_production_stats st
                    ON 
                        (st.mrp_id = mrp.id)
                GROUP BY
                    st.date,
                    st.workcenter_id,
                    mrp.product_id,
                    mrp.id
                HAVING 
                    DATE(st.date) + INTERVAL '8 days' >= DATE(now())
                    
                UNION ALL

                SELECT 
                    10000 + max(st.id) as id,
                    True as is_total,
                    st.date as date_planned,
                    sum(st.total) as maked_qty,
                    sum(st.startup) as startup,
                    sum(st.workers) as workers,
                    sum(st.hour) as hour,
                    st.workcenter_id as workcenter_id,
                    0 as production_id,

                    0 as product_id,

                    DATE(st.date) = DATE(now()) as is_today,

                    'TOTAL' as name,
                    0 as todo_qty,
                    0 as remain_qty,
                    0 as lavoration_qty
                FROM 
                    mrp_production_stats st
                GROUP BY
                    st.date,
                    st.workcenter_id
                HAVING 
                    DATE(st.date) + INTERVAL '8 days' >= DATE(now())
                )""")  # HAVING mrp.state != 'cancel' mrp.workcenter_id


class MrpProduction(orm.Model):
    """ Statistic data
    """
    _inherit = 'mrp.production'

    # Utility:
    def get_current_locked_status(
            self, cr, uid, ids, code_pos=6, context=None):
        """ Dict for locked with code 6 char
        """
        locked = {}
        for item in self.browse(
                cr, uid, ids, context=context)[0].order_line_ids:
            default_code = item.product_id.default_code[:code_pos]
            if default_code in locked:
                locked[default_code] += item.product_uom_maked_sync_qty
            else:
                locked[default_code] = item.product_uom_maked_sync_qty
        return locked

    # Button events:
    def start_blocking_stats(self, cr, uid, ids, context=None):
        """ Save current production to check difference
        """

        return self.write(cr, uid, ids, {
            'stat_start_total': '%s' % (
                self.get_current_locked_status(cr, uid, ids, context=context),
                ),
            # Save for online calc datetime start:
            'stat_start_datetime': datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT),
            }, context=context)

    def stop_blocking_stats(self, cr, uid, ids, context=None):
        """ Get default and open wizard
        """
        mrp_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Check difference:
        current = self.get_current_locked_status(
            cr, uid, ids, context=context)
        try:
            previous = eval(mrp_proxy.stat_start_total)
        except:
            raise osv.except_osv(
                _('Errore'),
                _('La procedura prevede di aprire la giornata, '
                  ' fare i bloccaggi e poi alla fine chiuderla!'),
            )

        total = 0
        default_res = []
        for default_code, current_tot in current.iteritems():
            last_tot = previous.get(default_code, 0)
            if last_tot != current_tot:  # TODO negative?
                partial = current_tot - last_tot  # difference
                total += partial
                default_res.append({
                    'default_code': default_code,
                    'qty': partial,
                    })

        ctx = context.copy()
        try:
            workcenter_id = mrp_proxy.lavoration_ids[0].workcenter_id.id
        except:
            workcenter_id = False
        try:
            workers = mrp_proxy.lavoration_ids[0].workers
        except:
            workers = 0
        try:
            hour = mrp_proxy.lavoration_ids[0].duration
        except:
            hour = 0

        ctx.update({
            # 'default_workcenter_id':
            'default_total': total,
            'default_mrp_id': mrp_proxy.id,
            'default_workcenter_id': workcenter_id,
            'default_workers': workers,
            'default_hour': hour,
            'default_detail_ids': default_res,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Stats'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mrp.production.create.stats.wizard',
            'domain': [],
            'context': ctx,
            'target': 'new',
            'nodestroy': False,
        }

    def _function_start_readable_text(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for mrp in self.browse(cr, uid, ids, context=context):
            res[mrp.id] = ''
            if mrp.stat_start_total:
                for default_code, total in eval(
                        mrp.stat_start_total).iteritems():
                    res[mrp.id] += '[\'%s\': %s] ' % (default_code, total)
        return res

    _columns = {
        'stat_start_datetime': fields.datetime('Start stats datetime'),
        'stat_start_total': fields.text('Ref. Total',
            help='Total current item when start blocking operation'),

        'stats_ids': fields.one2many(
            'mrp.production.stats', 'mrp_id', 'Stats'),
        'stat_start_total_text': fields.function(
            _function_start_readable_text, method=True,
            type='char', size=200, string='Totale rif.', store=False),
        }
